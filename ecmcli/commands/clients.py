"""
Harvest a detailed list of clients seen by online routers.
"""

import asyncio
import cellulario
import itertools
import pickle
import pkg_resources
from . import base


class List(base.ECMCommand):
    """ Show the currently connected clients on a router. The router must be
    connected to ECM for this to work. """

    name = 'ls'
    wifi_bw_modes = {
        0: "20",
        1: "40",
        2: "80"
    }
    wifi_modes = {
        0: "802.11b",
        1: "802.11g",
        2: "802.11n",
        3: "802.11n-only",
        4: "802.11ac"
    }
    wifi_bands = {
        0: "2.4",
        1: "5"
    }

    def setup_args(self, parser):
        self.add_router_argument('idents', nargs='*')
        self.add_argument('-v', '--verbose', action="store_true")
        self.inject_table_factory()

    @property
    def mac_db(self):
        try:
            return self._mac_db
        except AttributeError:
            mac_db = pkg_resources.resource_stream('ecmcli', 'mac.db')
            self._mac_db = pickle.load(mac_db)
            return self._mac_db

    def mac_lookup_short(self, info):
        return self.mac_lookup(info, 0)

    def mac_lookup_long(self, info):
        return self.mac_lookup(info, 1)

    def mac_lookup(self, info, idx):
        mac = int(''.join(info['mac'].split(':')[:3]), 16)
        localadmin = mac & 0x20000
        # This really only pertains to cradlepoint devices.
        if localadmin and mac not in self.mac_db:
            mac &= 0xffff
        return self.mac_db.get(mac, [None, None])[idx]

    def wifi_status_acc(self, client, default=''):
        """ Accessor for WiFi RSSI, txrate and mode. """
        if 'wifi' not in client:
            return default
        wifi = client['wifi']
        status = [
            self.get_wifi_rssi(wifi),
            '%d Mbps' % wifi['txrate'],
            self.wifi_modes[wifi['mode']],
        ]
        return ', '.join(status)

    def get_wifi_rssi(self, wifi):
        rssi_vals = []
        for i in itertools.count(0):
            try:
                rssi_vals.append(wifi['rssi%d' % i])
            except KeyError:
                break
        rssi = sum(rssi_vals) / len(rssi_vals)
        if rssi > -40:
            fmt = '<b><green>%.0f</green></b>'
        elif rssi > -55:
            fmt = '<green>%.0f</green>'
        elif rssi > -65:
            fmt = '<yellow>%.0f</yellow>'
        elif rssi > -80:
            fmt = '<red>%.0f</red>'
        else:
            fmt = '<b><red>%.0f</red></b>'
        return fmt % rssi + ' dBm'

    def wifi_bss_acc(self, client, default=''):
        """ Accessor for WiFi access point. """
        if 'wifi' not in client:
            return default
        wifi = client['wifi']
        radio = wifi['radio_info']
        bss = radio['bss'][wifi['bss']]
        band = self.wifi_bands[radio['wifi_band']]
        return '%s (%s Ghz)' % (bss['ssid'], band)

    def run(self, args):
        filters = {
            "state": 'online',
            "product__series": 3
        }
        if args.idents:
            routers = [self.api.get_by_id_or_name('routers', x)
                       for x in args.idents]
            filters["id__in"] = ','.join(x['id'] for x in routers)
        headers = ['Router', 'IP Addresses', 'Hostname', 'MAC', 'Hardware']
        accessors = ['router', 'ips', 'dns', 'mac']
        if not args.verbose:
            accessors.append(self.mac_lookup_short)
        else:
            headers.extend(['WiFi Status', 'WiFi AP'])
            accessors.extend([
                self.mac_lookup_long,
                self.wifi_status_acc,
                self.wifi_bss_acc
            ])
        cell = cellulario.IOCell(coord='pool')
        async_api = self.api.clone(async=True, loop=cell.loop)

        @cell.tier()
        def get_clients(route):
            """ Initial Cell tier for clients info. """
            for clients in self.api.remote('status.lan.clients', **filters):
                if not clients['success']:
                    continue
                by_mac = {}
                for x in clients['results'][0]['data']:
                    x['router'] = clients['router']['name']
                    if x['mac'] in by_mac:
                        by_mac[x['mac']]['_ips'].append(x['ip_address'])
                    else:
                        x['_ips'] = [x['ip_address']]
                        by_mac[x['mac']] = x
                for x in by_mac.values():
                    x['ips'] = ', '.join(sorted(x['_ips'], key=len))
                yield from route.emit(clients['id'], by_mac)

        @cell.tier(pool_size=10)
        def get_dns(route, rid, clients):
            leases = (yield from async_api.get('remote', 'status/dhcpd/leases',
                                               id=rid))[0]
            yield from route.emit(rid, leases)

        reduce_from = [get_clients, get_dns]
        if args.verbose:
            @cell.tier(source=get_clients, pool_size=10)
            def get_wifi(route, rid, clients):
                requests = [
                    async_api.get('remote', 'config/wlan/radio', id=rid),
                    async_api.get('remote', 'status/wlan/clients', id=rid)
                ]
                results = yield from asyncio.gather(*requests)
                radio, wclients = results[0][0], results[1][0]
                radios = radio['success'] and radio['data']
                if wclients['success'] and wclients['data']:
                    for x in wclients['data']:
                        x['radio_info'] = radios[x['radio']]
                yield from route.emit(rid, wclients)
            reduce_from.append(get_wifi)

        @cell.tier(source=reduce_from, gatherby=lambda rid, _: rid)
        def reduce(route, clients, dns, wifi=None):
            clients = clients[1]
            dns = dns[1]
            if dns['success'] and dns['data']:
                for x in dns['data']:
                    if x['mac'] in clients:
                        clients[x['mac']]['dns'] = x['hostname']
            wifi = wifi and wifi[1]
            if wifi and wifi['success'] and wifi['data']:
                for x in wifi['data']:
                    if x['mac'] in clients:
                        clients[x['mac']]['wifi'] = x
            for x in clients.values():
                yield from route.emit(x)

        @cell.cleaner
        def cleanup():
            async_api.close()

        with self.make_table(headers=headers, accessors=accessors) as t:
            t.print(cell)


class OrigList(base.ECMCommand):
    """ Show the currently connected clients on a router. The router must be
    connected to ECM for this to work. """
    # XXX Broken when len(clients) > page_size

    name = 'lsorig'
    wifi_bw_modes = {
        0: "20",
        1: "40",
        2: "80"
    }
    wifi_modes = {
        0: "802.11b",
        1: "802.11g",
        2: "802.11n",
        3: "802.11n-only",
        4: "802.11ac"
    }
    wifi_bands = {
        0: "2.4",
        1: "5"
    }

    def setup_args(self, parser):
        self.add_router_argument('idents', nargs='*')
        self.add_argument('-v', '--verbose', action="store_true")
        self.inject_table_factory()

    @property
    def mac_db(self):
        try:
            return self._mac_db
        except AttributeError:
            mac_db = pkg_resources.resource_stream('ecmcli', 'mac.db')
            self._mac_db = pickle.load(mac_db)
            return self._mac_db

    def mac_lookup_short(self, info):
        return self.mac_lookup(info, 0)

    def mac_lookup_long(self, info):
        return self.mac_lookup(info, 1)

    def mac_lookup(self, info, idx):
        mac = int(''.join(info['mac'].split(':')[:3]), 16)
        localadmin = mac & 0x20000
        # This really only pertains to cradlepoint devices.
        if localadmin and mac not in self.mac_db:
            mac &= 0xffff
        return self.mac_db.get(mac, [None, None])[idx]

    def make_dns_getter(self, ids):
        dns = {}
        for leases in self.api.get_pager('remote', 'status/dhcpd/leases',
                                         id__in=','.join(ids)):
            if not leases['success'] or not leases['data']:
                continue
            dns.update(dict((x['mac'], x['hostname'])
                            for x in leases['data']))
        return lambda x: dns.get(x['mac'], '')

    def make_wifi_getter(self, ids):
        wifi = {}
        radios = {}
        for x in self.api.get_pager('remote', 'config/wlan/radio',
                                    id__in=','.join(ids)):
            if x['success']:
                radios[x['id']] = x['data']
        for x in self.api.get_pager('remote', 'status/wlan/clients',
                                    id__in=','.join(ids)):
            if not x['success'] or not x['data']:
                continue
            for client in x['data']:
                client['radio_info'] = radios[x['id']][client['radio']]
                wifi[client['mac']] = client
        return lambda x: wifi.get(x['mac'], {})

    def wifi_status_acc(self, client, default):
        """ Accessor for WiFi RSSI, txrate and mode. """
        if not client:
            return default
        status = [
            self.get_wifi_rssi(client),
            '%d Mbps' % client['txrate'],
            self.wifi_modes[client['mode']],
        ]
        return ', '.join(status)

    def get_wifi_rssi(self, wifi_info):
        rssi_vals = []
        for i in itertools.count(0):
            try:
                rssi_vals.append(wifi_info['rssi%d' % i])
            except KeyError:
                break
        rssi = sum(rssi_vals) / len(rssi_vals)
        if rssi > -40:
            fmt = '<b><green>%.0f</green></b>'
        elif rssi > -55:
            fmt = '<green>%.0f</green>'
        elif rssi > -65:
            fmt = '<yellow>%.0f</yellow>'
        elif rssi > -80:
            fmt = '<red>%.0f</red>'
        else:
            fmt = '<b><red>%.0f</red></b>'
        return fmt % rssi + ' dBm'

    def wifi_bss_acc(self, client, default):
        """ Accessor for WiFi access point. """
        if not client:
            return default
        radio = client['radio_info']
        bss = radio['bss'][client['bss']]
        band = self.wifi_bands[client['radio_info']['wifi_band']]
        return '%s (%s Ghz)' % (bss['ssid'], band)

    def run(self, args):
        if args.idents:
            routers = [self.api.get_by_id_or_name('routers', x)
                       for x in args.idents]
        else:
            routers = self.api.get_pager('routers', state='online',
                                         product__series=3)
        ids = dict((x['id'], x['name']) for x in routers)
        if not ids:
            raise SystemExit("No online routers found")
        data = []
        for clients in self.api.get_pager('remote', 'status/lan/clients',
                                          id__in=','.join(ids)):
            if not clients['success']:
                continue
            by_mac = {}
            for x in clients['data']:
                x['router'] = ids[str(clients['id'])]
                if x['mac'] in by_mac:
                    by_mac[x['mac']]['ip_addresses'].append(x['ip_address'])
                else:
                    x['ip_addresses'] = [x['ip_address']]
                    by_mac[x['mac']] = x
            data.extend(by_mac.values())
        dns_getter = self.make_dns_getter(ids)
        ip_getter = lambda x: ', '.join(sorted(x['ip_addresses'], key=len))
        headers = ['Router', 'IP Addresses', 'Hostname', 'MAC', 'Hardware']
        accessors = ['router', ip_getter, dns_getter, 'mac']
        if not args.verbose:
            accessors.append(self.mac_lookup_short)
        else:
            wifi_getter = self.make_wifi_getter(ids)
            headers.extend(['WiFi Status', 'WiFi AP'])
            na = ''
            accessors.extend([
                self.mac_lookup_long,
                lambda x: self.wifi_status_acc(wifi_getter(x), na),
                lambda x: self.wifi_bss_acc(wifi_getter(x), na)
            ])
        with self.make_table(headers=headers, accessors=accessors) as t:
            t.print(data)


class Clients(base.ECMCommand):

    name = 'clients'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(List, default=True)
        self.add_subcommand(OrigList)

command_classes = [Clients]
