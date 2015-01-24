"""
ECM Command Line Interface
"""

from __future__ import print_function, division

import argparse
import getpass
import os
import syndicate
from .commands import logs, settings
from syndicate.adapters import sync as synadapter

COOKIE = os.environ.get('ECMCLI_COOKIE')

routers_parser = argparse.ArgumentParser(add_help=False)
routers_parser.add_argument('--routers', nargs='+', type=int)


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

    if COOKIE:
        auth = synadapter.HeaderAuth('Cookie', COOKIE)
    else:
        user, passwd = args.username, args.password
        if not user:
            user = raw_input('Username: ')
        if not passwd:
            passwd = getpass.getpass()
        auth = user, passwd

    api = syndicate.Service(uri='https://www.cradlepointecm.com',
                            urn='/api/v1/', auth=auth)
    args.invoke(api, args)
