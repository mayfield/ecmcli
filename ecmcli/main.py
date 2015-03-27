"""
ECM Command Line Interface
"""

import argparse
import collections
import logging
import sys
from . import api
from .commands import (
    accounts,
    alerts,
    flashleds,
    groups,
    logs,
    ls,
    reboot,
    settings,
    shell,
    users,
    wanrate,
)

# logging.basicConfig(level=0)

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
p.set_defaults(invoke=logs.command, get_routers=True)

p = subs.add_parser('flashleds', parents=[routers_parser,
                    flashleds.parser])
p.set_defaults(invoke=flashleds.command, get_routers=True)

p = subs.add_parser('reboot', parents=[routers_parser, reboot.parser])
p.set_defaults(invoke=reboot.command, get_routers=True)

p = subs.add_parser('wanrate', parents=[routers_parser, wanrate.parser])
p.set_defaults(invoke=wanrate.command, get_routers=True)

p = subs.add_parser('shell', parents=[routers_parser, shell.parser])
p.set_defaults(invoke=shell.command, get_routers=True)

p = subs.add_parser('ls', parents=[ls.parser])
p.set_defaults(invoke=ls.command, get_routers=True)

p = subs.add_parser('alerts', parents=[routers_parser, alerts.parser])
p.set_defaults(invoke=alerts.command)

p = subs.add_parser('users', parents=[users.parser])
p.set_defaults(invoke=users.command)

p = subs.add_parser('groups', parents=[groups.parser])
p.set_defaults(invoke=groups.command)

p = subs.add_parser('accounts', parents=[accounts.parser])
p.set_defaults(invoke=accounts.command)


def main():
    args = main_parser.parse_args()
    if not hasattr(args, 'invoke'):
        main_parser.print_usage()
        exit(1)
    ecmapi = api.ECMService(username=args.username, password=args.password)
    options = {}
    if getattr(args, 'get_routers', False):
        filters = {"id__in": ','.join(map(str, args.routers))} \
                  if getattr(args, 'routers', None) else {}
        routers = ecmapi.get_pager('routers', **filters)
        routers = collections.OrderedDict((x['id'], x) for x in routers)
        if not routers:
            print("WARNING: No Routers Found", file=sys.stderr)
            exit(0)
        options['routers'] = routers
    try:
        args.invoke(ecmapi, args, **options)
    except KeyboardInterrupt:
        exit(1)
