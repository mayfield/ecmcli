"""
Manage ECM Groups.
"""

from . import base


class Printer(object):
    """ Mixin for printing commands. """

    expands = ','.join([
        'statistics',
        'product',
        'account',
        'target_firmware',
        'settings_bindings.setting',
        'configuration'
    ])

    def setup_args(self, parser):
        parser.add_argument('-v', '--verbose', action='store_true')
        super().setup_args(parser)

    def prerun(self, args):
        self.printed_header = False
        self.printer = self.verbose_printer if args.verbose else \
                       self.terse_printer
        super().prerun(args)

    def bundle_group(self, group):
        group['target'] = '%s (%s)' % (group['product']['name'],
                                       group['target_firmware']['version'])
        group['settings'] = dict((x['setting']['name'] + ':', x['value'])
                                 for x in group['settings_bindings']
                                 if x['value'] is not None)
        stats = group['statistics']
        group['online'] = stats['online_count']
        group['offline'] = stats['offline_count']
        group['total'] = stats['device_count']
        return group

    def verbose_printer(self, group):
        print('ID:           ', group['id'])
        print('Name:         ', group['name'])
        print('Online:       ', group['online'])
        print('Total:        ', group['total'])
        print('Target:       ', group['target'])
        print('Account:      ', group['account']['name'])
        print('Suspended:    ', group['statistics']['suspended_count'])
        print('Synchronized: ', group['statistics']['synched_count'])
        if group['settings']:
            print('Settings...')
            for x in sorted(group['settings'].items()):
                print('  %-30s %s' % x)
        print()

    def terse_printer(self, group):
        if not self.printed_header:
            self.printed_header = True
            info = {
                "name": 'NAME (ID)',
                "account": 'ACCOUNT',
                "target": 'TARGET',
                "online": 'ONLINE'
            }
        else:
            info = {
                "name": '%s (%s)' % (group['name'], group['id']),
                "account": group['account']['name'],
                "target": group['target'],
                "online": '%s/%s' % (group['online'], group['total'])
            }
        print('%(name)-30s %(account)-16s %(target)-16s %(online)-5s' % info)


class Show(Printer, base.Command):
    """ Show group(s). """

    name = 'show'

    def setup_args(self, parser):
        parser.add_argument('ident', metavar='GROUP_ID_OR_NAME', nargs='?')
        super().setup_args(parser)

    def run(self, args):
        if args.ident:
            groups = [self.api.get_by_id_or_name('groups', args.ident,
                                                 expand=self.expands)]
        else:
            groups = self.api.get_pager('groups', expand=self.expands)
        for x in groups:
            self.printer(self.bundle_group(x))


class Create(base.Command):
    """ Create a new group.
    A group mostly represents configuration for more than one device, but
    also manages settings such as alerts and log acquisition. """

    name = 'create'

    def setup_args(self, parser):
        parser.add_argument('--name')
        parser.add_argument('--product')
        parser.add_argument('--firmware')

    def run(self, args):
        name = args.name or input('Name: ')
        if not name:
            raise SystemExit("Name required")

        product = args.product or input('Product: ')
        products = dict((x['name'], x) for x in self.api.get_pager('products'))
        if product not in products:
            if not product:
                print("Product required")
            else:
                print("Invalid product:", product)
            print("\nValid products...")
            for x in sorted(products):
                print("\t", x)
            raise SystemExit(1)

        fw = args.firmware or input('Firmware: ')
        firmwares = dict((x['version'], x)
                         for x in self.api.get_pager('firmwares',
                                                product=products[product]['id']))
        if fw not in firmwares:
            if not fw:
                print("Firmware required")
            else:
                print("Invalid firmware:", fw)
            print("\nValid firmares...")
            for x in sorted(firmwares):
                print("\t", x)
            raise SystemExit(1)

        self.api.post('groups', {
            "name": name,
            "product": products[product]['resource_uri'],
            "target_firmware": firmwares[fw]['resource_uri']
        })


class Edit(base.Command):
    """ Edit group attributes. """

    name = 'edit'

    def setup_args(self, parser):
        parser.add_argument('ident', metavar='GROUP_ID_OR_NAME')
        parser.add_argument('--name')
        parser.add_argument('--firmware')

    def run(self, args):
        group = self.api.get_by_id_or_name('groups', args.ident)
        updates = {}
        if args.name:
            updates['name'] = args.name
        if args.firmware:
            fw = self.api.get_by(['version'], 'firmwares', args.firmware)
            updates['target_firmware'] = fw['resource_uri']
        self.api.put('groups', group['id'], updates)


class Delete(base.Command):
    """ Delete one or more groups. """

    name = 'delete'

    def setup_args(self, parser):
        parser.add_argument('ident', metavar='GROUP_ID_OR_NAME', nargs='+')
        parser.add_argument('-f', '--force', action="store_true")

    def run(self, args):
        for ident in args.ident:
            group = self.api.get_by_id_or_name('groups', ident)
            if not args.force and \
               not base.confirm('Delete group: %s' % group['name'],
                                exit=False):
                continue
            self.api.delete('groups', group['id'])


class Move(base.Command):
    """ Move group to a different account. """

    name = 'move'

    def setup_args(self, parser):
        parser.add_argument('ident', metavar='GROUP_ID_OR_NAME')
        parser.add_argument('new_account', metavar='NEW_ACCOUNT_ID_OR_NAME')
        parser.add_argument('-f', '--force', action="store_true")

    def run(self, args):
        group = self.api.get_by_id_or_name('groups', args.ident)
        account = self.api.get_by_id_or_name('accounts', args.new_account)
        self.api.put('groups', group['id'],
                     {"account": account['resource_uri']})


class Search(Printer, base.Command):
    """ Search for groups. """

    name = 'search'

    def setup_args(self, parser):
        parser.add_argument('search', metavar='SEARCH_CRITERIA', nargs='+')
        super().setup_args(parser)

    def run(self, args):
        fields = ['name', ('firmware', 'target_firmware.version'),
                  ('product', 'product.name'), ('account', 'account.name')]
        results = list(self.api.search('groups', fields, args.search,
                                       expand=self.expands))
        if not results:
            raise SystemExit("No Results For: %s" % ' '.join(args.search))
        for x in results:
            self.printer(self.bundle_group(x))


class Groups(base.Command):
    """ Manage ECM Groups. """

    name = 'groups'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(Show, default=True)
        self.add_subcommand(Create)
        self.add_subcommand(Edit)
        self.add_subcommand(Delete)
        self.add_subcommand(Move)
        self.add_subcommand(Search)

command_classes = [Groups]
