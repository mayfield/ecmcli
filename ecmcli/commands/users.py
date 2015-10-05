"""
List/Edit/Manage ECM Users.
"""

import datetime
import getpass
import shellish
from . import base


class Common(object):

    expands = ','.join([
        'authorizations.role',
        'profile.account'
    ])

    def prerun(self, args):
        self.verbose = getattr(args, 'verbose', False)
        self.printer = self.verbose_printer if self.verbose else \
                       self.terse_printer
        super().prerun(args)

    def get_user(self, username):
        user = self.api.get('users', username=username, expand=self.expands)
        if not user:
            raise SystemExit("Invalid username: %s" % username)
        return user[0]

    def splitname(self, fullname):
        name = fullname.rsplit(' ', 1)
        last_name = name.pop() if len(name) > 1 else ''
        return name[0], last_name

    def bundle_user(self, user):
        account = user['profile']['account']
        user['name'] = '%(first_name)s %(last_name)s' % user
        user['roles'] = ', '.join(x['role']['name']
                                  for x in user['authorizations']
                                  if x['role']['id'] != '4')
        user['account_desc'] = '%s (%s)' % (account['name'], account['id'])
        return user

    def verbose_printer(self, users):
        for x in users:
            user = self.bundle_user(x)
            slen = user['profile']['session_length']
            session = datetime.timedelta(seconds=slen)
            print('Username:       ', user['username'])
            print('Full Name:      ', user['name'])
            print('Account:        ', user['account_desc'])
            print('Role(s):        ', user['roles'])
            print('ID:             ', user['id'])
            print('Email:          ', user['email'])
            print('Joined:         ', user['date_joined'])
            print('Last Login:     ', user['last_login'])
            print('Session Length: ', session)
            print()

    def terse_printer(self, users):
        fields = [
            ('username', 'Username'),
            ('name', 'Full Name'),
            ('account_desc', 'Account'),
            ('roles', 'Role(s)'),
            ('id', 'ID'),
            ('email', 'EMail')
        ]
        table = shellish.Table(headers=[x[1] for x in fields],
                               accessors=[x[0] for x in fields])
        table.print(map(self.bundle_user, users))

    def add_username_argument(self, *keys, **options):
        if not keys:
            keys = ('username',)
        options.setdefault("metavar", 'USERNAME')
        return self.add_completer_argument(*keys, resource='users',
                                           res_field='username', **options)


class Show(Common, base.ECMCommand):
    """ Show user info. """

    name = 'show'

    def setup_args(self, parser):
        self.add_username_argument(nargs='?')
        self.add_argument('-v', '--verbose', action='store_true')

    def run(self, args, users=None):
        if users is None:
            if args.username:
                users = [self.get_user(args.username)]
            else:
                users = self.api.get_pager('users', expand=self.expands)
        self.printer(users)


class Create(Common, base.ECMCommand):
    """ Create a new user. """

    name = 'create'
    role_choices = ['admin', 'full', 'readonly']

    def setup_args(self, parser):
        self.add_argument('--email')
        self.add_argument('--password')
        self.add_argument('--fullname')
        self.add_argument('--role', choices=self.role_choices)

    def run(self, args):
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


class Edit(Common, base.ECMCommand):
    """ Edit user attributes. """

    name = 'edit'

    def setup_args(self, parser):
        self.add_username_argument()
        self.add_argument('--email')
        self.add_argument('--fullname')
        self.add_argument('--session_length', type=int)

    def run(self, args):
        user = self.get_user(args.username)
        updates = {}
        if args.fullname:
            first, last = self.splitname(args.fullname)
            updates['first_name'] = first
            updates['last_name'] = last
        if args.email:
            updates['email'] = args.email
        if updates:
            self.api.put('users', user['id'], updates)
        if args.session_length:
            self.api.put('profiles', user['profile']['id'],
                         {"session_length": args.session_length})


class Delete(Common, base.ECMCommand):
    """ Delete a user. """

    name = 'delete'

    def setup_args(self, parser):
        self.add_username_argument('usernames', nargs='+')
        self.add_argument('-f', '--force', action="store_true")

    def run(self, args):
        for username in args.usernames:
            user = self.get_user(username)
            if not args.force and \
               not base.confirm('Delete user: %s' % username, exit=False):
                continue
            self.api.delete('users', user['id'])


class Move(Common, base.ECMCommand):
    """ Move a user to a different account. """

    name = 'move'

    def setup_args(self, parser):
        self.add_username_argument()
        self.add_account_argument('new_account',
                                  metavar='NEW_ACCOUNT_ID_OR_NAME')

    def run(self, args):
        user = self.get_user(args.username)
        account = self.api.get_by_id_or_name('accounts', args.new_account)
        self.api.put('profiles', user['profile']['id'],
                     {"account": account['resource_uri']})


class Passwd(base.ECMCommand):
    """ Change your password. """

    name = 'passwd'

    def run(self, args):
        user = self.api.ident['user']
        update = {
            "current_password": getpass.getpass('Current Password: '),
            "password": getpass.getpass('New Password: '),
            "password2": getpass.getpass('New Password (confirm): ')
        }
        if update['password'] != update.pop('password2'):
            raise SystemExit("Aborted: passwords do not match")
        self.api.put('users', user['id'], update)


class Search(Common, base.ECMCommand):
    """ Search for users. """

    name = 'search'
    fields = ['username', 'first_name', 'last_name', 'email',
              ('account', 'profile.account.name')]

    def setup_args(self, parser):
        searcher = self.make_searcher('users', self.fields)
        self.lookup = searcher.lookup
        self.add_search_argument(searcher)
        self.add_argument('-v', '--verbose', action='store_true')

    def run(self, args):
        results = list(self.lookup(args.search, expand=self.expands))
        if not results:
            raise SystemExit("No results for: %s" % ' '.join(args.search))
        self.printer(results)


class Users(base.ECMCommand):
    """ Manage ECM Users. """

    name = 'users'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(Show, default=True)
        self.add_subcommand(Create)
        self.add_subcommand(Delete)
        self.add_subcommand(Edit)
        self.add_subcommand(Move)
        self.add_subcommand(Passwd)
        self.add_subcommand(Search)

command_classes = [Users]
