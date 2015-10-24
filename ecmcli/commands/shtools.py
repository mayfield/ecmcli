"""
Tools for the interactive shell.
"""


import code
from . import base


class Login(base.ECMCommand):
    """ Login as a different user. """

    name = 'login'

    def setup_args(self, parser):
        self.add_argument('username', nargs='?')

    def run(self, args):
        if not args.username:
            args.username = input('Username: ')
        self.api.login(args.username)
        self.shell.reset_cwd()


class Debug(base.ECMCommand):
    """ Run an interactive python interpretor. """

    name = 'debug'

    def run(self, args):
        code.interact(None, None, self.__dict__)

command_classes = [Login, Debug]
