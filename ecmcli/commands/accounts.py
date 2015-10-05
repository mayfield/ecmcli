"""
Manage ECM Accounts.
"""

from . import base
from shellish import layout


class Formatter(object):

    terse_table_fields = (
        (lambda x: x['name'], 'Name'),
        (lambda x: x['id'], 'ID'),
        (lambda x: len(x['groups']), 'Groups'),
        (lambda x: x['customer']['customer_name'], 'Customer'),
        (lambda x: x['customer']['contact_name'], 'Contact')
    )

    verbose_table_fields = (
        (lambda x: x['name'], 'Name'),
        (lambda x: x['id'], 'ID'),
        (lambda x: len(x['groups']), 'Groups'),
        (lambda x: x['routers_count'], 'Routers'),
        (lambda x: x['user_profiles_count'], 'Users'),
        (lambda x: x['subaccounts_count'], 'Subaccounts'),
        (lambda x: x['customer']['customer_name'], 'Customer'),
        (lambda x: x['customer']['contact_name'], 'Contact')
    )

    expands = [
        'groups',
        'customer',
    ]

    def setup_args(self, parser):
        self.add_argument('-v', '--verbose', action='store_true')
        super().setup_args(parser)

    def prerun(self, args):
        self.verbose = args.verbose
        if args.verbose:
            self.formatter = self.verbose_formatter
            self.table_fields = self.verbose_table_fields
        else:
            self.formatter = self.terse_formatter
            self.table_fields = self.terse_table_fields
        self.table = layout.Table(headers=[x[1] for x in self.table_fields],
                                  accessors=[self.safe_get(x[0], '')
                                             for x in self.table_fields])
        super().prerun(args)

    def safe_get(self, func, default=None):
        def fn(x):
            try:
                return func(x)
            except:
                return default
        return fn

    def bundle(self, account):
        if self.verbose:
            counts = ['routers', 'user_profiles', 'subaccounts']
            for x in counts:
                n = self.api.get(urn=account[x], count='id')[0]['id_count']
                account['%s_count' % x] = n
        account['groups_count'] = len(account['groups'])
        return account

    def terse_formatter(self, account):
        return '%(name)s (id:%(id)s)' % account

    def verbose_formatter(self, account):
        return '%(name)s (id:%(id)s, routers:%(routers_count)d ' \
               'groups:%(groups_count)d, users:%(user_profiles_count)d, ' \
               'subaccounts:%(subaccounts_count)d)' % account


class Tree(Formatter, base.ECMCommand):
    """ Show account Tree """

    name = 'tree'

    def setup_args(self, parser):
        self.add_account_argument(nargs='?')
        super().setup_args(parser)

    def run(self, args):
        if args.ident:
            root_id = self.api.get_by_id_or_name('accounts', args.ident)['id']
        else:
            root_id = None
        self.show_tree(root_id)

    def show_tree(self, root_id):
        """ Huge page size for accounts costs nearly nothing, but api calls
        are extremely expensive.  The fastest and best way to get accounts and
        their descendants is to get massive pages from the root level, which
        already include descendants;  Build our own tree and do account level
        filtering client-side.  This theory is proven as of ECM 7-18-2015. """
        accounts_pager = self.api.get_pager('accounts', page_size=10000)
        accounts = dict((x['resource_uri'], x) for x in accounts_pager)
        root_ref = root = {"node": layout.TreeNode('root')}
        for uri, x in accounts.items():
            parent = accounts.get(x['account'], root)
            if 'node' not in parent:
                parent['node'] = layout.TreeNode(parent)
            if 'node' not in x:
                x['node'] = layout.TreeNode(x)
            parent['node'].children.append(x['node'])
            if root_id is not None and x['id'] == root_id:
                root_ref = x
        if root_ref == root:
            root_ref = root['node'].children
        else:
            root_ref = [root_ref['node']]
        formatter = lambda x: self.formatter(self.bundle(x.value))
        t = layout.Tree(formatter=formatter, sort_key=lambda x: x.value['id'])
        for x in t.render(root_ref):
            print(x)


class Show(Formatter, base.ECMCommand):
    """ Show account info. """

    name = 'show'

    def setup_args(self, parser):
        self.add_account_argument('idents', nargs='*')
        super().setup_args(parser)

    def run(self, args):
        expands = ','.join(self.expands)
        if args.idents:
            accounts = [self.api.get_by_id_or_name('accounts', x,
                                                   expand=expands)
                        for x in args.idents]
        else:
            accounts = self.api.get_pager('accounts', expand=expands)
        self.table.print(map(self.bundle, accounts))


class Create(base.ECMCommand):
    """ Create account """

    name = 'create'

    def setup_args(self, parser):
        self.add_account_argument('-p', '--parent',
                                  metavar="PARENT_ACCOUNT_ID_OR_NAME")
        self.add_argument('name', metavar='NAME')

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


class Delete(base.ECMCommand):
    """ Delete an account """

    name = 'delete'

    def setup_args(self, parser):
        self.add_account_argument()
        self.add_argument('-f', '--force', action='store_true')

    def run(self, args):
        account = self.api.get_by_id_or_name('accounts', args.ident)
        if not args.force:
            base.confirm('Confirm account delete: %s (%s)' % (account['name'],
                         account['id']))
        self.api.delete('accounts', account['id'])


class Move(base.ECMCommand):
    """ Move account to new parent account """

    name = 'move'

    def setup_args(self, parser):
        self.add_account_argument()
        self.add_account_argument('new_parent',
                                  metavar='NEW_PARENT_ID_OR_NAME')

    def run(self, args):
        account = self.api.get_by_id_or_name('accounts', args.ident)
        new_parent = self.api.get_by_id_or_name('accounts', args.new_parent)
        self.api.put('accounts', account['id'],
                     {"account": new_parent['resource_uri']})


class Rename(base.ECMCommand):
    """ Rename an account """

    name = 'rename'

    def setup_args(self, parser):
        self.add_account_argument()
        self.add_argument('new_name', metavar='NEW_NAME')

    def run(self, args):
        account = self.api.get_by_id_or_name('accounts', args.ident)
        self.api.put('accounts', account['id'], {"name": args.new_name})


class Search(Formatter, base.ECMCommand):
    """ Search for account(s) """

    name = 'search'

    def setup_args(self, parser):
        expands = ','.join(self.expands)
        searcher = self.make_searcher('accounts', ['name'], expand=expands)
        self.lookup = searcher.lookup
        self.add_search_argument(searcher)
        super().setup_args(parser)

    def run(self, args):
        results = list(self.lookup(args.search))
        if not results:
            raise SystemExit("No results for: %s" % ' '.join(args.search))
        self.table.print(map(self.bundle, results))


class Accounts(base.ECMCommand):
    """ Manage ECM Accounts. """

    name = 'accounts'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(Show, default=True)
        self.add_subcommand(Tree)
        self.add_subcommand(Create)
        self.add_subcommand(Delete)
        self.add_subcommand(Move)
        self.add_subcommand(Rename)
        self.add_subcommand(Search)

command_classes = [Accounts]
