"""
ECM Command Line Interface
"""

import argparse
import collections
import logging
import sys
from . import api
from .commands import logs, settings, flashleds, reboot, wanrate

#logging.basicConfig(level=0)

routers_parser = argparse.ArgumentParser(add_help=False)
routers_parser.add_argument('--routers', nargs='+')

main_parser = argparse.ArgumentParser(description='ECM Command Line Interface')
subs = main_parser.add_subparsers(title='SUBCOMMANDS',
                                  description='Valid Subcommands')
main_parser.add_argument('--username')
main_parser.add_argument('--password')

p = subs.add_parser('settings', parents=[settings.parser])
p.set_defaults(invoke=settings.command)

p = subs.add_parser('logs', parents=[routers_parser, logs.parser])
p.set_defaults(invoke=logs.command)

p = subs.add_parser('flashleds', parents=[routers_parser,
                    flashleds.parser])
p.set_defaults(invoke=flashleds.command)

p = subs.add_parser('reboot', parents=[routers_parser, reboot.parser])
p.set_defaults(invoke=reboot.command)

p = subs.add_parser('wanrate', parents=[routers_parser, wanrate.parser])
p.set_defaults(invoke=wanrate.command)


def main():
    args = main_parser.parse_args()
    if not hasattr(args, 'invoke'):
        main_parser.print_usage()
        exit(1)
    ecmapi = api.ECMService(username=args.username, password=args.password)
    filters = {"id__in": ','.join(map(str, args.routers))} \
              if getattr(args, 'routers', None) else {}
    routers = ecmapi.get_pager('routers', **filters)
    routers = collections.OrderedDict((x['id'], x) for x in routers)
    if not routers:
        print("WARNING: No Routers Found", file=sys.stderr)
        exit(0)
    try:
        args.invoke(ecmapi, args, routers)
    except KeyboardInterrupt:
        exit(1)
