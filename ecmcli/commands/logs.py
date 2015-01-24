"""
Download Device Logs from ECM.
"""

import html
from syndicate import data as syndata

FORMAT = '%(timestamp)s [%(levelname)8s] [%(source)18s] [%(name)16s] ' \
         '[%(mac)s] %(message)s'


def command(api, args):
    filters = {"ids__in": ','.join(args.routers)} if args.routers else {}
    routers = api.get_pager('routers', fields='id,mac,name', **filters)
    router_ids = dict((x['id'], x) for x in routers)
    for rid, rinfo in router_ids.items():
        print("Logs for Router: %s" % rid)
        for x in api.get_pager('logs', rid):
            x['message'] = html.unescape(x['message'])
            x['name'] = '%s(%s)' % (rinfo['name'], rinfo['id'])
            x['mac'] = rinfo['mac']
            print(FORMAT % x)
