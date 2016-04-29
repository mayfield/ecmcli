"""
View and edit features (bindings) along with managing collaborations.
"""

import collections
import shellish
from . import base
from .. import ui


class Common(object):
    """ Mixin of common stuff. """

    def add_ident_argument(self):
        self.add_argument('featureid', metavar='ID',
                          complete=self.make_completer('featurebindings',
                                                       'id'))


class List(Common, base.ECMCommand):
    """ List features. """

    name = 'ls'
    expands = (
        'account',
        'feature',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        check = '<b>%s</b>' % shellish.beststr('✓', '*')
        self.verbose_fields = collections.OrderedDict((
            ('id', 'ID'),
            (self.feature_title_acc, 'Name'),
            ('feature.version', 'Version'),
            (lambda x: ui.time_since(x['created']), 'Age'),
            ('account.name', 'Account'),
            ('feature.category', 'Category'),
            (lambda x: check if x['enabled'] else '', 'Enabled'),
            (lambda x: check if x['locked'] else '', 'Locked'),
            (lambda x: check if x['tos_accepted'] else '', 'TOS Accepted'),

        ))
        self.terse_fields = collections.OrderedDict((
            ('id', 'ID'),
            (self.feature_title_acc, 'Name'),
            (lambda x: ui.time_since(x['created']), 'Age'),
            ('feature.category', 'Category'),
            (lambda x: check if x['enabled'] else '', 'Enabled'),
            (lambda x: check if x['tos_accepted'] else '', 'TOS Accepted'),
        ))

    def setup_args(self, parser):
        self.add_argument('-a', '--all', action='store_true', help='Show '
                          'internal features too.')
        self.add_argument('--verbose', '-v', action='store_true')
        self.inject_table_factory()
        super().setup_args(parser)

    def run(self, args):
        filters = {}
        if not args.all:
            filters['feature.category__nin'] = 'internal'
        features = self.api.get_pager('featurebindings',
                                      expand=','.join(self.expands), **filters)
        fields = self.terse_fields if not args.verbose else self.verbose_fields
        with self.make_table(headers=fields.values(),
                             accessors=fields.keys()) as t:
            t.print(map(dict, map(base.totuples, features)))

    def feature_title_acc(self, row):
        return row['feature.title'] or row['feature.name']


class Delete(Common, base.ECMCommand):
    """ Delete a feature """

    name = 'rm'
    use_pager = False

    def setup_args(self, parser):
        self.add_ident_argument()
        self.add_argument('-f', '--force', action="store_true")
        super().setup_args(parser)

    def run(self, args):
        binding = self.api.get_by('id', 'featurebindings', args.featureid,
                                  expand='feature')
        if not args.force:
            self.confirm('Delete feature (binding): %s (%s)' % (
                         binding['feature']['name'], binding['id']))
        self.api.delete('featurebindings', binding['id'])


class Routers(Common, base.ECMCommand):
    """ List routers bound to a feature. """

    name = 'routers'

    def setup_args(self, parser):
        self.add_ident_argument()
        self.inject_table_factory()
        super().setup_args(parser)

    def run(self, args):
        feature = self.api.get_by('id', 'featurebindings', args.featureid)
        routers = self.api.get(urn=feature['routers'])
        fields = collections.OrderedDict((
            ('id', 'ID'),
            ('name', 'Name'),
        ))
        with self.make_table(headers=fields.values(),
                             accessors=fields.keys()) as t:
            t.print(routers)


class AddRouter(Common, base.ECMCommand):
    """ Add router to a feature. """

    name = 'addrouter'

    def setup_args(self, parser):
        self.add_ident_argument()
        self.add_router_argument('router')
        super().setup_args(parser)

    def run(self, args):
        router = self.api.get_by_id_or_name('routers', args.router)
        self.api.post('featurebindings', args.featureid, 'routers',
                      [router['resource_uri']])


class RemoveRouter(Common, base.ECMCommand):
    """ Remove router from a feature. """

    name = 'removerouter'

    def setup_args(self, parser):
        self.add_ident_argument()
        self.add_router_argument('router')
        super().setup_args(parser)

    def run(self, args):
        router = self.api.get_by_id_or_name('routers', args.router)
        self.api.delete('featurebindings', args.featureid, 'routers',
                        data=[router['resource_uri']])


class Features(base.ECMCommand):
    """ View and edit features (bindings).

    For features that have router bindings or other settings those can be
    managed with these commands too. """

    name = 'features'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(List, default=True)
        self.add_subcommand(Delete)
        self.add_subcommand(Routers)
        self.add_subcommand(AddRouter)
        self.add_subcommand(RemoveRouter)

command_classes = [Features]
