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
        messages = list(self.api.get_pager('system_message', type__nexact='tos'))
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
    """ Show authorizations. """

    name = 'list'
    expands = (
        'account',
        'role',
        'user'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields = collections.OrderedDict((
            ('id', 'ID'),
            ('account.name', 'Account'),
            ('cascade', 'Cascade'),
            ('role.name', 'Role'),
            ('user.username', 'Username'),
            ('active', 'Active'),
        ))

    def setup_args(self, parser):
        self.add_table_group()
        self.add_argument('--inactive', action='store_true',
                          help='Only show inactive authorizations.')
        super().setup_args(parser)

    def run(self, args):
        auths = self.api.get_pager('authorizations',
                                   expand=','.join(self.expands))
        with shellish.Table(headers=self.fields.values(),
                            accessors=self.fields.keys(),
                            renderer=args.table_format) as t:
            import pdb
            pdb.set_trace()
            t.print(map(dict(map(base.totuples, auths))))


class Activate(Common, base.ECMCommand):
    """ Activate an authorization.
    This is the way you accept a collaboration invite. """

    name = 'activate'

    def setup_args(self, parser):
        self.add_argument('ident', metavar='ID',
                          complete=self.complete_id)
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

command_classes = [Authorizations]
