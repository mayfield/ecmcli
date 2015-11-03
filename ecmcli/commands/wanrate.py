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
    use_pager = False

    def setup_args(self, parser):
        self.add_router_argument('idents', nargs='*')
        self.add_argument('-s', '--sampletime',
                          help='How long to wait between sample captures '
                          'in seconds', type=float,
                          default=self.sample_delay)
        self.inject_table_factory(format_excludes={'json'})
        super().setup_args(parser)

    def run(self, args):
        if args.idents:
            routers = [self.api.get_by_id_or_name('routers', x)
                       for x in args.idents]
        else:
            routers = list(self.api.get_pager('routers', state='online',
                                              product__series=3))
        routers_by_id = dict((x['id'], x) for x in routers)
        if not routers_by_id:
            raise SystemExit("No valid routers to monitor")
        headers = ['%s (%s)' % (x['name'], x['id']) for x in routers]
        table = self.make_table(headers=headers, flex=False)
        while True:
            start = time.time()
            # XXX: We should calculate our own bps instead of using 'bps' to
            # ensure the resolution of our rate correlates with our
            # sampletime.
            data = self.api.get('remote', 'status/wan/stats/bps',
                                id__in=','.join(routers_by_id))
            time.sleep(max(0, args.sampletime - (time.time() - start)))
            for x in data:
                if x['success']:
                    if x['data'] > 1024:
                        value = humanize.naturalsize(x['data'], gnu=True,
                                                     format='%.1f ') + 'bps'
                    else:
                        value = '%s bps' % x['data']
                    value = value.lower()
                else:
                    value = '[%s]' % x['reason']
                routers_by_id[str(x['id'])]['bps'] = value
            table.print_row([x['bps'] for x in routers])
        table.close()

command_classes = [WanRate]
