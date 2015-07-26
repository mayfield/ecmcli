"""
Manage ECM Routers.
"""

import argparse
import humanize

parser = argparse.ArgumentParser(add_help=False)
commands = parser.add_subparsers(dest='cmd')

show_parser = commands.add_parser('show', help='Show routers (DEFAULT)')
delete_parser = commands.add_parser('delete', help='Delete a router')
edit_parser = commands.add_parser('edit', help='Edit router attributes')
move_parser = commands.add_parser('move', help='Move a router into a different '
                               'account')
groupassign_parser = commands.add_parser('groupassign', help='Assign router to '
                                      'a (new) group')
groupunassign_parser = commands.add_parser('groupunassign', help='Unassign '
                                        'router from its group')
search_parser = commands.add_parser('search', help='Search for router(s)')

edit_parser.add_argument('ROUTER_ID_OR_NAME')
edit_parser.add_argument('--name')
edit_parser.add_argument('--desc')
edit_parser.add_argument('--asset_id')
edit_parser.add_argument('--custom1')
edit_parser.add_argument('--custom2')

move_parser.add_argument('ROUTER_ID_OR_NAME')
move_parser.add_argument('NEW_ACCOUNT_ID_OR_NAME')

groupassign_parser.add_argument('ROUTER_ID_OR_NAME')
groupassign_parser.add_argument('NEW_GROUP_ID_OR_NAME')
groupassign_parser.add_argument('-f', '--force', action='store_true',
                                help="Do not prompt for confirmation")

groupunassign_parser.add_argument('ROUTER_ID_OR_NAME')

delete_parser.add_argument('ROUTER_ID_OR_NAME', nargs='+')
delete_parser.add_argument('-f', '--force', action='store_true',
                           help="Do not prompt for confirmation")

show_parser.add_argument('ROUTER_ID_OR_NAME', nargs='?')
show_parser.add_argument('-v', '--verbose', action='store_true',
                         help="Verbose output.")

search_parser.add_argument('SEARCH_CRITERIA', nargs='+')
search_parser.add_argument('-v', '--verbose', action='store_true',
                           help="Verbose output.")

EXPANDS = [
    'account',
    'group'
]
VERBOSE_EXPANDS = [
    'group',
    'product',
    'actual_firmware',
    'last_known_location',
    'featurebindings'
]

def command(api, args):
    if not args.cmd:
        args.cmd = 'show'
        args.verbose = False
        args.ROUTER_ID_OR_NAME = None
    cmd = globals()['%s_cmd' % args.cmd]
    cmd(api, args)


def show_cmd(api, args, routers=None):
    if routers is None:
        expands = EXPANDS + (VERBOSE_EXPANDS if args.verbose else [])
        if args.ROUTER_ID_OR_NAME:
            routers = [api.get_by_id_or_name('routers', args.ROUTER_ID_OR_NAME,
                       expand=','.join(expands))]
        else:
            routers = api.get_pager('routers', expand=','.join(expands))
    printer = verbose_printer if args.verbose else terse_printer
    printer(routers, api=api)


def since(dt):
    """ Return humanized time since for an absolute datetime. """
    if dt is None:
        return ''
    since = dt.now(tz=dt.tzinfo) - dt
    return humanize.naturaltime(since)[:-4]


def verbose_printer(routers, api=None):
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


def terse_printer(routers, api=None):
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


def groupassign_cmd(api, args):
    router = api.get_by_id_or_name('routers', args.ROUTER_ID_OR_NAME,
                                   expand='group')
    group = api.get_by_id_or_name('groups', args.NEW_GROUP_ID_OR_NAME)
    if router['group'] and not args.force:
        confirm = input('Replace router group: %s with %s (type "yes" to '
                        'confirm): ' % (router['group']['name'],
                        group['name']))
        if confirm != 'yes':
            print("Aborted")
            exit(1)
    api.put('routers', router['id'], {"group": group['resource_uri']})


def groupunassign_cmd(api, args):
    router = api.get_by_id_or_name('routers', args.ROUTER_ID_OR_NAME)
    api.put('routers', router['id'], {"group": None})


def edit_cmd(api, args):
    router = api.get_by_id_or_name('routers', args.ROUTER_ID_OR_NAME)
    value = {}
    fields = ['name', 'desc', 'asset_id', 'custom1', 'custom2']
    for x in fields:
        v = getattr(args, x)
        if v is not None:
            value[x] = v
    api.put('routers', router['id'], value)


def delete_cmd(api, args):
    for id_or_name in args.ROUTER_ID_OR_NAME:
        router = api.get_by_id_or_name('routers', id_or_name)
        if not args.force:
            confirm = input('Delete router: %s, id:%s (type "yes" to confirm): ' % (
                            router['name'], router['id']))
            if confirm != 'yes':
                print("Aborted")
                continue
        api.delete('routers', router['id'])


def search_cmd(api, args):
    search = args.SEARCH_CRITERIA
    fields = ['name', 'desc', 'mac', ('account', 'account.name'), 'asset_id',
              'custom1', 'custom2', ('group', 'group.name'),
              ('firmware', 'actual_firmware.version'), 'ip_address',
              ('product', 'product.name'), 'serial_number', 'state']
    expands = EXPANDS + (VERBOSE_EXPANDS if args.verbose else [])
    results = list(api.search('routers', fields, search,
                              expand=','.join(expands)))
    if not results:
        print("No Results For:", *search)
        exit(1)
    show_cmd(api, args, routers=results)



