"""
List/Edit/Manage ECM Users.
"""

import argparse
import getpass

role_choices = ['admin', 'full', 'readonly']

parser = argparse.ArgumentParser(add_help=False)
commands = parser.add_subparsers()
show_cmd = commands.add_parser('show')
create_cmd = commands.add_parser('create')
delete_cmd = commands.add_parser('delete')
edit_cmd = commands.add_parser('edit')
move_cmd = commands.add_parser('move')
search_cmd = commands.add_parser('search')

create_cmd.add_argument('--email')
create_cmd.add_argument('--password')
create_cmd.add_argument('--fullname')
create_cmd.add_argument('--role', choices=role_choices)

edit_cmd.add_argument('USERNAME')
edit_cmd.add_argument('--username')
edit_cmd.add_argument('--email')
edit_cmd.add_argument('--password')
edit_cmd.add_argument('--fullname')

move_cmd.add_argument('USERNAME')
move_cmd.add_argument('NEW_ACCOUNT_ID_OR_NAME')

delete_cmd.add_argument('USERNAME')
delete_cmd.add_argument('-f', '--force', action="store_true",
                        help="Do not prompt for confirmation")

show_cmd.add_argument('USERNAME', nargs='?')
show_cmd.add_argument('-v', '--verbose', action='store_true',
                      help="Verbose output.")

search_cmd.add_argument('SEARCH_CRITERIA', nargs='+')
search_cmd.add_argument('-v', '--verbose', action='store_true',
                        help="Verbose output.")


def command(api, args):
    if not hasattr(args, 'cmd'):
        raise ReferenceError('command argument required')
    args.cmd(api, args)


def show(api, args):
    printer = verbose_printer if args.verbose else terse_printer
    if not args.verbose:
        printer(None, header=True)
    for x in get_users(api):
        printer(x)

show_cmd.set_defaults(cmd=show)


def create(api, args):
    username = args.email or input('Email: ')
    password = args.password or getpass.getpass()
    name = (args.fullname or input('Full Name: ')).split()
    last_name = name.pop() if len(name) > 1 else None
    role = args.role or input('Role {%s}: ' % ', '.join(role_choices))
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
    user = api.get('users', username=username, expand='profile.account')
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
        confirm = input('Delete user: %s, id:%s (type "yes" to confirm): ' % (
                        args.USERNAME, user['id']))
        if confirm != 'yes':
            print("Aborted")
            exit(1)
    api.delete('users', user['id'])

delete_cmd.set_defaults(cmd=delete)


def move(api, args):
    user = get_user(api, args.USERNAME)
    account = api.get_by_id_or_name('accounts', args.NEW_ACCOUNT_ID_OR_NAME)
    if not account:
        print("Account Not Found:", args.NEW_ACCOUNT_ID_OR_NAME)
        exit(1)
    api.put('profiles', user['profile']['id'], {"account": account['resource_uri']})

move_cmd.set_defaults(cmd=move)


def search(api, args):
    search = ' '.join(args.SEARCH_CRITERIA)
    fields = ['username', 'first_name', 'last_name', 'email']
    results = list(api.search('users', fields, search))
    if not results:
        print("No Results For:", search)
        exit(1)
    printer = verbose_printer if args.verbose else terse_printer
    if not args.verbose:
        printer(None, header=True)
    for x in get_users(api, id__in=','.join(x['id'] for x in results)):
        printer(x)

search_cmd.set_defaults(cmd=search)


def get_users(api, **filters):
    expand = ['authorizations', 'authorizations.role', 'profile.account']
    for x in api.get_pager('users', expand=','.join(expand), **filters):
        x['name'] = '%(first_name)s %(last_name)s' % x
        x['roles'] = ', '.join(xx['role']['name']
                               for xx in x['authorizations']
                               if xx['role']['id'] != '4')
        yield x


def verbose_printer(user):
    account = user['profile']['account']
    print('Username:   ', user['username'])
    print('Full Name:  ', user['name'])
    print('Account:    ', account['name'], '(%s)' % account['id'])
    print('Role(s):    ', user['roles'])
    print('ID:         ', user['id'])
    print('Email:      ', user['email'])
    print('Joined:     ', user['date_joined'])
    print('Last Login: ', user['last_login'])
    print()


def terse_printer(user, header=False):
    if header:
        user = {
            "username": 'USERNAME',
            "name": 'FULL NAME',
            "account_desc": 'ACCOUNT',
            "roles": 'ROLE(S)',
            "id": 'ID',
            "email": 'EMAIL'
        }
    else:
        user = user.copy()
        account = user['profile']['account']
        user['account_desc'] = '%s (%s)' % (account['name'], account['id'])
    print('%(username)-28s %(name)-23s %(account_desc)-21s %(roles)-17s %(id)-6s %(email)s' % user)
