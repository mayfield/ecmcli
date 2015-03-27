"""
List/Edit/Manage ECM Users.
"""

import argparse
import functools
import html
import humanize

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('-c', '--create', action='store_true',
                    help="Create new user.")
parser.add_argument('-e', '--edit', action='store_true',
                    help="Edit existing user.")
parser.add_argument('-d', '--delete', action='store_true',
                    help="Delete user.")
parser.add_argument('-v', '--verbose', action='store_true',
                    help="Verbose output.")



def command(api, args):
    if args.create:
        return create_user(api)
    elif args.edit:
        return edit_user(api)
    elif args.delete:
        return delete_user(api)
    else:
        printer = verbose_printer if args.verbose else terse_printer
        printer(api=api)


def create_user(api):
    print("CREATE")


def edit_user(api):
    print("EDIT")


def delete_user(api):
    print("DELETE")


def verbose_printer(api=None):
    pass


def terse_printer(api=None):
    fmt = '%(name)-30s %(id)6s %(email)30s'
    for x in api.get_pager('users', expand='profile'):
        x['email'] = html.unescape(x['email'])
        x['name'] = '%s %s (%s)' % (html.unescape(x['first_name']),
                    html.unescape(x['last_name']),
                    html.unescape(x['username']))
        print(fmt % x)
