"""
List ECM Accounts.
"""

import argparse
import html

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('-v', '--verbose', action='store_true',
                    help="Verbose output.")


def command(api, args):
    printer = verbose_printer if args.verbose else terse_printer
    printer(api=api)


def verbose_printer(api=None):
    pass


def terse_printer(api=None):
    fmt = '%(name)-20s %(id)6s'
    for x in api.get_pager('accounts'):
        x['name'] = html.unescape(x['name'])
        print(fmt % x)
