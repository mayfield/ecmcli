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
passwd_parser = commands.add_parser('passwd', help='Change user password')
search_parser = commands.add_parser('search', help='Search for user(s)')

create_parser.add_argument('--email')
create_parser.add_argument('--password')
create_parser.add_argument('--fullname')
create_parser.add_argument('--role', choices=role_choices)

edit_parser.add_argument('USERNAME')
edit_parser.add_argument('--email')
edit_parser.add_argument('--fullname')

move_parser.add_argument('USERNAME')
move_parser.add_argument('NEW_ACCOUNT_ID_OR_NAME')

passwd_parser.add_argument('USERNAME')

delete_parser.add_argument('USERNAME', nargs='+')
delete_parser.add_argument('-f', '--force', action="store_true",
                           help="Do not prompt for confirmation")

show_parser.add_argument('USERNAME', nargs='?')
show_parser.add_argument('-v', '--verbose', action='store_true',
                         help="Verbose output.")

search_parser.add_argument('SEARCH_CRITERIA', nargs='+')
search_parser.add_argument('-v', '--verbose', action='store_true',
                           help="Verbose output.")


EXPANDS = ','.join([
    'authorizations.role',
    'profile.account'
])


def splitname(fullname):
    name = fullname.rsplit(' ', 1)
    last_name = name.pop() if len(name) > 1 else ''
    return name[0], last_name


def command(api, args):
    if not args.cmd:
        args.cmd = 'show'
        args.verbose = False
        args.USERNAME = None
    cmd = globals()['%s_cmd' % args.cmd]
    cmd(api, args)


def show_cmd(api, args, users=None):
    printer = verbose_printer if args.verbose else terse_printer
    if users is None:
        if args.USERNAME:
            users = [get_user(api, args.USERNAME)]
        else:
            users = api.get_pager('users', expand=EXPANDS)
    if not args.verbose:
        printer(None, header=True)
    for x in users:
        printer(bundle_user(x))


def create_cmd(api, args):
    username = args.email or input('Email: ')
    password = args.password
    if not password:
        password = getpass.getpass('Password (or empty to send email): ')
        if password:
            password2 = getpass.getpass('Confirm Password: ')
            if password != password2:
                print("Aborted: passwords do not match")
                exit(1)
    name = splitname(args.fullname or input('Full Name: '))
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
        "first_name": name[0],
        "last_name": name[1],
        "password": password
    }, expand='profile')
    api.put('profiles', user['profile']['id'], {
        "require_password_change": not password
    })
    api.post('authorizations', {
        "account": user['profile']['account'],
        "cascade": True,
        "role": '/api/v1/roles/%d/' % role_id,
        "user": user['resource_uri']
    })


def get_user(api, username):
    user = api.get('users', username=username, expand=EXPANDS)
    if not user:
        print("Invalid Username")
        exit(1)
    return user[0]


def edit_cmd(api, args):
    user = get_user(api, args.USERNAME)
    updates = {}
    if args.fullname:
        first, last = splitname(args.fullname)
        updates['first_name'] = first
        updates['last_name'] = last
    if args.email:
        updates['email'] = args.email
    api.put('users', user['id'], updates)


def delete_cmd(api, args):
    for username in args.USERNAME:
        user = get_user(api, username)
        if not args.force:
            confirm = input('Delete user: %s, id:%s (type "yes" to confirm): '
                            % (username, user['id']))
            if confirm != 'yes':
                print("Aborted")
                continue
        api.delete('users', user['id'])


def move_cmd(api, args):
    user = get_user(api, args.USERNAME)
    account = api.get_by_id_or_name('accounts', args.NEW_ACCOUNT_ID_OR_NAME)
    api.put('profiles', user['profile']['id'],
            {"account": account['resource_uri']})


def passwd_cmd(api, args):
    user = get_user(api, args.USERNAME)
    update = {
        "current_password": getpass.getpass('Current Password: '),
        "password": getpass.getpass('New Password: '),
        "password2": getpass.getpass('New Password (confirm): ')
    }
    if update['password'] != update.pop('password2'):
        print("Aborted: passwords do not match")
        exit(1)
    api.put('users', user['id'], update)


def search_cmd(api, args):
    search = args.SEARCH_CRITERIA
    fields = ['username', 'first_name', 'last_name', 'email',
              ('account', 'profile.account.name')]
    results = list(api.search('users', fields, search, expand=EXPANDS))
    if not results:
        print("No Results For:", *search)
        exit(1)
    show_cmd(api, args, users=results)


def bundle_user(user):
    user['name'] = '%(first_name)s %(last_name)s' % user
    user['roles'] = ', '.join(x['role']['name']
                              for x in user['authorizations']
                              if x['role']['id'] != '4')
    return user


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
