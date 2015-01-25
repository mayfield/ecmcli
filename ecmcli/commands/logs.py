"""
Download Device Logs from ECM.
"""

import argparse
import collections
import html
from syndicate import data as syndata

FORMAT = '%(timestamp)s [%(mac)s] [%(levelname)8s] [%(source)18s] %(message)s'

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--clear', action='store_true', help="Clear logs")

# NOTE: ECM only can only filter by one level.
parser.add_argument('-l', '--level', help="Log level to " \
                    "include (debug, info, warning, error and/or critical)")


def command(api, args):
    filters = {"id__in": ','.join(map(str, args.routers))} \
              if args.routers else {}
    routers = api.get_pager('routers', fields='id,mac,name', **filters)
    router_ids = collections.OrderedDict((x['id'], x) for x in routers)
    for rid, rinfo in router_ids.items():
        rinfo['display_name'] = '%s (%s) %s' % (rinfo['name'], rid,
                                rinfo['mac'])
    if args.clear:
        clear(api, args, router_ids)
    else:
        view(api, args, router_ids)


def clear(api, args, router_ids):
    for rid, rinfo in router_ids.items():
        print("Clearing logs for: %s" % rinfo['display_name'])
        api.delete('logs', rid)


def view(api, args, router_ids):
    filters = {}
    if args.level:
        filters['levelname'] = args.level.upper()
    for rid, rinfo in router_ids.items():
        print("Logs for: %s" % rinfo['display_name'])
        for x in api.get_pager('logs', rid, **filters):
            x['message'] = html.unescape(x['message'])
            x['mac'] = rinfo['mac']
            print(FORMAT % x)
