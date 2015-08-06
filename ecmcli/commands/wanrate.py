"""
Collect two samples of wan usage to calculate the bit/sec rate.
"""

from . import base
import humanize
import time


class WanRate(base.Command):
    """ Show the current WAN bitrate of connected routers. """

    name = 'wanrate'
    sample_delay = 1

    def setup_args(self, parser):
        parser.add_argument('idents', metavar='ROUTER_ID_OR_NAME', nargs='+')
        parser.add_argument('-s', '--sampletime',
                            help='How long to wait between sample captures '
                            'in seconds', type=float,
                            default=self.sample_delay)

    def run(self, args):
        routers = [self.api.get_by_id_or_name('routers', x)
                   for x in args.idents]
        routers_by_id = dict((x['id'], x) for x in routers)
        column_fmt = '%20s'
        header = [column_fmt % ('%s (%s)' % (x['name'], x['id']))
                  for x in routers]
        print(', '.join(header))
        while True:
            start = time.time()
            # XXX: We should calculate our own bps instead of using 'bps' to
            # ensure the resolution of our rate correlates with our sampletime.
            data = self.api.get('remote', '/status/wan/stats/bps',
                                id__in=','.join(routers_by_id))
            time.sleep(max(0, args.sampletime - (time.time() - start)))
            for x in data:
                if x['success']:
                    value = humanize.naturalsize(x['data'], binary=True)
                else:
                    value = '[%s]' % x['reason']
                routers_by_id[str(x['id'])]['bps'] = value
            row = [column_fmt % x['bps'] for x in routers]
            print(', '.join(row))

command_classes = [WanRate]
