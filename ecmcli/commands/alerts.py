"""
Analyze and Report ECM Alerts.
"""

import collections
import humanize
import shellish
from . import base


def since(dt):
    """ Return humanized time since for an absolute datetime. """
    since = dt.now(tz=dt.tzinfo) - dt
    return humanize.naturaltime(since)[:-4]


class Alerts(base.ECMCommand):
    """ Analyze and Report ECM Alerts """

    name = 'alerts'

    def setup_args(self, parser):
        self.inject_table_factory()
        super().setup_args(parser)

    def run(self, args):
        by_type = collections.OrderedDict()
        alerts = self.api.get_pager('alerts', page_size=500,
                                    order_by='-created_ts')
        if shellish.is_terminal():
            msg = "\rCollecting new alerts: %5d"
            print(msg % 0, end='', flush=True)
        for i, x in enumerate(alerts, 1):
            if shellish.is_terminal():
                print(msg % i, end='', flush=True)
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
        if shellish.is_terminal():
            print()
        headers = ['Alert Type', 'Count', 'Most Recent', 'Oldest']
        with self.make_table(headers=headers) as t:
            t.print((name, len(x['records']), since(x['newest']),
                     since(x['oldest'])) for name, x in by_type.items())

command_classes = [Alerts]
