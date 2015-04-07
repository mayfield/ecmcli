"""
Collect two samples of wan usage to calculate the bit/sec rate.
"""

import argparse
import humanize
import time

DEF_SAMPLE_DELAY = 1

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('-s', '--sampletime', help='How long to wait between '
                    'sample captures in seconds', type=float,
                    default=DEF_SAMPLE_DELAY)


def command(api, args, routers=None):
    # XXX: This is horribly broken when routers > page_size.
    routers = list(routers)
    rfilter = {
        "id__in": ','.join(x['id'] for x in routers)
    }
    routers_by_id = dict((x['id'], x) for x in routers)
    column_fmt = '%20s'
    header = [column_fmt % ('%s (%s)' % (x['name'], x['id']))
              for x in routers]
    print(', '.join(header))
    while True:
        start = time.time()
        # XXX: We should calculate our own bps instead of using 'bps' to
        # ensure the resolution of our rate correlates with our sampletime.
        data = api.get('remote/status/wan/stats/bps', **rfilter)
        time.sleep(max(0, args.sampletime - (time.time() - start)))
        for x in data:
            if x['success']:
                value = humanize.naturalsize(x['data'], binary=True)
            else:
                value = '[%s]' % x['reason']
            routers_by_id[str(x['id'])]['bps'] = value
        row = [column_fmt % x['bps'] for x in routers]
        print(', '.join(row))
