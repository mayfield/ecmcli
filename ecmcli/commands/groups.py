"""
Manage ECM Groups.
"""

import shellish
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
        self.add_argument('-v', '--verbose', action='store_true')
        super().setup_args(parser)

    def prerun(self, args):
        self.printed_header = False
        self.printer = self.verbose_printer if args.verbose else \
                       self.terse_printer
        super().prerun(args)

    def bundle_group(self, group):
        group['product'] = group['product']['name']
        group['firmware'] = group['target_firmware']['version']
        if not isinstance(group['settings_bindings'], str):
            group['settings'] = dict((x['setting']['name'] + ':', x['value'])
                                     for x in group['settings_bindings']
                                     if not isinstance(x, str) and
                                        x['value'] is not None)
        else:
            group['settings'] = {}
        stats = group['statistics']
        group['online'] = stats['online_count']
        group['offline'] = stats['offline_count']
        group['total'] = stats['device_count']
        group['account_name'] = group['account']['name']
        return group

    def verbose_printer(self, groups):
        for x in groups:
            group = self.bundle_group(x)
            print('ID:           ', group['id'])
            print('Name:         ', group['name'])
            print('Online:       ', group['online'])
            print('Total:        ', group['total'])
            print('Product:      ', group['product'])
            print('Firmware:     ', group['firmware'])
            print('Account:      ', group['account']['name'])
            print('Suspended:    ', group['statistics']['suspended_count'])
            print('Synchronized: ', group['statistics']['synched_count'])
            if group['settings']:
                print('Settings...')
                for x in sorted(group['settings'].items()):
                    print('  %-30s %s' % x)
            print()

    def terse_printer(self, groups):
        fields = (
            ("name", 'Name'),
            ("id", 'ID'),
            ("account_name", 'Account'),
            ("product", 'Product'),
            ("firmware", 'Firmware'),
            ("online", 'Online'),
            ("offline", 'Offline'),
            ("total", 'Total'),
        )
        table = shellish.Table(headers=[x[1] for x in fields],
                               accessors=[x[0] for x in fields])
        table.print(map(self.bundle_group, groups))


class Show(Printer, base.ECMCommand):
    """ Show group(s). """

    name = 'show'

    def setup_args(self, parser):
        self.add_group_argument(nargs='?')
        super().setup_args(parser)

    def run(self, args):
        if args.ident:
            groups = [self.api.get_by_id_or_name('groups', args.ident,
                                                 expand=self.expands)]
        else:
            groups = self.api.get_pager('groups', expand=self.expands)
        self.printer(groups)


class Create(base.ECMCommand):
    """ Create a new group.
    A group mostly represents configuration for more than one device, but
    also manages settings such as alerts and log acquisition. """

    name = 'create'

    def setup_args(self, parser):
        self.add_argument('--name')
        self.add_product_argument('--product')
        self.add_firmware_argument('--firmware')

    def run(self, args):
        name = args.name or input('Name: ')
        if not name:
            raise SystemExit("Name required")

        product = args.product or input('Product: ')
        products = dict((x['name'], x)
                        for x in self.api.get_pager('products'))
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


class Edit(base.ECMCommand):
    """ Edit group attributes. """

    name = 'edit'

    def setup_args(self, parser):
        self.add_group_argument()
        self.add_argument('--name')
        self.add_firmware_argument('--firmware')

    def run(self, args):
        group = self.api.get_by_id_or_name('groups', args.ident)
        updates = {}
        if args.name:
            updates['name'] = args.name
        if args.firmware:
            fw = self.api.get_by(['version'], 'firmwares', args.firmware)
            updates['target_firmware'] = fw['resource_uri']
        self.api.put('groups', group['id'], updates)


class Delete(base.ECMCommand):
    """ Delete one or more groups. """

    name = 'delete'

    def setup_args(self, parser):
        self.add_group_argument('idents', nargs='+')
        self.add_argument('-f', '--force', action="store_true")

    def run(self, args):
        for ident in args.idents:
            group = self.api.get_by_id_or_name('groups', ident)
            if not args.force and \
               not base.confirm('Delete group: %s' % group['name'],
                                exit=False):
                continue
            self.api.delete('groups', group['id'])


class Move(base.ECMCommand):
    """ Move group to a different account. """

    name = 'move'

    def setup_args(self, parser):
        self.add_group_argument()
        self.add_account_argument('new_account', metavar='NEW_ACCOUNT_ID_OR_NAME')
        self.add_argument('-f', '--force', action="store_true")

    def run(self, args):
        group = self.api.get_by_id_or_name('groups', args.ident)
        account = self.api.get_by_id_or_name('accounts', args.new_account)
        self.api.put('groups', group['id'],
                     {"account": account['resource_uri']})


class Search(Printer, base.ECMCommand):
    """ Search for groups. """

    name = 'search'
    fields = ['name', ('firmware', 'target_firmware.version'),
              ('product', 'product.name'), ('account', 'account.name')]

    def setup_args(self, parser):
        searcher = self.make_searcher('groups', self.fields)
        self.lookup = searcher.lookup
        self.add_search_argument(searcher)
        super().setup_args(parser)

    def run(self, args):
        results = list(self.lookup(args.search, expand=self.expands))
        if not results:
            raise SystemExit("No Results For: %s" % ' '.join(args.search))
        self.printer(results)


class Groups(base.ECMCommand):
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
