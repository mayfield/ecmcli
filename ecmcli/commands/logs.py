"""
Download Device Logs from ECM.
"""

from syndicate import data as syndata
try:
    import html
except ImportError:
    import HTMLParser
    html_unescape = HTMLParser.HTMLParser().unescape
else:
    html_unescape = html.unescape

FORMAT = '%(timestamp)s [%(levelname)8s] [%(source)16s] %(message)s'


def command(api, args):
    if not args.routers:
        routers = api.get_pager('routers', fields='id, mac')
        router_ids = dict((x['id'], r['mac']) for x in routers)
    else:
        router_ids = map(str, args.routers)
    for rid in router_ids:
        print("Logs for Router: %s" % rid)
        for x in api.get_pager('logs', rid):
            x['message'] = html_unescape(x['message'])
            print(FORMAT % x)
