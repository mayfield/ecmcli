"""
List ECM Routers.
"""

import argparse
import functools
import html
import humanize

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('-v', '--verbose', action='store_true',
                    help="Verbose output.")



def command(api, args, routers=None):
    printer = verbose_printer if args.verbose else terse_printer

    printer(routers.values(), api=api)


@functools.lru_cache(maxsize=2^16)
def res_fetch(api, urn):
    """ Return a remote ECM resource by urn. (NOTE: MEMOIZING) """
    return api.get(urn=urn)


def since(dt):
    """ Return humanized time since for an absolute datetime. """
    since = dt.now(tz=dt.tzinfo) - dt
    return humanize.naturaltime(since)[:-4]


def verbose_printer(routers, api=None):
    fields = (
        ('account_info', 'Account'),
        ('asset_id', 'Asset ID'),
        ('config_status', 'Config Status'),
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
            return x[subres] and res_fetch(api, x[subres])

        def fetch_sub_name_and_id(subres):
            sub = fetch_sub(subres)
            return sub and '%s (%s)' % (html.unescape(sub['name']), sub['id'])

        if not first:
            print()
        print('%s (%s):' % (html.unescape(x['name']), x['id']))
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
            field = html.unescape(str(x[key]))
            print(fmt % (label, field))
        first = False


def terse_printer(routers, api=None):
    fmt = '%(name)-20s %(id)6s %(ip_address)16s %(state)8s (%(since)s)'
    for x in routers:
        x['name'] = html.unescape(x['name'])
        x['since'] = since(x['state_ts'])
        print(fmt % x)
