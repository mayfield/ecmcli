"""
View and edit authorizations along with managing collaborations.
"""

import collections
import shellish
from . import base


class Common(object):
    """ Mixin of common stuff. """

    def add_auth_argument(self):
        self.add_argument('authid', metavar='ID',
                          complete=self.make_completer('authorizations', 'id'))


class List(Common, base.ECMCommand):
    """ List authorizations. """

    name = 'ls'
    expands = (
        'account',
        'role',
        'user.profile.account',
        'securitytoken.account'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        check = '<b>%s</b>' % shellish.beststr('✓', '*')
        self.verbose_fields = collections.OrderedDict((
            ('id', 'ID'),
            (self.trustee_acc, 'Beneficiary (user/token)'),
            (self.orig_account_acc, 'Originating Account'),
            ('role.name', 'Role'),
            ('account.name', 'Rights on (account)'),
            (lambda x: check if x['cascade'] else '', 'Cascades'),
            (lambda x: check if not x['active'] else '', 'Inactive'),
        ))
        self.terse_fields = collections.OrderedDict((
            ('id', 'ID'),
            (self.trustee_acc, 'Beneficiary (user/token)'),
            ('role.name', 'Role'),
            ('account.name', 'Rights on (account)'),
            (lambda x: check if not x['active'] else '', 'Inactive'),
        ))

    def trustee_acc(self, row):
        """ Show the username@account or securitytoken@account. """
        try:
            return row['user.username']
        except KeyError:
            try:
                return row['securitytoken.label']
            except KeyError:
                return '<unassigned>'

    def orig_account_acc(self, row):
        """ Show the originating account. This is where the user/token hails
        from. """
        if 'user.username' in row:
            try:
                return row['user.profile.account.name']
            except KeyError:
                return '(%s)' % row['user.profile.account'].split('/')[-2]
        else:
            try:
                return row['securitytoken.account.name']
            except KeyError:
                try:
                    return '(%s)' % row['securitytoken.account'].split('/')[-2]
                except KeyError:
                    return '<unassigned>'

    def setup_args(self, parser):
        self.add_user_argument('--beneficiary', help='Limit display to this '
                               'beneficiary.')
        self.add_role_argument('--role', help='Limit display to this role.')
        self.add_account_argument('--rights-on', help='Limit display to '
                                  'records affecting this account.')
        self.add_argument('--inactive', action='store_true',
                          help='Limit display to inactive records.')
        self.add_argument('--verbose', '-v', action='store_true')
        self.inject_table_factory()
        super().setup_args(parser)

    def run(self, args):
        filters = {}
        if args.beneficiary:
            beni = args.beneficiary
            filters['_or'] = 'user__username=%s|securitytoken.label=%s' % (
                             beni, beni)
        if args.role:
            filters['role__name'] = args.role
        if args.rights_on:
            filters['account__name'] = args.rights_on
        if args.inactive:
            filters['active'] = False
        auths = self.api.get_pager('authorizations',
                                   expand=','.join(self.expands), **filters)
        fields = self.terse_fields if not args.verbose else self.verbose_fields
        with self.make_table(headers=fields.values(),
                             accessors=fields.keys()) as t:
            t.print(map(dict, map(base.totuples, auths)))


class Delete(Common, base.ECMCommand):
    """ Delete an authorization. """

    name = 'rm'
    use_pager = False

    def setup_args(self, parser):
        self.add_auth_argument()
        self.add_argument('-f', '--force', action="store_true")
        super().setup_args(parser)

    def format_auth(self, auth):
        if auth['user']:
            try:
                beni = auth['user']['username']
            except TypeError:
                beni = '(%s)' % auth['user'].split('/')[-2]
        elif auth['securitytoken']:
            try:
                beni = auth['securitytoken']['label']
            except TypeError:
                beni = '(%s)' % auth['securitytoken'].split('/')[-2]
        else:
            beni = '<unassigned>'
        try:
            rights_on = auth['account']['name']
        except TypeError:
            rights_on = '(%s)' % auth['account'].split('/')[-2]
        return '%s [%s -> %s]' % (auth['id'], beni, rights_on)

    def run(self, args):
        auth = self.api.get_by('id', 'authorizations', args.authid,
                               expand='user,securitytoken,account')
        if not args.force:
            self.confirm('Delete authorization: %s' % self.format_auth(auth))
        self.api.delete('authorizations', auth['id'])


class Create(Common, base.ECMCommand):
    """ Create a new authorization. """

    name = 'create'
    use_pager = False

    def setup_args(self, parser):
        beni = parser.add_mutually_exclusive_group()
        self.add_user_argument('--beneficiary-user', parser=beni,
                               help='Username to benefit.')
        self.add_argument('--beneficiary-token', parser=beni, type=int,
                          help='Security token ID to benefit.')
        self.add_role_argument('--role', help='Role for the beneficiary.')
        self.add_account_argument('--rights-on', help='Account bestowing '
                                  'rights to.')
        self.add_argument('--no-cascade', action='store_true')
        self.add_argument('--foreign', action='store_true', help='Create an '
                          'authorization for a foreign user. Sometimes '
                          'referred to as a collaborator request.')
        super().setup_args(parser)

    def run(self, args):
        new = {
            "cascade": not args.no_cascade
        }
        foreign = args.foreign
        user = args.beneficiary_user
        token = args.beneficiary_token
        if foreign and token:
            raise SystemExit("Foreign authorizations only work with users.")
        if not user and not token:
            if foreign:
                user = input("Enter collaborator beneficiary username: ")
                if not user:
                    raise SystemExit("User Required")
            else:
                user = input("Enter beneficiary username (<enter> to skip): ")
                if not user:
                    token = input("Enter beneficiary token ID: ")
                    if not token:
                        raise SystemExit("User or Token Required")
        if user:
            if foreign:
                new['username'] = user
            else:
                user = self.api.get_by('username', 'users', user)
                new['user'] = user['resource_uri']
        elif token:
            token = self.api.get_by('id', 'securitytokens', token)
            new['securitytoken'] = token['resource_uri']
        role = args.role or input('Role: ')
        new['role'] = self.api.get_by_id_or_name('roles', role)['resource_uri']
        rights_on = args.rights_on or input('Account (rights on): ')
        new['account'] = self.api.get_by_id_or_name('accounts',
                                                    rights_on)['resource_uri']
        resource = 'authorizations' if not foreign else \
                   'foreign_authorizations'
        self.api.post(resource, new)


class Edit(Common, base.ECMCommand):
    """ Edit authorization attributes. """

    name = 'edit'

    def setup_args(self, parser):
        self.add_auth_argument()
        self.add_role_argument('--role')
        self.add_account_argument('--account')
        cascade = parser.add_mutually_exclusive_group()
        self.add_argument('--cascade', action='store_true', parser=cascade,
                          help="Permit beneficiary rights to subaccounts.")
        self.add_argument('--no-cascade', action='store_true', parser=cascade)
        active = parser.add_mutually_exclusive_group()
        self.add_argument('--activate', action='store_true', parser=active,
                          help="Activate the authorization.")
        self.add_argument('--deactivate', action='store_true', parser=active,
                          help="Deactivate the authorization.")
        super().setup_args(parser)

    def run(self, args):
        auth = self.api.get_by('id', 'authorizations', args.authid)
        updates = {}
        if args.role:
            role = self.api.get_by_id_or_name('roles', args.role)
            updates['role'] = role['resource_uri']
        if args.cascade:
            updates['cascade'] = True
        elif args.no_cascade:
            updates['cascade'] = False
        if args.activate:
            updates['active'] = True
        elif args.deactivate:
            updates['active'] = False
        if args.account:
            role = self.api.get_by_id_or_name('accounts', args.role)
            updates['account'] = role['resource_uri']
        if updates:
            self.api.put('authorizations', auth['id'], updates)


class RoleExamine(base.ECMCommand):
    """ Examine the permissions of a role. """

    name = 'examine'
    method_colors = {
        'get': 'green',
        'put': 'magenta',
        'post': 'magenta',
        'patch': 'magenta',
        'delete': 'red'
    }

    def setup_args(self, parser):
        self.add_role_argument()
        self.add_argument('--resources', nargs='+', help='Limit display to '
                          'these resource(s).')
        self.add_argument('--methods', metavar="METHOD", nargs='+',
                          help='Limit display to resources permitted to use '
                          'these method(s).')
        self.inject_table_factory()
        super().setup_args(parser)

    def color_code(self, method):
        color = self.method_colors.get(method.lower(), 'yellow')
        return '<%s>%s</%s>' % (color, method, color)

    def run(self, args):
        """ Unroll perms for a role. """
        role = self.api.get_by_id_or_name('roles', args.ident,
                                          expand='permissions')
        if args.methods:
            methods = set(x.lower() for x in args.methods)
        rights = collections.defaultdict(dict)
        operations = set()
        for x in role['permissions']:
            res = x['subject']
            op = x['operation']
            if args.resources and res not in args.resources:
                continue
            if args.methods and op not in methods:
                continue
            operations |= {op}
            rights[res]['name'] = res
            rights[res][op] = self.color_code(op.upper())
        title = 'Permissions for: %s (%s)' % (role['name'], role['id'])
        headers = ['API Resource'] + ([''] * len(operations))
        accessors = ['name'] + sorted(operations)
        with self.make_table(title=title, headers=headers,
                             accessors=accessors) as t:
            t.print(sorted(rights.values(), key=lambda x: x['name']))


class Roles(base.ECMCommand):
    """ View authorization roles.

    List the available roles in the system or examine the exact permissions
    provided by a given role. """

    name = 'roles'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(RoleExamine)
        self.fields = collections.OrderedDict((
            ('id', 'ID'),
            ('name', 'Name'),
            ('get', 'GETs'),
            ('put', 'PUTs'),
            ('post', 'POSTs'),
            ('delete', 'DELETEs'),
            ('patch', 'PATCHes'),
        ))

    def setup_args(self, parser):
        self.inject_table_factory()
        super().setup_args(parser)

    def run(self, args):
        operations = set()
        roles = list(self.api.get_pager('roles', expand='permissions'))
        for x in roles:
            counts = collections.Counter(xx['operation']
                                         for xx in x['permissions'])
            operations |= set(counts)
            x.update(counts)
        ops = sorted(operations)
        headers = ['ID', 'Name'] + ['%ss' % x.upper() for x in ops]
        accessors = ['id', 'name'] + ops
        with self.make_table(headers=headers, accessors=accessors) as t:
            t.print(roles)


class Authorizations(base.ECMCommand):
    """ View and edit authorizations.

    Authorizations control who has access to an account(s) along with the
    role/permissions for that access.  A `collaborator` authorization may also
    be granted to external users to provide access to local resources from
    users outside your own purview.  This may be used for handling support or
    other cases where you want to temporarily grant access to a 3rd party. """

    name = 'authorizations'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(List, default=True)
        self.add_subcommand(Delete)
        self.add_subcommand(Create)
        self.add_subcommand(Edit)
        self.add_subcommand(Roles)

command_classes = [Authorizations]
