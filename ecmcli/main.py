"""
ECM Command Line Interface
"""

import argparse
import getpass
import json
import os
import syndicate
from .commands import logs, settings
from syndicate.adapters.sync import LoginAuth
from requests.utils import dict_from_cookiejar


SITE = 'https://cradlepointecm.com'
COOKIES_FILE = os.path.expanduser('~/.ecmcli_cookies')
try:
    with open(COOKIES_FILE) as f:
        COOKIES = json.load(f)
except IOError:
    COOKIES = None

routers_parser = argparse.ArgumentParser(add_help=False)
routers_parser.add_argument('--routers', nargs='+', type=int)


class ECMService(syndicate.Service):

    def do(self, *args, **kwargs):
        global COOKIES
        r = super().do(*args, **kwargs)
        cookies = dict_from_cookiejar(self.adapter.session.cookies)
        if cookies != COOKIES:
            with open(COOKIES_FILE, 'w') as f:
                os.chmod(COOKIES_FILE, 0o600)
                json.dump(cookies, f)
            COOKIES = cookies
        return r


def main():
    parser = argparse.ArgumentParser(description='ECM Command Line Interface')
    subs = parser.add_subparsers(title='SUBCOMMANDS',
                                 description='Valid Subcommands')
    parser.add_argument('--username')
    parser.add_argument('--password')

    settings_parser = subs.add_parser('settings')
    settings_parser.set_defaults(invoke=settings.command)

    logs_parser = subs.add_parser('logs', parents=[routers_parser])
    logs_parser.set_defaults(invoke=logs.command)

    args = parser.parse_args()

    api = ECMService(uri=SITE, urn='/api/v1/')
    if COOKIES:
        api.adapter.session.cookies.update(COOKIES)
    else:
        user = args.username or input('Username: ')
        passwd = args.password or getpass.getpass()
        login_url = '%s/api/v1/login/' % SITE
        auth = LoginAuth(url=login_url, method='POST', data={
            "username": user,
            "password": passwd
        })
        api.auth = api.adapter.auth = auth
    args.invoke(api, args)
