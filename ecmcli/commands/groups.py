"""
Manage ECM Groups.
"""

import argparse

parser = argparse.ArgumentParser(add_help=False)
commands = parser.add_subparsers(dest='cmd')
show_parser = commands.add_parser('show', help='Show groups (DEFAULT)')
create_parser = commands.add_parser('create', help='Create group')
delete_parser = commands.add_parser('delete', help='Delete group')
edit_parser = commands.add_parser('edit', help='Edit group attributes')
move_parser = commands.add_parser('move', help='Move group to new account')
search_parser = commands.add_parser('search', help='Search for group(s)')

create_parser.add_argument('--name')
create_parser.add_argument('--product')
create_parser.add_argument('--firmware')

edit_parser.add_argument('GROUP_ID_OR_NAME')
edit_parser.add_argument('--name')
edit_parser.add_argument('--product')
edit_parser.add_argument('--firmware')

move_parser.add_argument('GROUP_ID_OR_NAME')
move_parser.add_argument('NEW_ACCOUNT_ID_OR_NAME')

delete_parser.add_argument('GROUP_ID_OR_NAME', nargs='+')
delete_parser.add_argument('-f', '--force', action="store_true",
                           help="Do not prompt for confirmation")

show_parser.add_argument('GROUP_ID_OR_NAME', nargs='?')
show_parser.add_argument('-v', '--verbose', action='store_true',
                         help="Verbose output.")

search_parser.add_argument('SEARCH_CRITERIA', nargs='+')
search_parser.add_argument('-v', '--verbose', action='store_true',
                           help="Verbose output.")

EXPANDS = ','.join([
    'statistics',
    'product',
    'account',
    'target_firmware',
    'settings_bindings.setting',
    'configuration'
])


def completer(text, line, begin, end):
    return [x for x in commands.choices if x.startswith(text)]


def command(api, args):
    if not args.cmd:
        args.cmd = 'show'
        args.verbose = False
        args.GROUP_ID_OR_NAME = None
    cmd = globals()['%s_cmd' % args.cmd]
    cmd(api, args)


def show_cmd(api, args, groups=None):
    printer = verbose_printer if args.verbose else terse_printer
    if groups is None:
        id_or_name = args.GROUP_ID_OR_NAME
        if id_or_name:
            groups = [api.get_by_id_or_name('groups', id_or_name,
                                            expand=EXPANDS)]
        else:
            groups = api.get_pager('groups', expand=EXPANDS)
    if not args.verbose:
        printer(None, header=True)
    for x in groups:
        printer(bundle_group(x))


def create_cmd(api, args):
    name = args.name or input('Name: ')
    if not name:
        print("Name required")
        exit(1)

    product = args.product or input('Product: ')
    products = dict((x['name'], x) for x in api.get_pager('products'))
    if product not in products:
        if not product:
            print("Product required")
        else:
            print("Invalid product:", product)
        print("\nValid products...")
        for x in sorted(products):
            print("\t", x)
        exit(1)

    fw = args.firmware or input('Firmware: ')
    firmwares = dict((x['version'], x)
                     for x in api.get_pager('firmwares',
                                            product=products[product]['id']))
    if fw not in firmwares:
        if not fw:
            print("Firmware required")
        else:
            print("Invalid firmware:", fw)
        print("\nValid firmares...")
        for x in sorted(firmwares):
            print("\t", x)
        exit(1)

    group = api.post('groups', {
        "name": name,
        "product": products[product]['resource_uri'],
        "target_firmware": firmwares[fw]['resource_uri']
    })


def edit_cmd(api, args):
    group = api.get_by_id_or_name('groups', args.GROUP_ID_OR_NAME)
    updates = {}
    if args.name:
        updates['name'] = args.name
    if args.product:
        p = api.get_by_id_or_name('products', args.product)
        updates['product'] = p['resource_uri']
    if args.firmware:
        fw = api.get_by(['version'], 'firmwares', args.firmware)
        updates['target_firmware'] = fw['resource_uri']
    api.put('groups', group['id'], updates)


def delete_cmd(api, args):
    for username in args.USERNAME:
        user = get_user(api, username)
        if not args.force:
            confirm = input('Delete user: %s, id:%s (type "yes" to confirm): '
                            % (username, user['id']))
            if confirm != 'yes':
                print("Aborted")
                continue
        api.delete('users', user['id'])


def move_cmd(api, args):
    user = get_user(api, args.USERNAME)
    account = api.get_by_id_or_name('accounts', args.NEW_ACCOUNT_ID_OR_NAME)
    api.put('profiles', user['profile']['id'], {"account": account['resource_uri']})


def search_cmd(api, args):
    search = args.SEARCH_CRITERIA
    fields = ['name', ('firmware', 'target_firmware.version'),
              ('product', 'product.name'), ('account', 'account.name')]
    results = list(api.search('groups', fields, search, expand=EXPANDS))
    if not results:
        print("No Results For:", *search)
        exit(1)
    show_cmd(api, args, groups=results)


def bundle_group(group):
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


def verbose_printer(group):
    print('ID:          ', group['id'])
    print('Name:        ', group['name'])
    print('Online:      ', group['online'])
    print('Total:       ', group['total'])
    print('Target:      ', group['target'])
    print('Account:     ', group['account']['name'])
    print('Suspended:   ', group['statistics']['suspended_count'])
    print('Syncronized: ', group['statistics']['synched_count'])
    if group['settings']:
        print('Settings...')
        for x in sorted(group['settings'].items()):
            print('  %-30s %s' % x)
    print()


def terse_printer(group, header=False):
    if header:
        info = {
            "name": 'NAME (ID)',
            "account": 'ACCOUNT',
            "target": 'TARGET',
            "online": 'ONLINE'
        }
    else:
        stats = group['statistics']
        info = {
            "name": '%s (%s)' % (group['name'], group['id']),
            "account": group['account']['name'],
            "target": group['target'],
            "online": '%s/%s' % (group['online'], group['total'])
        }
    print('%(name)-30s %(account)-16s %(target)-16s %(online)-5s' % info)
