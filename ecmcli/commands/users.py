"""
List/Edit/Manage ECM Users.
"""

import argparse
import getpass

role_choices = ['admin', 'full', 'readonly']

parser = argparse.ArgumentParser(add_help=False)
commands = parser.add_subparsers(dest='cmd')
show_parser = commands.add_parser('show', help='Show users (DEFAULT)')
create_parser = commands.add_parser('create', help='Create user')
delete_parser = commands.add_parser('delete', help='Delete user')
edit_parser = commands.add_parser('edit', help='Edit user attributes')
move_parser = commands.add_parser('move', help='Move user to new account')
search_parser = commands.add_parser('search', help='Search for user(s)')

create_parser.add_argument('--email')
create_parser.add_argument('--password')
create_parser.add_argument('--fullname')
create_parser.add_argument('--role', choices=role_choices)

edit_parser.add_argument('USERNAME')
edit_parser.add_argument('--username')
edit_parser.add_argument('--email')
edit_parser.add_argument('--password')
edit_parser.add_argument('--fullname')

move_parser.add_argument('USERNAME')
move_parser.add_argument('NEW_ACCOUNT_ID_OR_NAME')

delete_parser.add_argument('USERNAME')
delete_parser.add_argument('-f', '--force', action="store_true",
                        help="Do not prompt for confirmation")

show_parser.add_argument('USERNAME', nargs='?')
show_parser.add_argument('-v', '--verbose', action='store_true',
                      help="Verbose output.")

search_parser.add_argument('SEARCH_CRITERIA', nargs='+')
search_parser.add_argument('-v', '--verbose', action='store_true',
                           help="Verbose output.")


def command(api, args):
    if not args.cmd:
        args.cmd = 'show'
        args.verbose = False
        args.USERNAME = None
    cmd = globals()['%s_cmd' % args.cmd]
    cmd(api, args)


def show_cmd(api, args):
    printer = verbose_printer if args.verbose else terse_printer
    if args.USERNAME:
        users = [get_user(api, args.USERNAME)]
    else:
        users = get_users(api)
    if not args.verbose:
        printer(None, header=True)
    for x in users:
        printer(x)


def create_cmd(api, args):
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


def get_user(api, username):
    expand = ['authorizations.role', 'profile.account']
    user = api.get('users', username=username, expand=','.join(expand))
    if not user:
        print("Invalid Username")
        exit(1)
    return bundle_user(user[0])


def edit_cmd(api, args):
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


def delete_cmd(api, args):
    user = get_user(api, args.USERNAME)
    if not args.force:
        confirm = input('Delete user: %s, id:%s (type "yes" to confirm): ' % (
                        args.USERNAME, user['id']))
        if confirm != 'yes':
            print("Aborted")
            exit(1)
    api.delete('users', user['id'])


def move_cmd(api, args):
    user = get_user(api, args.USERNAME)
    account = api.get_by_id_or_name('accounts', args.NEW_ACCOUNT_ID_OR_NAME)
    api.put('profiles', user['profile']['id'], {"account": account['resource_uri']})


def search_cmd(api, args):
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


def bundle_user(user):
    user['name'] = '%(first_name)s %(last_name)s' % user
    user['roles'] = ', '.join(x['role']['name']
                              for x in user['authorizations']
                              if x['role']['id'] != '4')
    return user


def get_users(api, **filters):
    expand = ['authorizations.role', 'profile.account']
    for x in api.get_pager('users', expand=','.join(expand), **filters):
        yield bundle_user(x)


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
