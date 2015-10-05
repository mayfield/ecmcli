"""
Collect two samples of wan usage to calculate the bit/sec rate.
"""

import humanize
import time
from . import base


class WanRate(base.ECMCommand):
    """ Show the current WAN bitrate of connected routers. """

    name = 'wanrate'
    sample_delay = 1

    def setup_args(self, parser):
        self.add_router_argument('idents', nargs='+')
        self.add_argument('-s', '--sampletime',
                          help='How long to wait between sample captures '
                          'in seconds', type=float,
                          default=self.sample_delay)

    def run(self, args):
        routers = [self.api.get_by_id_or_name('routers', x)
                   for x in args.idents]
        routers_by_id = dict((x['id'], x) for x in routers)
        headers = ['%s (%s)' % (x['name'], x['id']) for x in routers]
        table = self.tabulate([headers], flex=False)
        while True:
            start = time.time()
            # XXX: We should calculate our own bps instead of using 'bps' to
            # ensure the resolution of our rate correlates with our sampletime.
            data = self.api.get('remote', '/status/wan/stats/bps',
                                id__in=','.join(routers_by_id))
            time.sleep(max(0, args.sampletime - (time.time() - start)))
            for x in data:
                if x['success']:
                    if x['data'] > 1024:
                        value = humanize.naturalsize(x['data'], gnu=True, format='%.1f ') + 'bps'
                    else:
                        value = '%s bps' % x['data']
                    value = value.lower()
                else:
                    value = '[%s]' % x['reason']
                routers_by_id[str(x['id'])]['bps'] = value
            table.print_row([x['bps'] for x in routers])

command_classes = [WanRate]
