"""
Bootstrap the shell and commands and then run either one.
"""

import importlib
import pkg_resources
import shellish
import sys
from . import api
from .commands import base, shtools

command_modules = [
    'accounts',
    'alerts',
    'authorizations',
    'firmware',
    'flashleds',
    'gpio',
    'groups',
    'logs',
    'messages',
    'remote',
    'routers',
    'settings',
    'shell',
    'trace',
    'users',
    'wanrate'
]


class ECMRoot(base.ECMCommand):
    """ ECM Command Line Interface

    This utility represents a collection of sub-commands to perform against
    the Cradlepoint ECM service.  You must already have a valid ECM
    username/password to use this tool.  For more info go to
    https://cradlepointecm.com/. """

    name = 'ecm'

    def setup_args(self, parser):
        distro = pkg_resources.get_distribution('ecmcli')
        self.add_argument('--api-username')
        self.add_argument('--api-password')
        self.add_argument('--api-site',
                          help='E.g. https://cradlepointecm.com')
        self.add_argument('--debug', action='store_true')
        self.add_argument('--version', action='version',
                          version=distro.version)

    def run(self, args):
        for x in shtools.command_classes:
            self.add_subcommand(x)
        self.interact()


def main():
    try:
        _main()
    except KeyboardInterrupt:
        sys.exit(1)
    except BrokenPipeError:
        sys.exit(1)


def _main():
    root = ECMRoot(api=api.ECMService())
    root.add_subcommand(shellish.SystemCompletionSetup)
    for modname in command_modules:
        module = importlib.import_module('.%s' % modname, 'ecmcli.commands')
        for Command in module.command_classes:
            root.add_subcommand(Command)
    args = root.argparser.parse_args()
    if args.debug:
        root['trace']['enable']([])
    root.api.connect(args.api_site, username=args.api_username,
                     password=args.api_password)
    root(args)
