"""
Manage ECM Routers.
"""

import argparse
import functools
import humanize

parser = argparse.ArgumentParser(add_help=False)
commands = parser.add_subparsers(dest='cmd')

show_parser = commands.add_parser('show', help='Show routers (DEFAULT)')
delete_parser = commands.add_parser('delete', help='Delete a router')
edit_parser = commands.add_parser('edit', help='Edit router attributes')
move_parser = commands.add_parser('move', help='Move a router into a different '
                               'account')
groupassign_parser = commands.add_parser('groupassign', help='Assign router to '
                                      'a group')
groupunassign_parser = commands.add_parser('groupunassign', help='Unassign '
                                        'router from a group')
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

groupunassign_parser.add_argument('ROUTER_ID_OR_NAME')

delete_parser.add_argument('ROUTER_ID_OR_NAME')
delete_parser.add_argument('-f', '--force', action="store_true",
                        help="Do not prompt for confirmation")

show_parser.add_argument('ROUTER_ID_OR_NAME', nargs='?')
show_parser.add_argument('-v', '--verbose', action='store_true',
                      help="Verbose output.")

search_parser.add_argument('SEARCH_CRITERIA', nargs='+')
search_parser.add_argument('-v', '--verbose', action='store_true',
                        help="Verbose output.")


def command(api, args, routers=None):
    if not args.cmd:
        args.cmd = 'show'
        args.verbose = False
        args.ROUTER_ID_OR_NAME = None
    cmd = globals()['%s_cmd' % args.cmd]
    cmd(api, args, routers=routers)


def show_cmd(api, args, routers=None):
    if args.ROUTER_ID_OR_NAME:
        routers = [api.get_by_id_or_name('routers', args.ROUTER_ID_OR_NAME)]
    printer = verbose_printer if args.verbose else terse_printer
    printer(routers, api=api)


@functools.lru_cache(maxsize=2^16)
def res_fetch(api, urn):
    """ Return a remote ECM resource by urn. (NOTE: MEMOIZING) """
    return api.get(urn=urn)


def since(dt):
    """ Return humanized time since for an absolute datetime. """
    if dt is None:
        return ''
    since = dt.now(tz=dt.tzinfo) - dt
    return humanize.naturaltime(since)[:-4]


def verbose_printer(routers, api=None):
    fields = (
        ('account_info', 'Account'),
        ('asset_id', 'Asset ID'),
        ('config_status', 'Config Status'),
        ('custom1', 'Custom 1'),
        ('custom2', 'Custom 2'),
        ('desc', 'Description'),
        ('entitlements', 'Entitlements'),
        ('firmware_info', 'Firmware'),
        ('group_info', 'Group'),
        ('id', 'ID'),
        ('ip_address', 'IP Address'),
        ('joined', 'Joined'),
        ('locality', 'Locality'),
        ('location_info', 'Location'),
        ('mac', 'MAC'),
        ('product_info', 'Product'),
        ('quarantined', 'Quarantined'),
        ('serial_number', 'Serial Number'),
        ('since', 'Connection Time'),
        ('state', 'Connection'),
    )
    location_url = 'https://maps.google.com/maps?' \
                   'q=loc:%(latitude)f+%(longitude)f'
    offset = max(map(len, (x[1] for x in fields))) + 2
    fmt = '\t%%-%ds: %%s' % offset
    first = True
    for x in routers:

        def fetch_sub(subres):
            return x.get(subres) and res_fetch(api, x[subres])

        def fetch_sub_name_and_id(subres):
            sub = fetch_sub(subres)
            return sub and '%s (%s)' % (sub['name'], sub['id'])

        if not first:
            print()
        print('%s (%s):' % (x['name'], x['id']))
        x['since'] = since(x['state_ts'])
        x['joined'] = since(x['create_ts']) + ' ago'
        x['account_info'] = fetch_sub_name_and_id('account')
        x['group_info'] = fetch_sub_name_and_id('group')
        x['product_info'] = fetch_sub_name_and_id('product')
        fw = fetch_sub('actual_firmware')
        x['firmware_info'] = fw['version'] if fw else 'Unsupported'
        loc = fetch_sub('last_known_location')
        x['location_info'] = loc and location_url % loc
        ents = fetch_sub('featurebindings')
        acc = lambda x: x['settings']['entitlement'] \
                         ['sf_entitlements'][0]['name']
        x['entitlements'] = ', '.join(map(acc, ents)) if ents else 'None'
        for key, label in fields:
            print(fmt % (label, x[key]))
        first = False


def terse_printer(routers, api=None):
    fmt = '%(name)-20s %(id)6s %(ip_address)16s %(state)8s (%(since)s)'
    for x in routers:
        x['since'] = x['state_ts'] and since(x['state_ts'])
        print(fmt % x)


def groupassign_cmd(api, args, routers=None):
    pass


def groupunassign_cmd(api, args, routers=None):
    pass


def edit_cmd(api, args, routers=None):
    router = api.get_by_id_or_name('routers', args.ROUTER_ID_OR_NAME)
    value = {}
    fields = ['name', 'desc', 'asset_id', 'custom1', 'custom2']
    for x in fields:
        v = getattr(args, x)
        if v is not None:
            value[x] = v
    api.put('routers', router['id'], value)
