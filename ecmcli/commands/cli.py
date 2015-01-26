"""
Pull data from the router CLI and make it look like it's this tool's interface.
"""

import argparse
import html

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('command', nargs="+", help='Command to execute')


def command(api, args, routers):
    rfilter = {
        "id__in": ','.join(routers)
    }
    command = '%s\n' % ' '.join(args.command)
    data = api.put('remote/control/csterm/ecmcli-%s/k' % api.sessionid,
                   command, **rfilter)
    for x in data:
        print()
        print("%s (%s):" % (routers[str(x['id'])]['name'], x['id']))
        print("=" * 80)
        if x['success']:
            if x['data'] == command:
                print("Warning: unsupported firmware")
            else:
                print(html.unescape(x['data']))
        else:
            print("Error: %s / %s" % (x['exception'], x['reason']))
        print("-" * 80)
        print()
