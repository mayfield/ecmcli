"""
Manage ECM Accounts.
"""

from . import base


class Formatter(object):

    def setup_args(self, parser):
        parser.add_argument('-v', '--verbose', action='store_true')
        super().setup_args(parser)

    def prerun(self, args):
        self.formatter = self.verbose_formatter if args.verbose else \
                         self.terse_formatter
        super().prerun(args)

    def terse_formatter(self, account):
        return '%(name)s (id:%(id)s)' % account

    def verbose_formatter(self, account):
        count = dict.fromkeys(['routers', 'groups', 'user_profiles',
                               'subaccounts'], 0)
        for x in count:
            n = self.api.get(urn=account[x], count='id')[0]['id_count']
            account['%s_count' % x] = n
        return '%(name)s (id:%(id)s, routers:%(routers_count)d ' \
               'groups:%(groups_count)d, users:%(user_profiles_count)d, ' \
               'subaccounts:%(subaccounts_count)d)' % account


class Show(Formatter, base.Command):
    """ Show accounts """

    name = 'show'

    def setup_args(self, parser):
        parser.add_argument('ident', metavar='ACCOUNT_ID_OR_NAME', nargs='?')
        super().setup_args(parser)

    def run(self, args):
        if args.ident:
            account = self.api.get_by_id_or_name('accounts', args.ident)
            print(self.formatter(account))
        else:
            return self.show_tree()

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


class Create(base.Command):
    """ Create account """

    name = 'create'

    def setup_args(self, parser):
        parser.add_argument('-p', '--parent',
                            metavar="PARENT_ACCOUNT_ID_OR_NAME")
        parser.add_argument('name', metavar='NAME')

    def run(self, args):
        new_account = {
            "name": args.name
        }
        if args.parent:
            account = self.api.get_by_id_or_name('accounts', args.parent)
            if not account:
                raise SystemExit("Account not found: %s" % args.parent)
            new_account['account'] = account['resource_uri']
        self.api.post('accounts', new_account)


class Delete(base.Command):
    """ Delete an account """

    name = 'delete'

    def setup_args(self, parser):
        parser.add_argument('ident', metavar='ACCOUNT_ID_OR_NAME')
        parser.add_argument('-f', '--force', action='store_true')

    def run(self, args):
        account = self.api.get_by_id_or_name('accounts', args.ident)
        if not args.force:
            base.confirm('Confirm account delete: %s (%s)' % (account['name'],
                         account['id']))
        self.api.delete('accounts', account['id'])


class Move(base.Command):
    """ Move account to new parent account """

    name = 'move'

    def setup_args(self, parser):
        parser.add_argument('ident', metavar='ACCOUNT_ID_OR_NAME')
        parser.add_argument('new_parent', metavar='NEW_PARENT_ID_OR_NAME')

    def run(self, args):
        account = self.api.get_by_id_or_name('accounts', args.ident)
        new_parent = self.api.get_by_id_or_name('accounts', args.new_parent)
        self.api.put('accounts', account['id'],
                     {"account": new_parent['resource_uri']})


class Rename(base.Command):
    """ Rename an account """

    name = 'rename'

    def setup_args(self, parser):
        parser.add_argument('ident', metavar='ACCOUNT_ID_OR_NAME')
        parser.add_argument('new_name', metavar='NEW_NAME')

    def run(self, args):
        account = self.api.get_by_id_or_name('accounts', args.ident)
        self.api.put('accounts', account['id'], {"name": args.new_name})


class Search(Formatter, base.Command):
    """ Search for account(s) """

    name = 'search'

    def setup_args(self, parser):
        parser.add_argument('search', metavar='SEARCH_CRITERIA', nargs='+')
        super().setup_args(parser)

    def run(self, args):
        results = list(self.api.search('accounts', ['name'], args.search))
        if not results:
            raise SystemExit("No results for: %s" % ' '.join(args.search))
        for x in results:
            print(self.formatter(x))


class Accounts(base.Command):
    """ Manage ECM Accounts. """

    name = 'accounts'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(Show, default=True)
        self.add_subcommand(Create)
        self.add_subcommand(Delete)
        self.add_subcommand(Move)
        self.add_subcommand(Rename)
        self.add_subcommand(Search)

command_classes = [Accounts]
