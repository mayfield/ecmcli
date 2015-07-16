"""
ECM Command Line Interface

This utility represents a collection of sub-commands to perform against the
Cradlepoint ECM service.  You must already have a valid ECM username/password
to use this tool.  For more info go to https://cradlepointecm.com/.
"""

import argparse
import collections
import importlib
import logging
import pkg_resources
import sys
from . import api, commands

# logging.basicConfig(level=0)

routers_parser = argparse.ArgumentParser(add_help=False)
routers_parser.add_argument('--routers', nargs='+', metavar="ID_OR_NAME")

raw_formatter = argparse.RawDescriptionHelpFormatter
distro = pkg_resources.get_distribution('ecmcli')
main_parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=raw_formatter)
sub_desc = 'Provide a subcommand argument (below) to perform an operation.'
subs = main_parser.add_subparsers(title='subcommands', description=sub_desc,
                                  metavar='SUBCOMMAND', help='Usage')
main_parser.add_argument('--username')
main_parser.add_argument('--password')
main_parser.add_argument('--account')
main_parser.add_argument('--version', action='version', version=distro.version)

def add_command(name, parents=None, **defaults):
    module = importlib.import_module('.%s' % name, 'ecmcli.commands')
    if not parents:
        parents = []
    try:
        help = module.parser.format_usage().split(' ', 2)[2]
    except IndexError:
        help = ''
    p = subs.add_parser(name, parents=parents+[module.parser], help=help)
    p.set_defaults(invoke=module.command, **defaults)

add_command('settings')
add_command('logs', parents=[routers_parser], get_routers=True)
add_command('flashleds', parents=[routers_parser], get_routers=True)
add_command('reboot', parents=[routers_parser], get_routers=True)
add_command('wanrate', parents=[routers_parser], get_routers=True)
add_command('shell', parents=[routers_parser], get_routers=True)
add_command('ls', get_routers=True)
add_command('alerts', parents=[routers_parser], get_routers=True)
add_command('users')
add_command('groups')
add_command('accounts')
add_command('config', parents=[routers_parser], get_routers=True)


def main():
    args = main_parser.parse_args()
    if not hasattr(args, 'invoke'):
        main_parser.print_help()
        exit(1)
    ecmapi = api.ECMService(username=args.username, password=args.password)
    if args.account:
        try:
            ecmapi.account = int(args.account)
        except ValueError:
            accounts = ecmapi.get('accounts', fields='id', name=args.account)
            ecmapi.account = accounts[0]['id']
    options = {}
    if getattr(args, 'get_routers', False):
        filters = {}
        if getattr(args, 'routers', None):
            id_filters = []
            name_filters = []
            for x in args.routers:
                try:
                    id_filters.append(str(int(x)))
                except ValueError:
                    name_filters.append(x)
            if id_filters:
                filters["id__in"] = ','.join(id_filters)
            if name_filters:
                filters["name__in"] = ','.join(name_filters)
        routers = ecmapi.get_pager('routers', **filters)
        if not routers:
            print("WARNING: No Routers Found", file=sys.stderr)
            exit(0)
        options['routers'] = routers
    try:
        args.invoke(ecmapi, args, **options)
    except KeyboardInterrupt:
        pass
    except ReferenceError as e:
        print('ERROR:', e)
        main_parser.print_usage()
    else:
        exit(0)
    exit(1)
