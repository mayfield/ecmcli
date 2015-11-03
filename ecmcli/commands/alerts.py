"""
Analyze and Report ECM Alerts.
"""

import collections
import humanize
import sys
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
        is_terminal = sys.stdout.isatty()
        if is_terminal:
            msg = "Collecting new alerts: %%d/%d" % alerts.meta['total_count']
            print(msg % 0)
        for i, x in enumerate(alerts, 1):
            print(msg % i)
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
