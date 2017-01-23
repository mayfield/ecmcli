"""
Manage ECM Routers.
"""

import time
from . import base
from .. import ui


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
        self.inject_table_factory()
        super().setup_args(parser)

    def prerun(self, args):
        if args.verbose:
            self.expands = self.verbose_expands
            self.printer = self.verbose_printer
        else:
            self.expands = self.terse_expands
            self.printer = self.terse_printer
        super().prerun(args)

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
            t = self.make_table(columns=[key_col_width, None],
                                headers=['Router Name', x['name']])
            x['since'] = ui.time_since(x['state_ts'])
            x['joined'] = ui.time_since(x['create_ts']) + ' ago'
            x['account_info'] = '%s (%s)' % (x['account']['name'],
                                             x['account']['id'])
            loc = x.get('last_known_location')
            x['location_info'] = location_url % loc if loc else ''
            ents = x['featurebindings']
            acc = lambda x: x['settings']['entitlement']['sf_entitlements'] \
                             [0]['name']
            x['entitlements'] = ', '.join(map(acc, ents)) if ents else ''
            x['dashboard_url'] = 'https://cradlepointecm.com/ecm.html' \
                                 '#devices/dashboard?id=%s' % x['id']
            for key, label in sorted(fields.items(), key=lambda x: x[1]):
                t.print_row([label, x[key]])
            t.close()

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
            ("id", "ID"),
            ("name", "Name"),
            ("product_info", "Product"),
            ("firmware_info", "Firmware"),
            ("account_name", "Account"),
            ("group_name", "Group"),
            ("ip_address", "IP Address"),
            (lambda x: self.colorize_conn_state(x['state']), "Conn")
        )
        with self.make_table(headers=[x[1] for x in fields],
                             accessors=[x[0]for x in fields]) as t:
            t.print(map(self.bundle_router, routers))

    def colorize_conn_state(self, state):
        colormap = {
            "online": 'green',
            "offline": 'red'
        }
        color = colormap.get(state, 'yellow')
        return '<%s>%s</%s>' % (color, state, color)

    def bundle_router(self, router):
        router['account_name'] = router['account']['name']
        router['group_name'] = self.group_name(router['group'])
        fw = router['actual_firmware']
        router['firmware_info'] = fw['version'] if fw else ''
        router['product_info'] = router['product']['name']
        return router


class List(Printer, base.ECMCommand):
    """ List routers registered with ECM. """

    name = 'ls'

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
        results = self.lookup(args.search, expand=self.expands)
        if not results:
            raise SystemExit("No results for: %s" % ' '.join(args.search))
        self.printer(results)


class GroupAssign(base.ECMCommand):
    """ Assign a router to a [new] group. """

    name = 'groupassign'
    use_pager = False

    def setup_args(self, parser):
        self.add_router_argument()
        self.add_group_argument('new_group', metavar='NEW_GROUP_ID_OR_NAME')
        self.add_argument('-f', '--force', action='store_true')

    def run(self, args):
        router = self.api.get_by_id_or_name('routers', args.ident,
                                            expand='group')
        group = self.api.get_by_id_or_name('groups', args.new_group)
        if router['group'] and not args.force:
            self.confirm('Replace router group: %s => %s' % (
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

    name = 'mv'

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

    name = 'rm'
    use_pager = False

    def setup_args(self, parser):
        self.add_router_argument('idents', nargs='+')
        self.add_argument('-f', '--force', action='store_true')

    def run(self, args):
        for id_or_name in args.idents:
            router = self.api.get_by_id_or_name('routers', id_or_name)
            if not args.force and \
               not self.confirm('Delete router: %s, id:%s' % (router['name'],
                                router['id']), exit=False):
                continue
            self.api.delete('routers', router['id'])


class Reboot(base.ECMCommand):
    """ Reboot connected router(s). """

    name = 'reboot'
    use_pager = False

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
               not self.confirm("Reboot %s (%s)" % (x['name'], x['id']),
                                exit=False):
                continue
            print("Rebooting: %s (%s)" % (x['name'], x['id']))
            self.api.put('remote', '/control/system/reboot', 1, id=x['id'])


class FlashLEDS(base.ECMCommand):
    """ Flash the LEDs of online routers. """

    name = 'flashleds'
    min_flash_delay = 0.200
    use_pager = False

    def setup_args(self, parser):
        self.add_router_argument('idents', nargs='*')
        self.add_argument('--duration', '-d', type=float, default=60,
                          help='Duration in seconds for LED flashing.')

    def run(self, args):
        if args.idents:
            routers = [self.api.get_by_id_or_name('routers', r)
                       for r in args.idents]
        else:
            routers = self.api.get_pager('routers')
        ids = []
        print("Flashing LEDS for:")
        for rinfo in routers:
            print("    %s (%s)" % (rinfo['name'], rinfo['id']))
            ids.append(rinfo['id'])
        rfilter = {
            "id__in": ','.join(ids)
        }
        leds = dict.fromkeys((
            "LED_ATTENTION",
            "LED_SS_1",
            "LED_SS_2",
            "LED_SS_3",
            "LED_SS_4"
        ), 0)
        print()
        start = time.time()
        while time.time() - start < args.duration:
            for k, v in leds.items():
                leds[k] = state = not v
            step = time.time()
            self.api.put('remote', '/control/gpio', leds, **rfilter)
            print("\rLEDS State: %s" % ('ON ' if state else 'OFF'), end='',
                  flush=True)
            time.sleep(max(0, self.min_flash_delay - (time.time() - step)))


class Routers(base.ECMCommand):
    """ Manage ECM Routers. """

    name = 'routers'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(List, default=True)
        self.add_subcommand(Edit)
        self.add_subcommand(Search)
        self.add_subcommand(Move)
        self.add_subcommand(GroupAssign)
        self.add_subcommand(GroupUnassign)
        self.add_subcommand(Delete)
        self.add_subcommand(Reboot)
        self.add_subcommand(FlashLEDS)

command_classes = [Routers]
