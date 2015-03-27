"""
Anaylize and Report ECM Alerts.
"""

import argparse
import collections
import functools
import html
import humanize
import sys

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('-e', '--expand', action='store_true',
                    help="Expand each alert.")


def command(api, args):
    last_ts = '2000-01-01 00:00+00:00'
    by_type = collections.OrderedDict()
    alerts = api.get_pager('alerts', created_ts__gt=last_ts,
                           order_by='-created_ts')
    msg = "\rCollecting new alerts: %5d"
    print(msg % 0, end='')
    sys.stdout.flush()
    for i, x in enumerate(alerts):
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
    for key, data in by_type.items():
        print('%25s (%5d) newest: %-20s oldest: %-20s' % (key, len(data['records']),
              since(data['newest']),
              since(data['oldest'])))
