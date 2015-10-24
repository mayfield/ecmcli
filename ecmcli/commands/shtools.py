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
        self.api.login(args.username)
        self.shell.reset_cwd()


class Logout(base.ECMCommand):
    """ Logout from ECM. """

    name = 'logout'

    def run(self, args):
        self.api.reset_auth()
        self.shell.reset_cwd()


class Debug(base.ECMCommand):
    """ Run an interactive python interpretor. """

    name = 'debug'

    def run(self, args):
        code.interact(None, None, self.__dict__)

command_classes = [Login, Logout, Debug]
