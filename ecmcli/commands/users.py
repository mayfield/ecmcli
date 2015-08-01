"""
List/Edit/Manage ECM Users.
"""

import getpass
from . import base


class Users(base.Command):
    """ Manage ECM Users """

    name = 'users'
    role_choices = ['admin', 'full', 'readonly']
    expands = ','.join([
        'authorizations.role',
        'profile.account'
    ])

    def init_argparser(self):
        parser = base.ArgParser(self.name, subcommands=True)

        p = parser.add_subcommand('show', self.show_cmd, default=True)
        p.add_argument('username', metavar='USERNAME', nargs='?')
        p.add_argument('-v', '--verbose', action='store_true')

        p = parser.add_subcommand('create', self.create_cmd)
        p.add_argument('--email')
        p.add_argument('--password')
        p.add_argument('--fullname')
        p.add_argument('--role', choices=self.role_choices)

        p = parser.add_subcommand('delete', self.delete_cmd)
        p.add_argument('username', metavar='USERNAME', nargs='+')
        p.add_argument('-f', '--force', action="store_true")

        p = parser.add_subcommand('edit', self.edit_cmd)
        p.add_argument('username', metavar='USERNAME')
        p.add_argument('--email')
        p.add_argument('--fullname')

        p = parser.add_subcommand('move', self.move_cmd)
        p.add_argument('username', metavar='USERNAME')
        p.add_argument('new_account', metavar='NEW_ACCOUNT_ID_OR_NAME')

        p = parser.add_subcommand('passwd', self.passwd_cmd)
        p.add_argument('username', metavar='USERNAME')

        p = parser.add_subcommand('search', self.search_cmd)
        p.add_argument('search', metavar='SEARCH_CRITERIA', nargs='+')
        p.add_argument('-v', '--verbose', action='store_true')

        return parser

    def splitname(self, fullname):
        name = fullname.rsplit(' ', 1)
        last_name = name.pop() if len(name) > 1 else ''
        return name[0], last_name

    def prerun(self, args):
        self.verbose = getattr(args, 'verbose', False)
        self.printed_header = False
        self.printer = self.verbose_printer if self.verbose else \
                       self.terse_printer

    def show_cmd(self, args, users=None):
        """ Show users """
        if users is None:
            if args.username:
                users = [self.get_user(args.username)]
            else:
                users = self.api.get_pager('users', expand=self.expands)
        for x in users:
            self.printer(self.bundle_user(x))

    def create_cmd(self, args):
        """ Create a new user """
        username = args.email or input('Email: ')
        password = args.password
        if not password:
            password = getpass.getpass('Password (or empty to send email): ')
            if password:
                password2 = getpass.getpass('Confirm Password: ')
                if password != password2:
                    raise SystemExit("Aborted: passwords do not match")
        name = self.splitname(args.fullname or input('Full Name: '))
        role = args.role or input('Role {%s}: ' % ', '.join(self.role_choices))
        role_id = {
            'admin': 1,
            'full': 2,
            'readonly': 3
        }.get(role)
        if not role_id:
            raise SystemExit("Invalid role selection")
        user = self.api.post('users', {
            "username": username,
            "email": username,
            "first_name": name[0],
            "last_name": name[1],
            "password": password
        }, expand='profile')
        self.api.put('profiles', user['profile']['id'], {
            "require_password_change": not password
        })
        self.api.post('authorizations', {
            "account": user['profile']['account'],
            "cascade": True,
            "role": '/api/v1/roles/%d/' % role_id,
            "user": user['resource_uri']
        })

    def get_user(self, username):
        user = self.api.get('users', username=username, expand=self.expands)
        if not user:
            raise SystemExit("Invalid username: %s" % username)
        return user[0]

    def edit_cmd(self, args):
        """ Edit a user's attributes """
        user = self.get_user(args.username)
        updates = {}
        if args.fullname:
            first, last = self.splitname(args.fullname)
            updates['first_name'] = first
            updates['last_name'] = last
        if args.email:
            updates['email'] = args.email
        self.api.put('users', user['id'], updates)

    def delete_cmd(self, args):
        """ Delete a user """
        for username in args.username:
            user = self.get_user(username)
            if not args.force and \
               not base.confirm('Delete user: %s' % username, exit=False):
                continue
            self.api.delete('users', user['id'])

    def move_cmd(self, args):
        """ Move a user to a different account """
        user = self.get_user(args.username)
        account = self.api.get_by_id_or_name('accounts', args.new_account)
        self.api.put('profiles', user['profile']['id'],
                     {"account": account['resource_uri']})

    def passwd_cmd(self, args):
        """ Change your password """
        user = self.get_user(args.username)
        update = {
            "current_password": getpass.getpass('Current Password: '),
            "password": getpass.getpass('New Password: '),
            "password2": getpass.getpass('New Password (confirm): ')
        }
        if update['password'] != update.pop('password2'):
            raise SystemExit("Aborted: passwords do not match")
        self.api.put('users', user['id'], update)

    def search_cmd(self, args):
        """ Search for users """
        fields = ['username', 'first_name', 'last_name', 'email',
                  ('account', 'profile.account.name')]
        results = list(self.api.search('users', fields, args.search,
                                       expand=self.expands))
        if not results:
            raise SystemExit("No results for: %s" % ' '.join(args.search))
        self.show_cmd(args, users=results)

    def bundle_user(self, user):
        user['name'] = '%(first_name)s %(last_name)s' % user
        user['roles'] = ', '.join(x['role']['name']
                                  for x in user['authorizations']
                                  if x['role']['id'] != '4')
        return user

    def verbose_printer(self, user):
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

    def terse_printer(self, user):
        if not self.printed_header:
            self.printed_header = True
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
        print('%(username)-28s %(name)-23s %(account_desc)-21s %(roles)-17s '
              '%(id)-6s %(email)s' % user)

command_classes = [Users]
