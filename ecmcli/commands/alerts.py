"""
Analyze and Report ECM Alerts.
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


class Alerts(base.ECMCommand):
    """ Analyze and Report ECM Alerts """

    name = 'alerts'

    def setup_args(self, parser):
        self.add_subcommand(List, default=True)
        self.add_subcommand(Summary)
        self.add_subcommand(Webhook)


class List(base.ECMCommand):
    """ Analyze and Report ECM Alerts """

    name = 'ls'

    def setup_args(self, parser):
        self.inject_table_factory()
        super().setup_args(parser)

    def run(self, args):
        fields = collections.OrderedDict((
            ('Type', 'type'),
            ('Info', 'friendly_info'),
            ('Time', lambda x: ui.formatdatetime(ui.localize_dt(
                x['detected_at'])))
        ))
        with self.make_table(headers=fields.keys(),
                             accessors=fields.values()) as t:
            t.print(self.api.get_pager('router_alerts',
                                       order_by='-created_at_timeuuid'))


class Summary(base.ECMCommand):
    """ Analyze and Report ECM Alerts """

    name = 'summary'

    def setup_args(self, parser):
        self.inject_table_factory()
        super().setup_args(parser)

    def run(self, args):
        by_type = collections.OrderedDict()
        alerts = self.api.get_pager('router_alerts',
                                    order_by='-created_at_timeuuid')
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


class Webhook(base.ECMCommand):
    """ Monitor for new events and post them to a webhook. """

    name = 'webhook'

    def setup_args(self, parser):
        super().setup_args(parser)

    def run(self, args):
        by_type = collections.OrderedDict()
        alerts = self.api.get_pager('router_alerts',
                                    order_by='-created_at_timeuuid')
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


command_classes = [Alerts]
