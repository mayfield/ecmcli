"""
ECM Command Line Interface

This utility represents a collection of sub-commands to perform against the
Cradlepoint ECM service.  You must already have a valid ECM username/password
to use this tool.  For more info go to https://cradlepointecm.com/.
"""

import importlib
import pkg_resources
import sys
from . import api, commands, shell
from .commands import base

#import logging;logging.basicConfig(level=0)

command_modules = [
    #'accounts',
    #'alerts',
    #'config',
    #'flashleds',
    'groups',
    #'logs',
    #'reboot',
    #'routers',
    #'settings',
    #'shell',
    #'users',
    #'wanrate'
]


class ECM(base.Command):
    __doc__ = __doc__
    name = 'ecm'

    def setup_args(self, parser):
        distro = pkg_resources.get_distribution('ecmcli')
        parser.add_argument('--username')
        parser.add_argument('--password')
        parser.add_argument('--account', help='Limit activity to this account')
        parser.add_argument('--site', help='E.g. https://cradlepointecm.com')
        parser.add_argument('--version', action='version',
                            version=distro.version)

    def prerun(self, args):
        if args.account:
            account = self.api.get_by_id_or_name('accounts', args.account)
            self.api.account = account['id']
        super().prerun(args)

    def run(self, args):
        shell.ECMShell(self).cmdloop()


def main():
    ecm = ECM()
    for modname in command_modules:
        module = importlib.import_module('.%s' % modname, 'ecmcli.commands')
        for Command in module.command_classes:
            ecm.add_subcommand(Command())
    args = ecm.argparser.parse_args()
    ecm.api = api.ECMService(args.site, username=args.username,
                             password=args.password)
    try:
        ecm.invoke(args)
    except KeyboardInterrupt:
        sys.exit(1)
