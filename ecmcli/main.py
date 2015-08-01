"""
ECM Command Line Interface

This utility represents a collection of sub-commands to perform against the
Cradlepoint ECM service.  You must already have a valid ECM username/password
to use this tool.  For more info go to https://cradlepointecm.com/.
"""

import argparse
import importlib
import pkg_resources
import sys
from . import api, commands, shell

#import logging;logging.basicConfig(level=0)

command_modules = [
    'accounts',
    'alerts',
    'config',
    'flashleds',
    'groups',
    'logs',
    'reboot',
    'routers',
    'settings',
    'shell',
    'users',
    'wanrate'
]

distro = pkg_resources.get_distribution('ecmcli')
raw_formatter = argparse.RawDescriptionHelpFormatter
main_parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=raw_formatter)
cmd_desc = 'Provide a command argument to perform an operation.'
command_parser = main_parser.add_subparsers(title='commands',
                                            description=cmd_desc,
                                            metavar='COMMAND', help='Usage',
                                            dest='command')
main_parser.add_argument('--username')
main_parser.add_argument('--password')
main_parser.add_argument('--account', help='Limit activity to this account')
main_parser.add_argument('--site', help='E.g. https://cradlepointecm.com')
main_parser.add_argument('--version', action='version',
                         version=distro.version)


def main():
    cmds = []
    for modname in command_modules:
        module = importlib.import_module('.%s' % modname, 'ecmcli.commands')
        for Command in module.command_classes:
            cmd = Command()
            cmds.append(cmd)
            help = cmd.argparser.format_usage().split(' ', 2)[2]
            p = command_parser.add_parser(cmd.name, parents=[cmd.argparser],
                                          conflict_handler='resolve',
                                          description=Command.__doc__,
                                          help=help)
            p.set_defaults(invoke=cmd.invoke)

    args = main_parser.parse_args()
    ecmapi = api.ECMService(args.site, username=args.username,
                            password=args.password)
    if args.account:
        account = ecmapi.get_by_id_or_name('accounts', args.account)
        ecmapi.account = account['id']
    if not args.command:
        return shell.ECMShell(cmds, ecmapi).cmdloop()
    try:
        args.invoke(ecmapi, args)
    except KeyboardInterrupt:
        sys.exit(1)
