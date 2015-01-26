"""
Collect two samples of wan usage to calculate the bit/sec rate.
"""

import argparse
import humanize
import time

DEF_SAMPLE_DELAY = 1

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('-s', '--sampletime', help='How long to wait between '
                    'sample captures in seconds', default=DEF_SAMPLE_DELAY)


def command(api, args, routers):
    rfilter = {
        "id__in": ','.join(routers)
    }
    while True:
        start = time.time()
        # XXX: We should calculate our own bps instead of using 'bps' to
        # ensure the resolution of our rate correlates with our sampletime.
        data = api.get('remote/status/wan/stats/bps', **rfilter)
        time.sleep(max(0, args.sampletime - (time.time() - start)))
        row = []
        for x in data:
            name = '%s(%s)' % (routers[str(x['id'])]['name'], x['id'])
            if x['success']:
                value = humanize.naturalsize(x['data'], binary=True)
            else:
                value = '[%s]' % x['reason']
            row.append("%38s" % ('%s: %s' % (name, value)))
        print(', '.join(row))
