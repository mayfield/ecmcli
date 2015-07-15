"""
List/Edit/Manage ECM Users.
"""

import argparse
import getpass
from html.parser import HTMLParser

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


class TOSParser(HTMLParser):

    end = '\033[0m'
    tags = {
        'b': ('\033[1m', end),
        'h2': ('\n\033[1m', end+'\n'),
        'h1': ('\n\033[1m', end+'\n'),
        'ul': ('\033[4m', end),
        'p': ('\n', '\n')
    }
    ignore = [
        'style',
        'script',
        'head'
    ]

    def __init__(self):
        self.fmt_stack = []
        self.ignore_stack = []
        super().__init__()

    def handle_starttag(self, tag, attrs):
        if tag in self.tags:
            start, end = self.tags[tag]
            print(start, end='')
            self.fmt_stack.append((tag, end))
        if tag in self.ignore:
            self.ignore_stack.append(tag)

    def handle_endtag(self, tag):
        if self.fmt_stack and tag == self.fmt_stack[-1][0]:
            print(self.fmt_stack.pop()[1], end='')
        elif self.ignore_stack and tag == self.ignore_stack[-1]:
            self.ignore_stack.pop()

    def handle_data(self, data):
        if not self.ignore_stack:
            print(data.replace('\n', ' '), end='')

tos_parser = TOSParser()


def create_user(api):
    username = input('Email: ')
    password = getpass.getpass()
    name = input('Full Name: ').split()
    last_name = name.pop() if len(name) > 1 else None
    role = input('Role [a]dmin, [f]ull-access, [r]ead-only]: ')
    role_id = {
        'a': 1,
        'f': 2,
        'r': 3
    }.get(role)
    if not role_id:
        print("Invalid role selection")
        return
    user = api.post('users', {
        "username": username,
        "email": username,
        "first_name": ' '.join(name),
        "last_name": last_name,
        "password": password
    }, expand='profile')
    api.put('profiles', user['profile']['id'], {
        "require_password_change": False
    })
    print()
    api.post('authorizations', {
        "account": user['profile']['account'],
        "cascade": True,
        "role": '/api/v1/roles/%d/' % role_id,
        "user": user['resource_uri']
    })
    for x in api.get_pager('system_message', type='tos'):
        tos_parser.feed(x['message'])
        print()
        accept = input('Type "accept" to comply with this TOS: ')
        if accept != 'accept':
            print("WARNING: User not activated")
            return
        api.post('system_message_confirm', {
            "message": x['resource_uri']
        })


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
