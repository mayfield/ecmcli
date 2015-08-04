"""
Manage ECM Accounts.
"""

from . import base


class Show(base.Command):
    """ Show accounts """

    name = 'show'

    def setup_args(self, parser):
        parser.add_argument('ident', metavar='ACCOUNT_ID_OR_NAME', nargs='?')
        parser.add_argument('-v', '--verbose', action='store_true')

    def run(self, args):
        if args.ident:
            account = self.api.get_by_id_or_name('accounts', args.ident)
            print(self.formatter(account))
        else:
            return self.show_tree()

    def formatter(self, account):
        formatter = self.verbose_formatter if self.verbose else \
                    self.terse_formatter
        return formatter(account)

    def show_tree(self):
        """ Huge page size for accounts costs nearly nothing, but api calls
        are extremely expensive.  The fastest and best way to get accounts and
        their descendants is to get massive pages from the root level, which
        already include descendants;  Build our own tree and do account level
        filtering client-side.  This theory is proven as of ECM 7-18-2015. """
        if self.api.account:
            root_id = self.api.account
            self.api.account = None
        else:
            root_id = None
        accounts_pager = self.api.get_pager('accounts', page_size=10000)
        accounts = dict((x['resource_uri'], x) for x in accounts_pager)
        root_ref = root = {
            "children": []
        }
        pruned = accounts.copy()
        for uri, x in accounts.items():
            parent = pruned.get(x['account'], root)
            if root_id is not None and x['id'] == str(root_id):
                root_ref = x
            if 'children' not in parent:
                parent['children'] = []
            parent['children'].append(x)
        if root_ref == root:
            root_ref = root['children']
        else:
            root_ref = [root_ref]
        self.account_tree(root_ref)

    def verbose_formatter(self, account):
        count = dict.fromkeys(['routers', 'groups', 'user_profiles',
                               'subaccounts'], 0)
        for x in count:
            n = self.api.get(urn=account[x], count='id')[0]['id_count']
            account['%s_count' % x] = n
        return '%(name)s (id:%(id)s, routers:%(routers_count)d ' \
               'groups:%(groups_count)d, users:%(user_profiles_count)d, ' \
               'subaccounts:%(subaccounts_count)d)' % account

    def terse_formatter(self, account):
        return '%(name)s (id:%(id)s)' % account

    def account_tree(self, accounts, prefix=None):
        end = len(accounts) - 1
        for i, x in enumerate(sorted(accounts, key=lambda x: x['name'])):
            if prefix is not None:
                line = [prefix]
                if end == i:
                    line.append('└── ')
                elif i == 0:
                    line.append('├── ')
                else:
                    line.append('├── ')
            else:
                line = ['']
            print(''.join(line) + self.formatter(x))
            if x.get('children'):
                if prefix is not None:
                    line[-1] = '    ' if end == i else '│   '
                self.account_tree(x['children'], prefix=''.join(line))


class Accounts(base.Command):
    """ Manage ECM Accounts. """

    name = 'accounts'

    def setup_args(self, parser):
        #s = parser.add_subcommand('show', self.show_cmd, default=True)
        #s.add_argument('ident', metavar='ACCOUNT_ID_OR_NAME', nargs='?')
        #s.add_argument('-v', '--verbose', action='store_true')
        parser.add_subcommand(Show(), default=True)

        s = parser.add_subcommand('create', self.create_cmd)
        s.add_argument('-p', '--parent', metavar="PARENT_ACCOUNT_ID_OR_NAME")
        s.add_argument('name', metavar='NAME')

        s = parser.add_subcommand('delete', self.delete_cmd)
        s.add_argument('ident', metavar='ACCOUNT_ID_OR_NAME')
        s.add_argument('-f', '--force', action='store_true')

        s = parser.add_subcommand('move', self.move_cmd)
        s.add_argument('ident', metavar='ACCOUNT_ID_OR_NAME')
        s.add_argument('new_parent', metavar='NEW_PARENT_ID_OR_NAME')

        s = parser.add_subcommand('rename', self.rename_cmd)
        s.add_argument('ident', metavar='ACCOUNT_ID_OR_NAME')
        s.add_argument('new_name', metavar='NEW_NAME')

        s = parser.add_subcommand('search', self.search_cmd)
        s.add_argument('search', metavar='SEARCH_CRITERIA', nargs='+')
        s.add_argument('-v', '--verbose', action='store_true')

    def prerun(self, args):
        self.verbose = getattr(args, 'verbose', False)

    def show_cmd(self, args):
        """ Show accounts """
        if args.ident:
            account = self.api.get_by_id_or_name('accounts', args.ident)
            print(self.formatter(account))
        else:
            return self.show_tree()

    def formatter(self, account):
        formatter = self.verbose_formatter if self.verbose else \
                    self.terse_formatter
        return formatter(account)

    def show_tree(self):
        """ Huge page size for accounts costs nearly nothing, but api calls
        are extremely expensive.  The fastest and best way to get accounts and
        their descendants is to get massive pages from the root level, which
        already include descendants;  Build our own tree and do account level
        filtering client-side.  This theory is proven as of ECM 7-18-2015. """
        if self.api.account:
            root_id = self.api.account
            self.api.account = None
        else:
            root_id = None
        accounts_pager = self.api.get_pager('accounts', page_size=10000)
        accounts = dict((x['resource_uri'], x) for x in accounts_pager)
        root_ref = root = {
            "children": []
        }
        pruned = accounts.copy()
        for uri, x in accounts.items():
            parent = pruned.get(x['account'], root)
            if root_id is not None and x['id'] == str(root_id):
                root_ref = x
            if 'children' not in parent:
                parent['children'] = []
            parent['children'].append(x)
        if root_ref == root:
            root_ref = root['children']
        else:
            root_ref = [root_ref]
        self.account_tree(root_ref)

    def verbose_formatter(self, account):
        count = dict.fromkeys(['routers', 'groups', 'user_profiles',
                               'subaccounts'], 0)
        for x in count:
            n = self.api.get(urn=account[x], count='id')[0]['id_count']
            account['%s_count' % x] = n
        return '%(name)s (id:%(id)s, routers:%(routers_count)d ' \
               'groups:%(groups_count)d, users:%(user_profiles_count)d, ' \
               'subaccounts:%(subaccounts_count)d)' % account

    def terse_formatter(self, account):
        return '%(name)s (id:%(id)s)' % account

    def account_tree(self, accounts, prefix=None):
        end = len(accounts) - 1
        for i, x in enumerate(sorted(accounts, key=lambda x: x['name'])):
            if prefix is not None:
                line = [prefix]
                if end == i:
                    line.append('└── ')
                elif i == 0:
                    line.append('├── ')
                else:
                    line.append('├── ')
            else:
                line = ['']
            print(''.join(line) + self.formatter(x))
            if x.get('children'):
                if prefix is not None:
                    line[-1] = '    ' if end == i else '│   '
                self.account_tree(x['children'], prefix=''.join(line))

    def create_cmd(self, args):
        """ Create account """
        new_account = {
            "name": args.name
        }
        if args.parent:
            account = self.api.get_by_id_or_name('accounts', args.parent)
            if not account:
                raise SystemExit("Account not found: %s" % args.parent)
            new_account['account'] = account['resource_uri']
        self.api.post('accounts', new_account)

    def delete_cmd(self, args):
        """ Delete an account """
        account = self.api.get_by_id_or_name('accounts', args.ident)
        if not args.force:
            detail = self.verbose_formatter(account)
            base.confirm('Confirm account delete: %s' % detail)
        self.api.delete('accounts', account['id'])

    def move_cmd(self, args):
        """ Move account to new parent account """
        account = self.api.get_by_id_or_name('accounts', args.ident)
        new_parent = self.api.get_by_id_or_name('accounts', args.new_parent)
        self.api.put('accounts', account['id'],
                     {"account": new_parent['resource_uri']})

    def rename_cmd(self, args):
        """ Rename an account """
        account = self.api.get_by_id_or_name('accounts', args.ident)
        self.api.put('accounts', account['id'], {"name": args.new_name})

    def search_cmd(self, args):
        """ Search for account(s) """
        results = list(self.api.search('accounts', ['name'], args.search))
        if not results:
            raise SystemExit("No results for: %s" % ' '.join(args.search))
        for x in results:
            print(self.formatter(x))

command_classes = [Accounts]
