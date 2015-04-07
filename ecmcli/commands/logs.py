"""
Download Device Logs from ECM.
"""

import argparse

FORMAT = '%(timestamp)s [%(mac)s] [%(levelname)8s] [%(source)18s] %(message)s'

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--clear', action='store_true', help="Clear logs")

# NOTE: ECM only can only filter by one level.
parser.add_argument('-l', '--level', help="Log level to "
                    "include (debug, info, warning, error and/or critical)")


def command(api, args, routers=None):
    if args.clear:
        clear(api, args, routers)
    else:
        view(api, args, routers)


def clear(api, args, routers):
    for rinfo in routers:
        print("Clearing logs for: %s (%s)" % (rinfo['name'], rinfo['id']))
        api.delete('logs', rinfo['id'])


def view(api, args, routers):
    filters = {}
    if args.level:
        filters['levelname'] = args.level.upper()
    for rinfo in routers:
        print("Logs for: %s (%s)" % (rinfo['name'], rinfo['id']))
        for x in api.get_pager('logs', rinfo['id'], **filters):
            x['mac'] = rinfo['mac']
            print(FORMAT % x)
