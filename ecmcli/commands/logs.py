"""
Download router logs from ECM.
"""

import datetime
import html
import time
from . import base


class Logs(base.ECMCommand):
    """ Show or clear router logs. """

    use_pager = False
    max_follow_sleep = 30
    name = 'logs'
    levels = ['debug', 'info', 'warning', 'error', 'critical']
    level_colors = {
        "debug": 'dim',
        "info": 'blue',
        "warning": 'yellow',
        "error": 'red',
        "critical": 'red'
    }

    def setup_args(self, parser):
        self.add_router_argument('idents', nargs='*')
        self.add_argument('--clear', action='store_true', help="Clear logs")
        self.add_argument('-l', '--level', choices=self.levels)
        self.add_argument('-f', '--follow', action='store_true',
                          help="Follow live logs (online routers only)")
        self.add_argument('-n', '--numlines', type=int, default=20,
                          help="Number of lines to display")
        self.inject_table_factory()

    def table_timestamp_acc(self, record):
        """ Table accessor for log timestamp. """
        dt = datetime.datetime.fromtimestamp(record['timestamp'])
        return '%d:%s' % (dt.hour % 12, dt.strftime('%M:%S %p'))

    def table_levelname_acc(self, record):
        """ Table accessor for colorized log level name. """
        color = self.level_colors[record['levelname'].lower()]
        opentags = ['<%s>' % color]
        closetags = ['</%s>' % color]
        if record['levelname'] == 'CRITICAL':
            opentags.append('<b>')
            closetags.insert(0, '</b>')
        return ''.join(opentags) + record['levelname'] + ''.join(closetags)

    def run(self, args):
        filters = {}
        if args.follow:
            filters['state'] = 'online'
            filters['product__series'] = 3
        if args.idents:
            routers = [self.api.get_by_id_or_name('routers', x, **filters)
                       for x in args.idents]
        else:
            routers = self.api.get_pager('routers', **filters)
        if args.clear:
            self.clear(args, routers)
        else:
            with self.make_table(accessors=(
                self.table_timestamp_acc,
                lambda x: x['router']['name'],
                self.table_levelname_acc,
                'source',
                'message',
                'exc'
            ), columns=(
                {
                    "width": 11,
                    "padding": 1,
                    "align": 'right'
                },
                {
                    "minwidth": 12
                },
                {
                    "minwidth": 5,
                    "padding": 1
                },
                {
                    "minwidth": 6
                },
                None,
                None,
            )) as table:
                if args.follow:
                    self.follow(args, routers, table)
                else:
                    self.view(args, routers, table)

    def clear(self, args, routers):
        for rinfo in routers:
            print("Clearing logs for: %s (%s)" % (rinfo['name'], rinfo['id']))
            self.api.delete('logs', rinfo['id'])

    def view(self, args, routers, table):
        filters = {}
        if args.level:
            filters['levelname'] = args.level.upper()
        for rinfo in routers:
            print("Logs for: %s (%s)" % (rinfo['name'], rinfo['id']))
            for x in self.api.get_pager('logs', rinfo['id'], **filters):
                x['mac'] = rinfo['mac']
                print('%(timestamp)s [%(mac)s] [%(levelname)8s] '
                      '[%(source)18s] %(message)s' % x)

    def follow(self, args, routers, table):
        lastseen = {}
        router_ids = ','.join(x['id'] for x in routers)
        sleep = 0
        while True:
            logs = []
            for router in self.api.remote('status.log', id__in=router_ids):
                if not router['results']:
                    continue
                logdata = router['results'][0]['data']
                logdata.sort(key=lambda x: x[0])
                lastshown = lastseen.get(router['id'])
                offt = -args.numlines
                if lastshown is not None:
                    for offt, x in enumerate(logdata):
                        if x == lastshown:
                            offt += 1
                            break
                    else:
                        raise RuntimeError("Did not find tailing edge")
                updates = logdata[offt:]
                if updates:
                    logs.extend({
                        "router": router['router'],
                        "timestamp": x[0],
                        "levelname": x[1],
                        "source": x[2],
                        "message": x[3] and html.unescape(x[3])
                    } for x in updates)
                    lastseen[router['id']] = logdata[-1]
            if logs:
                logs.sort(key=lambda x: x['timestamp'])
                table.print(logs)
                sleep = 0
            else:
                sleep += 0.200
            time.sleep(min(self.max_follow_sleep, sleep))

command_classes = [Logs]
