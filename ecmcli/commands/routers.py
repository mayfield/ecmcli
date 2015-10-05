"""
Manage ECM Routers.
"""

import humanize
import pickle
import pkg_resources
import shellish
from . import base


class Printer(object):
    """ Mixin for printer commands. """

    terse_expands = ','.join([
        'account',
        'group',
        'product',
        'actual_firmware'
    ])
    verbose_expands = ','.join([
        'account',
        'group',
        'product',
        'actual_firmware',
        'last_known_location',
        'featurebindings'
    ])

    def setup_args(self, parser):
        self.add_argument('-v', '--verbose', action='store_true')
        super().setup_args(parser)

    def since(self, dt):
        """ Return humanized time since for an absolute datetime. """
        if dt is None:
            return ''
        since = dt.now(tz=dt.tzinfo) - dt
        return humanize.naturaltime(since)[:-4]

    def verbose_printer(self, routers):
        fields = {
            'account_info': 'Account',
            'asset_id': 'Asset ID',
            'config_status': 'Config Status',
            'custom1': 'Custom 1',
            'custom2': 'Custom 2',
            'dashboard_url': 'Dashboard URL',
            'desc': 'Description',
            'entitlements': 'Entitlements',
            'firmware_info': 'Firmware',
            'group_name': 'Group',
            'id': 'ID',
            'ip_address': 'IP Address',
            'joined': 'Joined',
            'locality': 'Locality',
            'location_info': 'Location',
            'mac': 'MAC',
            'product_info': 'Product',
            'quarantined': 'Quarantined',
            'serial_number': 'Serial Number',
            'since': 'Connection Time',
            'state': 'Connection',
        }
        location_url = 'https://maps.google.com/maps?' \
                       'q=loc:%(latitude)f+%(longitude)f'
        key_col_width = max(map(len, fields.values()))
        first = True
        for x in routers:
            if first:
                first = False
            else:
                print()
            x = self.bundle_router(x)
            t = shellish.Table(columns=[key_col_width, None],
                               headers=['Router Name', x['name']])
            x['since'] = self.since(x['state_ts'])
            x['joined'] = self.since(x['create_ts']) + ' ago'
            x['account_info'] = '%s (%s)' % (x['account']['name'],
                                             x['account']['id'])
            loc = x.get('last_known_location')
            x['location_info'] = location_url % loc if loc else ''
            ents = x['featurebindings']
            acc = lambda x: x['settings']['entitlement'] \
                             ['sf_entitlements'][0]['name']
            x['entitlements'] = ', '.join(map(acc, ents)) if ents else ''
            x['dashboard_url'] = 'https://cradlepointecm.com/ecm.html' \
                                 '#devices/dashboard?id=%s' % x['id']
            for key, label in sorted(fields.items(), key=lambda x: x[1]):
                t.print_row([label, x[key]])

    def group_name(self, group):
        """ Sometimes the group is empty or a URN if the user is not
        authorized to see it.  Return the best extrapolation of the
        group name. """
        if not group:
            return ''
        elif isinstance(group, str):
            return '<id:%s>' % group.rsplit('/')[-2]
        else:
            return group['name']

    def terse_printer(self, routers):
        fields = (
            ("name", "Name"),
            ("id", "ID"),
            ("product_info", "Product"),
            ("firmware_info", "Firmware"),
            ("account_name", "Account"),
            ("group_name", "Group"),
            ("ip_address", "IP Address"),
            ("state", "Conn")
        )
        table = shellish.Table(headers=[x[1] for x in fields],
                               accessors=[x[0]for x in fields])
        table.print(map(self.bundle_router, routers))

    def bundle_router(self, router):
        router['account_name'] = router['account']['name']
        router['group_name'] = self.group_name(router['group'])
        fw = router['actual_firmware']
        router['firmware_info'] = fw['version'] if fw else ''
        router['product_info'] = router['product']['name']
        return router

    def prerun(self, args):
        if args.verbose:
            self.expands = self.verbose_expands
            self.printer = self.verbose_printer
        else:
            self.expands = self.terse_expands
            self.printer = self.terse_printer
        super().prerun(args)


class Show(Printer, base.ECMCommand):
    """ Display routers. """

    name = 'show'

    def setup_args(self, parser):
        self.add_router_argument(nargs='?')
        super().setup_args(parser)

    def run(self, args):
        if args.ident:
            routers = [self.api.get_by_id_or_name('routers', args.ident,
                       expand=self.expands)]
        else:
            routers = self.api.get_pager('routers', expand=self.expands)
        self.printer(routers)


class Search(Printer, base.ECMCommand):
    """ Search for routers. """

    name = 'search'
    fields = ['name', 'desc', 'mac', ('account', 'account.name'), 'asset_id',
              'custom1', 'custom2', ('group', 'group.name'),
              ('firmware', 'actual_firmware.version'), 'ip_address',
              ('product', 'product.name'), 'serial_number', 'state']

    def setup_args(self, parser):
        searcher = self.make_searcher('routers', self.fields)
        self.lookup = searcher.lookup
        self.add_search_argument(searcher)
        super().setup_args(parser)

    def run(self, args):
        results = list(self.lookup(args.search, expand=self.expands))
        if not results:
            raise SystemExit("No results for: %s" % ' '.join(args.search))
        self.printer(results)


class GroupAssign(base.ECMCommand):
    """ Assign a router to a [new] group. """

    name = 'groupassign'

    def setup_args(self, parser):
        self.add_router_argument()
        self.add_group_argument('new_group', metavar='NEW_GROUP_ID_OR_NAME')
        self.add_argument('-f', '--force', action='store_true')

    def run(self, args):
        router = self.api.get_by_id_or_name('routers', args.ident,
                                            expand='group')
        group = self.api.get_by_id_or_name('groups', args.new_group)
        if router['group'] and not args.force:
            base.confirm('Replace router group: %s => %s' % (
                         router['group']['name'], group['name']))
        self.api.put('routers', router['id'],
                     {"group": group['resource_uri']})


class GroupUnassign(base.ECMCommand):
    """ Remove a router from its group. """

    name = 'groupunassign'

    def setup_args(self, parser):
        self.add_router_argument()

    def run(self, args):
        router = self.api.get_by_id_or_name('routers', args.ident)
        self.api.put('routers', router['id'], {"group": None})


class Edit(base.ECMCommand):
    """ Edit a group's attributes. """

    name = 'edit'

    def setup_args(self, parser):
        self.add_router_argument()
        self.add_argument('--name')
        self.add_argument('--desc')
        self.add_argument('--asset_id')
        self.add_argument('--custom1')
        self.add_argument('--custom2')

    def run(self, args):
        router = self.api.get_by_id_or_name('routers', args.ident)
        value = {}
        fields = ['name', 'desc', 'asset_id', 'custom1', 'custom2']
        for x in fields:
            v = getattr(args, x)
            if v is not None:
                value[x] = v
        self.api.put('routers', router['id'], value)


class Move(base.ECMCommand):
    """ Move a router to different account """

    name = 'move'

    def setup_args(self, parser):
        self.add_router_argument()
        self.add_account_argument('new_account',
                                  metavar='NEW_ACCOUNT_ID_OR_NAME')

    def run(self, args):
        router = self.api.get_by_id_or_name('routers', args.ident)
        account = self.api.get_by_id_or_name('accounts', args.new_account)
        self.api.put('routers', router['id'],
                     {"account": account['resource_uri']})


class Delete(base.ECMCommand):
    """ Delete (unregister) a router from ECM """

    name = 'delete'

    def setup_args(self, parser):
        self.add_router_argument('idents', nargs='+')
        self.add_argument('-f', '--force', action='store_true')

    def run(self, args):
        for id_or_name in args.idents:
            router = self.api.get_by_id_or_name('routers', id_or_name)
            if not args.force and \
               not base.confirm('Delete router: %s, id:%s' % (router['name'],
                                router['id']), exit=False):
                continue
            self.api.delete('routers', router['id'])


class Clients(base.ECMCommand):
    """ Show the currently connected clients on a router. The router must be
    connected to ECM for this to work. """

    name = 'clients'

    def setup_args(self, parser):
        self.add_router_argument('idents', nargs='*')
        self.add_argument('-v', '--verbose', action="store_true")

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
        localadmin =  mac & 0x20000
        # This really only pertains to cradlepoint devices.
        if localadmin and mac not in self.mac_db:
            mac &= 0xffff
        return self.mac_db.get(mac, [None, None])[idx]

    def make_dns_getter(self, ids):
        dns = {}
        for leases in self.api.get_pager('remote', '/status/dhcpd/leases',
                                         id__in=','.join(ids)):
            if not leases['success'] or not leases['data']:
                continue
            dns.update(dict((x['mac'], x['hostname'])
                            for x in leases['data']))
        return lambda x: dns.get(x['mac'], '')

    def make_wifi_getter(self, ids):
        wifi = {}
        for wclients in self.api.get_pager('remote', '/status/wlan/clients',
                                           id__in=','.join(ids)):
            if not wclients['success'] or not wclients['data']:
                continue
            wifi.update(dict((x['mac'], x) for x in wclients['data']))
        return lambda x: wifi.get(x['mac'], {})

    def run(self, args):
        if args.idents:
            routers = [self.api.get_by_id_or_name('routers', x)
                       for x in args.idents]
        else:
            routers = self.api.get_pager('routers', state='online',
                                         product__series=3)
        ids = dict((x['id'], x['name']) for x in routers
                   if x['state'] == 'online')
        if not ids:
            raise SystemExit("No online routers found")
        data = []
        for clients in self.api.get_pager('remote', '/status/lan/clients',
                                          id__in=','.join(ids)):
            if not clients['success']:
                continue
            for x in clients['data']:
                x['router'] = ids[str(clients['id'])]
                data.append(x)
        dns_getter = self.make_dns_getter(ids)
        headers = ['Router', 'IP Address', 'Hostname', 'MAC', 'Hardware']
        accessors = ['router', 'ip_address', dns_getter, 'mac']
        if not args.verbose:
            accessors.append(self.mac_lookup_short)
        else:
            wifi_getter = self.make_wifi_getter(ids)
            headers.extend(['WiFi Signal', 'WiFi Speed'])
            na = '<dim>n/a</dim>'
            accessors.extend([
                self.mac_lookup_long,
                lambda x: wifi_getter(x).get('rssi0', na),
                lambda x: wifi_getter(x).get('txrate', na)
            ])
        table = shellish.Table(headers=headers, accessors=accessors)
        table.print(data)


class Reboot(base.ECMCommand):
    """ Reboot connected router(s). """

    name = 'reboot'

    def setup_args(self, parser):
        self.add_router_argument('idents', nargs='*')
        self.add_argument('-f', '--force', action='store_true')

    def run(self, args):
        if args.idents:
            routers = [self.api.get_by_id_or_name('routers', r)
                       for r in args.idents]
        else:
            routers = self.api.get_pager('routers')
        for x in routers:
            if not args.force and \
               not base.confirm("Reboot %s (%s)" % (x['name'], x['id']),
                                exit=False):
                continue
            print("Rebooting: %s (%s)" % (x['name'], x['id']))
            self.api.put('remote', '/control/system/reboot', 1, id=x['id'])


class Routers(base.ECMCommand):
    """ Manage ECM Routers. """

    name = 'routers'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(Show, default=True)
        self.add_subcommand(Search)
        self.add_subcommand(Move)
        self.add_subcommand(GroupAssign)
        self.add_subcommand(GroupUnassign)
        self.add_subcommand(Delete)
        self.add_subcommand(Clients)
        self.add_subcommand(Reboot)

command_classes = [Routers]
