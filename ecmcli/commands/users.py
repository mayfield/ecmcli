"""
List/Edit/Manage ECM Users.
"""

import argparse
import getpass

parser = argparse.ArgumentParser(add_help=False)
commands = parser.add_subparsers()
show_cmd = commands.add_parser('show')
create_cmd = commands.add_parser('create')
delete_cmd = commands.add_parser('delete')
edit_cmd = commands.add_parser('edit')

create_cmd.add_argument('--email')
create_cmd.add_argument('--password')
create_cmd.add_argument('--fullname')
create_cmd.add_argument('--role', choices=['admin', 'full', 'readonly'])

edit_cmd.add_argument('USERNAME')
edit_cmd.add_argument('--email')
edit_cmd.add_argument('--password')
edit_cmd.add_argument('--fullname')
roll_choices = ['admin', 'full', 'readonly']
edit_cmd.add_argument('--role', choices=roll_choices)

delete_cmd.add_argument('USERNAME')

show_cmd.add_argument('USERNAME', nargs='?')
show_cmd.add_argument('-v', '--verbose', action='store_true',
                      help="Verbose output.")


def command(api, args):
    if not hasattr(args, 'cmd'):
        raise ReferenceError('command argument required')
    args.cmd(api, args)


def show(api, args):
    printer = verbose_printer if args.verbose else terse_printer
    printer(api=api)

show_cmd.set_defaults(cmd=show)


def create(api, args):
    username = args.email or input('Email: ')
    password = args.password or getpass.getpass()
    name = (args.fullname or input('Full Name: ')).split()
    last_name = name.pop() if len(name) > 1 else None
    role = args.role or input('Role {%s}: ' % ', '.join(roll_choices))
    role_id = {
        'admin': 1,
        'full': 2,
        'readonly': 3
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
    api.post('authorizations', {
        "account": user['profile']['account'],
        "cascade": True,
        "role": '/api/v1/roles/%d/' % role_id,
        "user": user['resource_uri']
    })
    print("Created user: %s" % user['username'])

create_cmd.set_defaults(cmd=create)


def edit(api, args):
    print("EDIT")

edit_cmd.set_defaults(cmd=edit)


def delete(api, args):
    print("DELETE")

delete_cmd.set_defaults(cmd=delete)


def verbose_printer(api=None):
    pass


def terse_printer(api=None):
    fmt = '%(name)-30s %(id)6s %(email)30s'
    for x in api.get_pager('users', expand='profile'):
        x['name'] = '%(first_name)s %(last_name)s (%(username)s)' % x
        print(fmt % x)
