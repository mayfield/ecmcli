"""
List ECM Accounts.
"""

import argparse

parser = argparse.ArgumentParser(add_help=False)
commands = parser.add_subparsers(dest='cmd')
show_parser = commands.add_parser('show', help='Show accounts (DEFAULT)')
create_parser = commands.add_parser('create', help='Create account')
delete_parser = commands.add_parser('delete', help='Delete account')
move_parser = commands.add_parser('move', help='Move account to new parent '
                                  'account')
rename_parser = commands.add_parser('rename', help='Rename account')
search_parser = commands.add_parser('search', help='Search for account(s)')

show_parser.add_argument('ACCOUNT_ID_OR_NAME', nargs='?')
show_parser.add_argument('-v', '--verbose', action='store_true')

create_parser.add_argument('-p', '--parent', metavar="ACCOUNT_ID_OR_NAME")
create_parser.add_argument('NAME')

delete_parser.add_argument('ACCOUNT_ID_OR_NAME')
delete_parser.add_argument('-f', '--force')

move_parser.add_argument('ACCOUNT_ID_OR_NAME')
move_parser.add_argument('NEW_PARENT_ID_OR_NAME')
move_parser.add_argument('-f', '--force')

rename_parser.add_argument('ACCOUNT_ID_OR_NAME')
rename_parser.add_argument('NEW_NAME')

search_parser.add_argument('SEARCH_CRITERIA', nargs='+')
search_parser.add_argument('-v', '--verbose', action='store_true')


def confirm(msg):
    if input('%s (type "yes" to confirm): ' % msg) != 'yes':
        print("Aborted")
        exit(1)


def command(api, args):
    if not args.cmd:
        args.cmd = 'show'
        args.verbose = False
        args.ACCOUNT_ID_OR_NAME = None
    cmd = globals()['%s_cmd' % args.cmd]
    cmd(api, args)


def show_cmd(api, args):
    if args.ACCOUNT_ID_OR_NAME:
        account = api.get_by_id_or_name('accounts', args.ACCOUNT_ID_OR_NAME)
        print(verbose_formatter(api, account))
    else:
        return show_tree(api, args)


def show_tree(api, args):
    """ Huge page size for accounts costs nearly nothing, but api calls are
    extremely expensive.  The fastest and best way to get accounts and
    their descendants is to get massive pages from the root level, which
    already include descendants;  Build our own tree and do account level
    filtering client-side.  This theory is proven as of ECM 7-18-2015. """
    if api.account:
        root_id = api.account
        api.account = None
    else:
        root_id = None
    accounts_pager = api.get_pager('accounts', page_size=10000)
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
    _verbose_formatter = lambda x: verbose_formatter(api, x)
    formatter = _verbose_formatter if args.verbose else terse_formatter
    if root_ref == root:
        root_ref = root['children']
    else:
        root_ref = [root_ref]
    account_tree(root_ref, formatter)


def verbose_formatter(api, account):
    count = dict.fromkeys(['routers', 'groups', 'user_profiles', 'subaccounts'], 0)
    for x in count:
        n = api.get(urn=account[x], count='id')[0]['id_count']
        account['%s_count' % x] = n
    return '%(name)s (id:%(id)s, routers:%(routers_count)d ' \
           'groups:%(groups_count)d, users:%(user_profiles_count)d, ' \
           'subaccounts:%(subaccounts_count)d)' % account


def terse_formatter(account):
    return '%(name)s (id:%(id)s)' % account


def account_tree(accounts, formatter, prefix=None):
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
        print(''.join(line) + formatter(x))
        if x.get('children'):
            if prefix is not None:
                line[-1] = '    ' if end == i else '│   '
            account_tree(x['children'], formatter, prefix=''.join(line))


def create_cmd(api, args):
    new_account = {
        "name": args.NAME
    }
    if args.parent:
        account = api.get_by_id_or_name('accounts', args.parent)
        if not account:
            print("Account Not Found:", id_or_name)
            exit(1)
        new_account['account'] = account['resource_uri']
    api.post('accounts', new_account)


def delete_cmd(api, args):
    account = api.get_by_id_or_name('accounts', args.ACCOUNT_ID_OR_NAME)
    if not args.force:
        detail = verbose_formatter(api, account)
        confirm('Confirm account delete: %s' % detail)
    api.delete('accounts', account['id'])


def move_cmd(api, args):
    account = api.get_by_id_or_name('accounts', args.ACCOUNT_ID_OR_NAME)
    new_parent = api.get_by_id_or_name('accounts', args.NEW_PARENT_ID_OR_NAME)
    api.put('accounts', account['id'], {"account": new_parent['resource_uri']})


def rename_cmd(api, args):
    account = api.get_by_id_or_name('accounts', args.ACCOUNT_ID_OR_NAME)
    api.put('accounts', account['id'], {"name": args.NEW_NAME})


def search_cmd(api, args):
    results = list(api.search('accounts', ['name'], args.SEARCH_CRITERIA))
    if not results:
        print("No Results For:", *args.SEARCH_CRITERIA)
        exit(1)
    _verbose_formatter = lambda x: verbose_formatter(api, x)
    formatter = _verbose_formatter if args.verbose else terse_formatter
    for x in results:
        print(formatter(x))
