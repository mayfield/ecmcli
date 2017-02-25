"""
Bootstrap the shell and commands and then run either one.
"""

import importlib
import logging
import pkg_resources
import shellish
import shellish.logging
import sys
from . import api
from .commands import base, shtools
from shellish.command import contrib

command_modules = [
    'accounts',
    'activity_log',
    'alerts',
    'apps',
    'authorizations',
    'clients',
    'features',
    'firmware',
    'groups',
    'login',
    'logs',
    'messages',
    'netflow',
    'remote',
    'routers',
    'shell',
    'tos',
    'trace',
    'users',
    'wanrate',
    'wifi',
]


class ECMSession(shellish.Session):

    command_error_verbosity = 'pretty'
    default_prompt_format = r': \033[7m{user}\033[0m / ECM ;\n:;'
    intro = '\n'.join([
        'Welcome to the ECM shell.',
        'Type "help" or "?" to list commands and "exit" to quit.'
    ])

    def verror(self, *args, **kwargs):
        msg = ' '.join(map(str, args))
        shellish.vtmlprint(msg, file=sys.stderr, **kwargs)

    def prompt_info(self):
        info = super().prompt_info()
        ident = self.root_command.api.ident
        username = ident['user']['username'] if ident else '*LOGGED_OUT*'
        info.update({
            "user": username,
            "site": self.root_command.api.site.split('//', 1)[1]
        })
        return info

    def execute(self, *args, **kwargs):
        try:
            return super().execute(*args, **kwargs)
        except api.TOSRequired:
            self.verror('TOS Acceptance Required')
            input('Press <enter> to review TOS')
            return self.root_command['tos']['accept'](argv='')
        except api.AuthFailure as e:
            self.verror('Auth error:' % e)
            return self.root_command['login'](argv='')


class ECMRoot(base.ECMCommand):
    """ ECM Command Line Interface

    This utility represents a collection of sub-commands to perform against
    the Cradlepoint ECM service.  You must already have a valid ECM
    username/password to use this tool.  For more info go to
    https://cradlepointecm.com/. """

    name = 'ecm'
    use_pager = False
    Session = ECMSession

    def setup_args(self, parser):
        distro = pkg_resources.get_distribution('ecmcli')
        self.add_argument('--api-username')
        self.add_argument('--api-password')
        self.add_argument('--api-site',
                          help='E.g. https://cradlepointecm.com')
        self.add_argument('--debug', action='store_true')
        self.add_argument('--trace', action='store_true')
        self.add_argument('--no-pager', action='store_true')
        self.add_argument('--version', action='version',
                          version=distro.version)
        self.add_subcommand(contrib.Commands)
        self.add_subcommand(contrib.SystemCompletion)

    def prerun(self, args):
        """ Add the interactive commands just before it goes to the prompt so
        they don't show up in the --help from the commands line. """
        for x in shtools.command_classes:
            self.add_subcommand(x)
        self.add_subcommand(contrib.Exit)
        self.add_subcommand(contrib.Help)
        self.add_subcommand(contrib.INI)
        self.add_subcommand(contrib.Reset)
        self.add_subcommand(contrib.Pager)
        self.remove_subcommand(contrib.SystemCompletion)

    def run(self, args):
        self.session.run_loop()


def main():
    try:
        _main()
    except KeyboardInterrupt:
        sys.exit(1)


def _main():
    root = ECMRoot(api=api.ECMService())
    for modname in command_modules:
        module = importlib.import_module('.%s' % modname, 'ecmcli.commands')
        for Command in module.command_classes:
            root.add_subcommand(Command)
    args = root.parse_args()
    if args.no_pager:
        root.session.allow_pager = False
    if args.trace:
        root['trace']['enable'](argv='')
    if args.debug:
        if args.debug:
            logger = logging.getLogger()
            logger.setLevel('DEBUG')
            logger.addHandler(shellish.logging.VTMLHandler())
    try:
        root.api.connect(args.api_site, username=args.api_username,
                         password=args.api_password)
    except api.Unauthorized:
        root['login'](argv='')
    root(args)
