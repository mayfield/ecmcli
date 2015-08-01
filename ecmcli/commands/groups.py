"""
Manage ECM Groups.
"""

from . import base


class Groups(base.Command):
    """ Manage ECM Groups. """

    name = 'groups'
    expands = ','.join([
        'statistics',
        'product',
        'account',
        'target_firmware',
        'settings_bindings.setting',
        'configuration'
    ])

    def init_argparser(self):
        parser = base.ArgParser(self.name, subcommands=True)

        s = parser.add_subcommand('show', self.show_cmd, default=True)
        s.add_argument('ident', metavar='GROUP_ID_OR_NAME', nargs='?')
        s.add_argument('-v', '--verbose', action='store_true')

        s = parser.add_subcommand('create', self.create_cmd)
        s.add_argument('--name')
        s.add_argument('--product')
        s.add_argument('--firmware')

        s = parser.add_subcommand('delete', self.delete_cmd)
        s.add_argument('ident', metavar='GROUP_ID_OR_NAME', nargs='+')
        s.add_argument('-f', '--force', action="store_true")

        s = parser.add_subcommand('move', self.move_cmd)
        s.add_argument('ident', metavar='GROUP_ID_OR_NAME')
        s.add_argument('new_account', metavar='NEW_ACCOUNT_ID_OR_NAME')
        s.add_argument('-f', '--force', action="store_true")

        s = parser.add_subcommand('edit', self.edit_cmd)
        s.add_argument('ident', metavar='GROUP_ID_OR_NAME')
        s.add_argument('--name')
        s.add_argument('--firmware')

        s = parser.add_subcommand('search', self.search_cmd)
        s.add_argument('search', metavar='SEARCH_CRITERIA', nargs='+')
        s.add_argument('-v', '--verbose', action='store_true')
        return parser

    def prerun(self, args):
        self.printed_header = False
        self.verbose = getattr(args, 'verbose', False)

    def completer(self, text, line, begin, end):
        return [x for x in self.argparser.subparser.choices if x.startswith(text)]

    def show_cmd(self, args, groups=None):
        """ Show group(s) """
        if groups is None:
            if args.ident:
                groups = [self.api.get_by_id_or_name('groups', args.ident,
                                                     expand=self.expands)]
            else:
                groups = self.api.get_pager('groups', expand=self.expands)
        for x in groups:
            self.printer(self.bundle_group(x))

    def create_cmd(self, args):
        """ Create a new group
        A group mostly represents configuration for more than one device, but
        also manages settings such as alerts and log acquisition. """
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

    def edit_cmd(self, args):
        """ Edit group attributes """
        group = self.api.get_by_id_or_name('groups', args.ident)
        updates = {}
        if args.name:
            updates['name'] = args.name
        if args.firmware:
            fw = self.api.get_by(['version'], 'firmwares', args.firmware)
            updates['target_firmware'] = fw['resource_uri']
        self.api.put('groups', group['id'], updates)

    def delete_cmd(self, args):
        """ Delete one or more groups """
        for ident in args.ident:
            group = self.api.get_by_id_or_name('groups', ident)
            if not args.force and \
               not base.confirm('Delete group: %s' % group['name'],
                                exit=False):
                continue
            self.api.delete('groups', group['id'])

    def move_cmd(self, args):
        """ Move group to a different account """
        group = self.api.get_by_id_or_name('groups', args.ident)
        account = self.api.get_by_id_or_name('accounts', args.new_account)
        self.api.put('groups', group['id'],
                     {"account": account['resource_uri']})

    def search_cmd(self, args):
        """ Search for groups """
        search = args.SEARCH_CRITERIA
        fields = ['name', ('firmware', 'target_firmware.version'),
                  ('product', 'product.name'), ('account', 'account.name')]
        results = list(self.api.search('groups', fields, search,
                                       expand=self.expands))
        if not results:
            raise SystemExit("No Results For: %s" % ' '.join(search))
        self.show_cmd(args, groups=results)

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

    def printer(self, group):
        fn = self.verbose_printer if self.verbose else self.terse_printer
        fn(group)

    def verbose_printer(group):
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

command_classes = [Groups]
