"""
List/Edit/Manage ECM Users.
"""

import argparse
import getpass

roll_choices = ['admin', 'full', 'readonly']

parser = argparse.ArgumentParser(add_help=False)
commands = parser.add_subparsers()
show_cmd = commands.add_parser('show')
create_cmd = commands.add_parser('create')
delete_cmd = commands.add_parser('delete')
edit_cmd = commands.add_parser('edit')

create_cmd.add_argument('--email')
create_cmd.add_argument('--password')
create_cmd.add_argument('--fullname')
create_cmd.add_argument('--role', choices=roll_choices)

edit_cmd.add_argument('USERNAME')
edit_cmd.add_argument('--username')
edit_cmd.add_argument('--email')
edit_cmd.add_argument('--password')
edit_cmd.add_argument('--fullname')
edit_cmd.add_argument('--role', choices=roll_choices)

delete_cmd.add_argument('USERNAME')
delete_cmd.add_argument('-f', '--force', action="store_true",
                        help="Do not prompt for confirmation")

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

create_cmd.set_defaults(cmd=create)


def get_user(api, username):
    user = api.get('users', username=username)
    if not user:
        print("Invalid Username")
        exit(1)
    return user[0]


def edit(api, args):
    user = get_user(api, args.USERNAME)
    username = args.username or input('Username [%s]: ' % user['username'])
    email = args.email or input('Email [%s]: ' % user['email'])
    prompt = 'Password [enter for no change]: '
    password = args.password or getpass.getpass(prompt)
    prompt = 'Full Name [%s %s]: ' % (user['first_name'], user['last_name'])
    name = (args.fullname or input(prompt)).split()
    last_name = name.pop() if len(name) > 1 else ''
    updates = {}
    if username:
        updates['username'] = username
    if email:
        updates['email'] = email
    if password:
        updates['password'] = password
        updates['current_password'] = getpass.getpass('Current Password ' \
                                                      'Required: ')
    if name:
        updates['first_name'] = name[0]
        updates['last_name'] = last_name
    user = api.put('users', user['id'], updates)

edit_cmd.set_defaults(cmd=edit)


def delete(api, args):
    user = get_user(api, args.USERNAME)
    if not args.force:
        confirm =input('Delete user: %s, id:%s (type "yes" to confirm): ' % (
                       args.USERNAME, user['id']))
        if confirm != 'yes':
            print("Aborted")
            exit(1)
    api.delete('users', user['id'])

delete_cmd.set_defaults(cmd=delete)


def get_users(api):
    expand = ['profile', 'authorizations', 'authorizations.role']
    for x in api.get_pager('users', expand=','.join(expand)):
        x['name'] = '%(first_name)s %(last_name)s' % x
        x['roles'] = ', '.join(xx['role']['name']
                               for xx in x['authorizations']
                               if xx['role']['id'] != '4')
        yield x


def verbose_printer(api=None):
    for x in get_users(api):
        print('Username:   ', x['username'])
        print('Full Name:  ', x['name'])
        print('Role(s):    ', x['roles'])
        print('ID:         ', x['id'])
        print('Email:      ', x['email'])
        print('Joined:     ', x['date_joined'])
        print('Last Login: ', x['last_login'])
        print()


def terse_printer(api=None):
    fmt = '%(username)-28s %(name)-23s %(roles)-17s %(id)-6s %(email)s'
    print(fmt % {
        "username": 'USERNAME',
        "name": 'FULL NAME',
        "roles": 'ROLE(S)',
        "id": 'ID',
        "email": 'EMAIL'
    })
    for x in get_users(api):
        print(fmt % x)
