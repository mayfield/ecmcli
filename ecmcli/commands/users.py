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

    def get_users(self, usernames):
        return self.api.glob_pager('users', username=usernames,
                                   expand=self.expands)

    def get_user(self, username):
        return self.api.get_by('username', 'users', username,
                               expand=self.expands)

    def splitname(self, fullname):
        name = fullname.rsplit(' ', 1)
        last_name = name.pop() if len(name) > 1 else ''
        return name[0], last_name

    def bundle_user(self, user):
        account = user['profile']['account']
        user['name'] = '%(first_name)s %(last_name)s' % user
        user['roles'] = ', '.join(x['role']['name']
                                  for x in user['authorizations']
                                  if not isinstance(x, str) and
                                     x['role']['id'] != '4')
        if isinstance(account, str):
            user['account_desc'] = '(%s)' % account.split('/')[-2]
        else:
            user['account_desc'] = '%s (%s)' % (account['name'],
                                                account['id'])
        slen = user['profile']['session_length']
        user['session'] = datetime.timedelta(seconds=slen)
        return user

    def add_username_argument(self, *keys, **options):
        if not keys:
            keys = ('username',)
        options.setdefault("metavar", 'USERNAME')
        return self.add_completer_argument(*keys, resource='users',
                                           res_field='username', **options)


class Printer(object):

    def setup_args(self, parser):
        self.inject_table_factory()
        super().setup_args(parser)

    def prerun(self, args):
        self.verbose = args.verbose
        self.printer = self.verbose_printer if self.verbose else \
                       self.terse_printer
        super().prerun(args)

    def verbose_printer(self, users):
        fields = [
            ('id', 'ID'),
            ('username', 'Username'),
            ('name', 'Full Name'),
            ('account_desc', 'Account'),
            ('roles', 'Role(s)'),
            ('email', 'EMail'),
            ('date_joined', 'Joined'),
            ('last_login', 'Last Login'),
            ('session', 'Max Session')
        ]
        self.print_table(fields, users)

    def terse_printer(self, users):
        fields = [
            ('id', 'ID'),
            ('username', 'Username'),
            ('name', 'Full Name'),
            ('account_desc', 'Account'),
            ('roles', 'Role(s)'),
            ('email', 'EMail')
        ]
        self.print_table(fields, users)

    def print_table(self, fields, users):
        with self.make_table(headers=[x[1] for x in fields],
                             accessors=[x[0] for x in fields]) as t:
            t.print(map(self.bundle_user, users))


class List(Common, Printer, base.ECMCommand):
    """ List users. """

    name = 'ls'

    def setup_args(self, parser):
        self.add_username_argument('usernames', nargs='*')
        self.add_argument('-v', '--verbose', action='store_true')
        super().setup_args(parser)

    def run(self, args):
        self.printer(self.get_users(args.usernames))


class Create(Common, base.ECMCommand):
    """ Create a new user. """

    name = 'create'
    use_pager = False

    def setup_args(self, parser):
        self.add_argument('--username')
        self.add_argument('--email')
        self.add_argument('--password')
        self.add_argument('--fullname')
        self.add_argument('--role',
                          complete=self.make_completer('roles', 'name'))
        self.add_argument('--account',
                          complete=self.make_completer('accounts', 'name'))
        super().setup_args(parser)

    def username_available(self, username):
        return self.api.get('check_username', username=username)[0]['is_valid']

    def run(self, args):
        while True:
            username = args.username or input('Username: ')
            if not self.username_available(username):
                shellish.vtmlprint("<red>Username unavailable.</red>")
                if args.username:
                    raise SystemExit(1)
            else:
                break
        email = args.email or input('Email: ')
        password = args.password
        if not password:
            password = getpass.getpass('Password (or empty to send email): ')
            if password:
                password2 = getpass.getpass('Confirm Password: ')
                if password != password2:
                    raise SystemExit("Aborted: passwords do not match")
        name = self.splitname(args.fullname or input('Full Name: '))
        role = args.role or input('Role: ')
        role_id = self.api.get_by_id_or_name('roles', role)['id']
        user_data = {
            "username": username,
            "email": email,
            "first_name": name[0],
            "last_name": name[1],
            "password": password,
        }
        if args.account:
            a = self.api.get_by_id_or_name('accounts', args.account)
            user_data['account'] = a['resource_uri']
        user = self.api.post('users', user_data, expand='profile')
        self.api.put('profiles', user['profile']['id'], {
            "require_password_change": not password
        })
        self.api.post('authorizations', {
            "account": user['profile']['account'],
            "cascade": True,
            "role": '/api/v1/roles/%s/' % role_id,
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
        super().setup_args(parser)

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

    name = 'rm'
    use_pager = False

    def setup_args(self, parser):
        self.add_username_argument('usernames', nargs='+')
        self.add_argument('-f', '--force', action="store_true")
        super().setup_args(parser)

    def run(self, args):
        for user in self.get_users(args.usernames):
            if not args.force and \
               not self.confirm('Delete user: %s' % user['username'],
                                exit=False):
                continue
            self.api.delete('users', user['id'])


class Move(Common, base.ECMCommand):
    """ Move a user to a different account. """

    name = 'mv'

    def setup_args(self, parser):
        self.add_username_argument('usernames', nargs='+')
        self.add_account_argument('new_account',
                                  metavar='NEW_ACCOUNT_ID_OR_NAME')
        super().setup_args(parser)

    def run(self, args):
        account = self.api.get_by_id_or_name('accounts', args.new_account)
        for user in self.get_users(args.usernames):
            self.api.put('profiles', user['profile']['id'],
                         {"account": account['resource_uri']})


class Passwd(base.ECMCommand):
    """ Change your password. """

    name = 'passwd'
    use_pager = False

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


class Search(Common, Printer, base.ECMCommand):
    """ Search for users. """

    name = 'search'
    fields = ['username', 'first_name', 'last_name', 'email',
              ('account', 'profile.account.name')]

    def setup_args(self, parser):
        searcher = self.make_searcher('users', self.fields)
        self.lookup = searcher.lookup
        self.add_argument('-v', '--verbose', action='store_true')
        self.add_search_argument(searcher)
        super().setup_args(parser)

    def run(self, args):
        results = self.lookup(args.search, expand=self.expands)
        if not results:
            raise SystemExit("No results for: %s" % ' '.join(args.search))
        self.printer(results)


class Users(base.ECMCommand):
    """ Manage ECM Users. """

    name = 'users'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(List, default=True)
        self.add_subcommand(Create)
        self.add_subcommand(Delete)
        self.add_subcommand(Edit)
        self.add_subcommand(Move)
        self.add_subcommand(Passwd)
        self.add_subcommand(Search)

command_classes = [Users]
