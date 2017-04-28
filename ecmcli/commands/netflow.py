"""
Monitor live network flow of one or more devices.
"""

import collections
from . import base


class Monitor(base.ECMCommand):
    """ Monitor live network flows. """

    name = 'monitor'
    use_pager = False

    def setup_args(self, parser):
        self.add_router_argument('idents', nargs='*')
        self.inject_table_factory()

    def run(self, args):
        filters = {
            "state": 'online',
            "product__series": 3
        }
        if args.idents:
            routers = [self.api.get_by_id_or_name('routers', x)
                       for x in args.idents]
            filters["id__in"] = ','.join(x['id'] for x in routers)
        fields = collections.OrderedDict((
            ("flow.start", self.flow_start_acc),
            ("flow.end", self.flow_end_acc),
            ("ip.daddr", 'orig.ip.daddr'),
            ("ip.protocol", 'orig.ip.protocol'),
            ("ip.saddr", 'orig.ip.saddr'),
            ("ip.dport", 'orig.ip.dport'),
            ("ip.sport", 'orig.ip.sport'),
            ("raw.pktcount", 'orig.raw.pktcount'),
            ("raw.pktlen", 'orig.raw.pktlen'),
        ))
        flows = collections.OrderedDict()

        res = self.api.put('remote', 'control/netflow/ulog/enable', True,
                           **filters)
        print('resd', res)
        print('resd', res)
        print('resd', res)
        while True:
            for x in self.api.remote('control.netflow.ulog.data', **filters):
                print('sx', x)

            with self.make_table(headers=fields.keys(),
                                 accessors=fields.values()) as t:
                t.print(flows)

    def flow_start_acc(self, record):
        return float('%s.%s' % (record['flow.start.sec'],
                                record['flow.start.usec']))

    def flow_end_acc(self, record):
        return float('%s.%s' % (record['flow.end.sec'],
                                record['flow.end.usec']))


class Netflow(base.ECMCommand):

    name = 'netflow'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(Monitor, default=True)

command_classes = [Netflow]
