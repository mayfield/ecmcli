"""
ECM Command Line Interface
"""


import argparse
import getpass
import html
import json
import logging
import os
import syndicate
import syndicate.client
import sys
from .commands import logs, settings
from syndicate.adapters.sync import LoginAuth
from requests.utils import dict_from_cookiejar

logging.basicConfig(level=0)

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
        try:
            r = super().do(*args, **kwargs)
        except syndicate.client.ResponseError as e:
            if e.response['exception'] != 'unauthorized':
                r = e.response
                print('Response ERROR: ', file=sys.stderr)
                for key, val in sorted(e.response.items()):
                    print("  %-20s: %s" % (key.capitalize(),
                          html.unescape(str(val))), file=sys.stderr)
                exit(1)
            try:
                os.remove(COOKIES_FILE)
            except FileNotFoundError:
                flushed_state = False
            else:
                flushed_state = True
            print('ERROR: Unauthorized', file=sys.stderr)
            if flushed_state:
                print('WARNING: Flushed session state', file=sys.stderr)
            exit(1)
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

    p = subs.add_parser('settings', parents=[settings.parser])
    p.set_defaults(invoke=settings.command)

    p = subs.add_parser('logs', parents=[routers_parser, logs.parser])
    p.set_defaults(invoke=logs.command)

    args = parser.parse_args()

    api = ECMService(uri=SITE, urn='/api/v1/')
    if COOKIES:
        api.adapter.session.cookies.update(COOKIES)
    else:
        creds = {
            "username": args.username or input('Username: '),
            "password": args.password or getpass.getpass()
        }
        auth = LoginAuth(url='%s/api/v1/login/' % SITE, data=creds)
        api.auth = api.adapter.auth = auth

    try:
        args.invoke(api, args)
    except KeyboardInterrupt:
        exit(1)
