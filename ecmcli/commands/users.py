"""
List/Edit/Manage ECM Users.
"""

import argparse

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
        x['name'] = '%(first_name)s %(last_name)s (%(username)s)' % x
        print(fmt % x)
