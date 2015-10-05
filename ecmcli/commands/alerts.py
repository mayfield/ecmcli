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
        self.add_argument('-e', '--expand', action='store_true',
                          help="Expand each alert")

    def run(self, args):
        by_type = collections.OrderedDict()
        alerts = self.api.get_pager('alerts', page_size=500,
                                    order_by='-created_ts')
        msg = "\rCollecting new alerts: %5d"
        print(msg % 0, end='')
        sys.stdout.flush()
        for i, x in enumerate(alerts, 1):
            print(msg % i, end='')
            sys.stdout.flush()
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
        print()
        data = [('Alert Type', 'Count', 'Most Recent', 'Oldest')]
        data.extend((
            name,
            len(x['records']),
            since(x['newest']),
            since(x['oldest'])
        ) for name, x in by_type.items())
        self.tabulate(data)

command_classes = [Alerts]
