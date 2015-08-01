"""
Manage ECM Routers.
"""

import humanize
from . import base


def since(dt):
    """ Return humanized time since for an absolute datetime. """
    if dt is None:
        return ''
    since = dt.now(tz=dt.tzinfo) - dt
    return humanize.naturaltime(since)[:-4]


class Routers(base.Command):
    """ Manage ECM Routers. """

    name = 'routers'
    terse_expands = ','.join([
        'account',
        'group'
    ])
    verbose_expands = ','.join([
        'account',
        'group',
        'product',
        'actual_firmware',
        'last_known_location',
        'featurebindings'
    ])

    def init_argparser(self):
        parser = base.ArgParser(self.name, subcommands=True)

        s = parser.add_subcommand('show', self.show_cmd, default=True)
        s.add_argument('ident', metavar='ROUTER_ID_OR_NAME', nargs='?')
        s.add_argument('-v', '--verbose', action='store_true')

        p = parser.add_subcommand('edit', self.edit_cmd)
        p.add_argument('ident', metavar='ROUTER_ID_OR_NAME')
        p.add_argument('--name')
        p.add_argument('--desc')
        p.add_argument('--asset_id')
        p.add_argument('--custom1')
        p.add_argument('--custom2')

        p = parser.add_subcommand('move', self.move_cmd)
        p.add_argument('ident', metavar='ROUTER_ID_OR_NAME')
        p.add_argument('new_account', metavar='NEW_ACCOUNT_ID_OR_NAME')

        p = parser.add_subcommand('delete', self.delete_cmd)
        p.add_argument('ident', metavar='ROUTER_ID_OR_NAME', nargs='+')
        p.add_argument('-f', '--force', action='store_true')

        p = parser.add_subcommand('groupassign', self.groupassign_cmd)
        p.add_argument('ident', metavar='ROUTER_ID_OR_NAME')
        p.add_argument('new_group', metavar='NEW_GROUP_ID_OR_NAME')
        p.add_argument('-f', '--force', action='store_true')

        p = parser.add_subcommand('groupunassign', self.groupunassign_cmd)
        p.add_argument('ident', metavar='ROUTER_ID_OR_NAME')

        p = parser.add_subcommand('search', self.search_cmd)
        p.add_argument('search', metavar='SEARCH_CRITERIA', nargs='+')
        p.add_argument('-v', '--verbose', action='store_true')

        return parser

    def prerun(self, args):
        self.verbose = getattr(args, 'verbose', False)
        if self.verbose:
            self.expands = self.verbose_expands
            self.printer = self.verbose_printer
        else:
            self.expands = self.terse_expands
            self.printer = self.terse_printer

    def show_cmd(self, args, routers=None):
        """ Display routers """
        if routers is None:
            if args.ident:
                routers = [self.api.get_by_id_or_name('routers', args.ident,
                           expand=self.expands)]
            else:
                routers = self.api.get_pager('routers', expand=self.expands)
        self.printer(routers)

    def verbose_printer(self, routers):
        fields = {
            'account_info': 'Account',
            'asset_id': 'Asset ID',
            'config_status': 'Config Status',
            'custom1': 'Custom 1',
            'custom2': 'Custom 2',
            'desc': 'Description',
            'entitlements': 'Entitlements',
            'firmware_info': 'Firmware',
            'group_info': 'Group',
            'id': 'ID',
            'ip_address': 'IP Address',
            'joined': 'Joined',
            'locality': 'Locality',
            'location_info': 'Location',
            'mac': 'MAC',
            'name': 'Name',
            'product_info': 'Product',
            'quarantined': 'Quarantined',
            'serial_number': 'Serial Number',
            'since': 'Connection Time',
            'state': 'Connection',
            'dashboard_url': 'Dashboard URL'
        }
        location_url = 'https://maps.google.com/maps?' \
                       'q=loc:%(latitude)f+%(longitude)f'
        offset = max(map(len, fields.values())) + 2
        fmt = '%%-%ds: %%s' % offset
        first = True
        for x in routers:
            if first:
                first = False
            else:
                print()
            print('*' * 10, '%s (%s) - %s - %s' % (x['name'], x['id'], x['mac'],
                  x['ip_address']), '*' * 10)
            x['since'] = since(x['state_ts'])
            x['joined'] = since(x['create_ts']) + ' ago'
            x['account_info'] = '%s (%s)' % (x['account']['name'], x['account']['id'])
            x['group_info'] = x['group']['name'] if x['group'] else ''
            x['product_info'] = x['product']['name']
            fw = x['actual_firmware']
            x['firmware_info'] = fw['version'] if fw else '<unsupported>'
            loc = x.get('last_known_location')
            x['location_info'] = location_url % loc if loc else ''
            ents = x['featurebindings']
            acc = lambda x: x['settings']['entitlement'] \
                             ['sf_entitlements'][0]['name']
            x['entitlements'] = ', '.join(map(acc, ents)) if ents else ''
            x['dashboard_url'] = 'https://cradlepointecm.com/ecm.html#devices/' \
                                 'dashboard?id=%s' % x['id']
            for key, label in sorted(fields.items(), key=lambda x: x[1]):
                print(fmt % (label, x[key]))

    def terse_printer(self, routers):
        fmt = '%(name_info)-24s %(account_name)-18s %(group_name)-22s ' \
              '%(ip_address)-16s %(state)s'
        print(fmt % {
            "name_info": "NAME (ID)",
            "account_name": "ACCOUNT",
            "group_name": "GROUP",
            "ip_address": "IP ADDRESS",
            "state": "CONN"
        })
        for x in routers:
            x['name_info'] = '%s (%s)' % (x['name'], x['id'])
            x['account_name'] = x['account']['name']
            x['group_name'] = x['group']['name'] if x['group'] else ''
            print(fmt % x)

    def groupassign_cmd(self, args):
        """ Assign a router to a [new] group """
        router = self.api.get_by_id_or_name('routers', args.ident,
                                            expand='group')
        group = self.api.get_by_id_or_name('groups', args.new_group)
        if router['group'] and not args.force:
            base.confirm('Replace router group: %s => %s' % (
                         router['group']['name'], group['name']))
        self.api.put('routers', router['id'],
                     {"group": group['resource_uri']})

    def groupunassign_cmd(self, args):
        """ Remove a router from its group """
        router = self.api.get_by_id_or_name('routers', args.ident)
        self.api.put('routers', router['id'], {"group": None})

    def edit_cmd(self, args):
        """ Edit a group's attributes """
        router = self.api.get_by_id_or_name('routers', args.ident)
        value = {}
        fields = ['name', 'desc', 'asset_id', 'custom1', 'custom2']
        for x in fields:
            v = getattr(args, x)
            if v is not None:
                value[x] = v
        self.api.put('routers', router['id'], value)

    def move_cmd(self, args):
        """ Move a router to different account """
        router = self.api.get_by_id_or_name('routers', args.ident)
        account = self.api.get_by_id_or_name('accounts', args.new_account)
        self.api.put('routers', router['id'],
                     {"account": account['resource_uri']})

    def delete_cmd(self, args):
        """ Delete (unregister) a router from ECM """
        for id_or_name in args.ident:
            router = self.api.get_by_id_or_name('routers', id_or_name)
            if not args.force and \
               not base.confirm('Delete router: %s, id:%s' % (router['name'],
                                router['id']), exit=False):
                continue
            self.api.delete('routers', router['id'])

    def search_cmd(self, args):
        """ Search for routers """
        fields = ['name', 'desc', 'mac', ('account', 'account.name'), 'asset_id',
                  'custom1', 'custom2', ('group', 'group.name'),
                  ('firmware', 'actual_firmware.version'), 'ip_address',
                  ('product', 'product.name'), 'serial_number', 'state']
        results = list(self.api.search('routers', fields, args.search,
                                       expand=self.expands))
        if not results:
            raise SystemExit("No results for: %s" % ' '.join(args.search))
        self.show_cmd(args, routers=results)

command_classes = [Routers]
