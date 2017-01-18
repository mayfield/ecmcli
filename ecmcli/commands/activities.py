"""
Activity Log
"""

import collections
import humanize
import shellish
import sys
from . import base
from .. import ui


def since(dt):
    """ Return humanized time since for an absolute datetime. """
    since = dt.now(tz=dt.tzinfo) - dt
    return humanize.naturaltime(since)[:-4]


class Activities(base.ECMCommand):
    """ ECM Activity Log """

    name = 'activities'

    def setup_args(self, parser):
        self.add_subcommand(List, default=True)
        self.add_subcommand(Webhook)


class List(base.ECMCommand):
    """ Show activity log entries. """

    name = 'ls'

    def setup_args(self, parser):
        self.inject_table_factory()
        super().setup_args(parser)

    def run(self, args):
        fields = collections.OrderedDict((
            ('Actor', 'actor_id'),
            ('Actor Type', 'actor_type'),
            ('Object', 'object_id'),
            ('Object Type', 'object_type'),
            ('Activity Type', 'activity_type'),
            ('Time', lambda x: ui.formatdatetime(ui.localize_dt(x['created_at'])))
        ))
        with self.make_table(headers=fields.keys(),
                             accessors=fields.values()) as t:
            t.print(self.api.get_pager('activity_logs',
                                       order_by='-created_at_timeuuid'))


class Webhook(base.ECMCommand):
    """ Monitor for new events and post them to a webhook. """

    name = 'webhook'

    def setup_args(self, parser):
        super().setup_args(parser)

    def run(self, args):
        by_type = collections.OrderedDict()
        alerts = self.api.get_pager('router_alerts', order_by='-created_at_timeuuid')
        if sys.stdout.isatty():
            msg = 'Collecting alerts: '
            alerts = shellish.progressbar(alerts, prefix=msg, clear=True)
        for i, x in enumerate(alerts, 1):
            try:
                ent = by_type[x['alert_type']]
            except KeyError:
                ent = by_type[x['alert_type']] = {
                    "records": [x],
                    "newest": x['created_ts'],
                    "oldest": x['created_ts'],
                }
            else:
                ent['records'].append(x),
                ent['oldest'] = x['created_ts']
        headers = ['Alert Type', 'Count', 'Most Recent', 'Oldest']
        with self.make_table(headers=headers) as t:
            t.print((name, len(x['records']), since(x['newest']),
                     since(x['oldest'])) for name, x in by_type.items())


command_classes = [Activities]
