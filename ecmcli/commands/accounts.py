"""
List ECM Accounts.
"""

import argparse

parser = argparse.ArgumentParser(add_help=False)
commands = parser.add_subparsers()
show_cmd = commands.add_parser('show')
create_cmd = commands.add_parser('create')
delete_cmd = commands.add_parser('delete')
move_cmd = commands.add_parser('move')
rename_cmd = commands.add_parser('rename')
search_cmd = commands.add_parser('search')

show_cmd.add_argument('ID_OR_NAME', nargs='?')
show_cmd.add_argument('-v', '--verbose', action='store_true')

create_cmd.add_argument('-p', '--parent', metavar="ID_OR_NAME")
create_cmd.add_argument('NAME')

delete_cmd.add_argument('ID_OR_NAME')
delete_cmd.add_argument('-f', '--force')

move_cmd.add_argument('ID_OR_NAME')
move_cmd.add_argument('NEW_PARENT_ID_OR_NAME')
move_cmd.add_argument('-f', '--force')

rename_cmd.add_argument('ID_OR_NAME')
rename_cmd.add_argument('NEW_NAME')

search_cmd.add_argument('SEARCH_CRITERIA', nargs='+')
search_cmd.add_argument('-v', '--verbose', action='store_true')


def confirm(msg):
    if input('%s (type "yes" to confirm): ' % msg) != 'yes':
        print("Aborted")
        exit(1)


def command(api, args):
    if not hasattr(args, 'cmd'):
        raise ReferenceError('command argument required')
    args.cmd(api, args)


def show(api, args):
    if args.ID_OR_NAME:
        return show_detail(api, args.ID_OR_NAME)
    else:
        return show_tree(api, args)

show_cmd.set_defaults(cmd=show)


def show_detail(api, id_or_name):
    for x in api.get_pager('accounts'):
        print(fmt % x)


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


def create(api, args):
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

create_cmd.set_defaults(cmd=create)


def delete(api, args):
    account = api.get_by_id_or_name('accounts', args.ID_OR_NAME)
    if not args.force:
        detail = verbose_formatter(api, account)
        confirm('Confirm account delete: %s' % detail)
    api.delete('accounts', account['id'])

delete_cmd.set_defaults(cmd=delete)


def move(api, args):
    account = api.get_by_id_or_name('accounts', args.ID_OR_NAME)
    new_parent = api.get_by_id_or_name('accounts', args.NEW_PARENT_ID_OR_NAME)
    api.put('accounts', account['id'], {"account": new_parent['resource_uri']})

move_cmd.set_defaults(cmd=move)


def rename(api, args):
    account = api.get_by_id_or_name('accounts', args.ID_OR_NAME)
    api.put('accounts', account['id'], {"name": args.NEW_NAME})

rename_cmd.set_defaults(cmd=rename)


def search(api, args):
    criteria = ' '.join(args.SEARCH_CRITERIA)
    results = api.search('accounts', ['name'], criteria)
    _verbose_formatter = lambda x: verbose_formatter(api, x)
    formatter = _verbose_formatter if args.verbose else terse_formatter
    for x in results:
        print(formatter(x))

search_cmd.set_defaults(cmd=search)
