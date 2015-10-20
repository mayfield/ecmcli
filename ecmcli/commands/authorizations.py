"""
View and edit authorizations along with setup collaborations with others.
"""

import collections
import functools
import humanize
import shellish
from . import base


class Common(object):

    def get_messages(self):
        """ Combine system and user message streams. """
        messages = list(self.api.get_pager('system_message',
                                           type__nexact='tos'))
        messages.extend(self.api.get_pager('user_messages'))
        messages.sort(key=lambda x: x['created'], reverse=True)
        return messages

    @functools.lru_cache()
    def get_user(self, user_urn):
        return self.api.get(urn=user_urn)

    def humantime(self, dt):
        if dt is None:
            return ''
        since = dt.now(tz=dt.tzinfo) - dt
        return humanize.naturaltime(since)


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
        self.add_argument('--inactive', action='store_true',
                          help='Only show inactive authorizations.')
        self.add_argument('--verbose', '-v', action='store_true')
        self.inject_table_factory()
        super().setup_args(parser)

    def run(self, args):
        auths = self.api.get_pager('authorizations',
                                   expand=','.join(self.expands))
        fields = self.terse_fields if not args.verbose else self.verbose_fields
        with self.make_table(headers=fields.values(),
                             accessors=fields.keys()) as t:
            t.print(map(dict, map(base.totuples, auths)))


class Roles(Common, base.ECMCommand):
    """ Describe a role's permissions. """

    name = 'role'
    expands = (
        'permissions',
    )

    def setup_args(self, parser):
        self.add_argument('roles', nargs='*',
                          complete=self.make_completer('roles', 'name'))
        self.add_argument('--verbose', '-v', action='store_true')
        self.inject_table_factory()
        super().setup_args(parser)

    def run(self, args):
        auths = self.api.get_pager('roles',
                                   expand=','.join(self.expands))
        shellish.tabulate(auths)  # XXX not using table factory


class Activate(Common, base.ECMCommand):
    """ Activate an authorization.
    This is the way you accept a collaboration invite. """

    name = 'activate'

    def setup_args(self, parser):
        self.add_argument('ident', metavar='ID',
                          complete=self.make_completer('authorizations', 'id'))
                          #complete=self.complete_id)
        super().setup_args(parser)

    @shellish.ttl_cache(60)
    def cached_auths(self):
        return frozenset(x['id']
                         for x in self.api.get_pager('authorizations'))

    def complete_id(self, prefix, args):
        return set(x for x in self.cached_auths()
                   if x.startswith(prefix))

    def run(self, args):
        self.api.put('authorizations', args.ident, dict(active=True))


class Authorizations(base.ECMCommand):
    """ Read/Acknowledge any messages from the system. """

    name = 'authorizations'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(List, default=True)
        self.add_subcommand(Activate)
        self.add_subcommand(Roles)

command_classes = [Authorizations]
