"""
Login to ECM.
"""

import getpass
from . import base


class Login(base.ECMCommand):
    """ Login to ECM. """

    name = 'login'
    use_pager = False

    def setup_args(self, parser):
        self.add_argument('username', nargs='?')

    def run(self, args):
        last_username = self.api.get_session(use_last=True)[0]
        prompt = 'Username'
        if last_username:
            prompt += ' [%s]: ' % last_username
        else:
            prompt += ': '
        username = args.username or input(prompt)
        if not username:
            if last_username:
                username = last_username
            else:
                raise SystemExit("Username required")
        if not self.api.load_session(username):
            password = getpass.getpass()
            self.api.set_auth(username, password)


class Logout(base.ECMCommand):
    """ Logout from ECM. """

    name = 'logout'
    use_pager = False

    def run(self, args):
        self.api.reset_auth()

command_classes = [Login, Logout]
