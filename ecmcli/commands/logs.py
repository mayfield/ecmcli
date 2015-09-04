"""
Download router logs from ECM.
"""

from . import base


class Logs(base.ECMCommand):
    """ Show or clear router logs. """

    name = 'logs'
    levels = ['debug', 'info', 'warning', 'error', 'critical']

    def setup_args(self, parser):
        parser.add_argument('idents', metavar='ROUTER_ID_OR_NAME', nargs='*')
        parser.add_argument('--clear', action='store_true', help="Clear logs")
        parser.add_argument('-l', '--level', choices=self.levels)

    def run(self, args):
        if args.idents:
            routers = map(self.api.get_by_id_or_name, args.idents)
        else:
            routers = self.api.get_pager('routers')
        if args.clear:
            self.clear(args, routers)
        else:
            self.view(args, routers)

    def clear(self, args, routers):
        for rinfo in routers:
            print("Clearing logs for: %s (%s)" % (rinfo['name'], rinfo['id']))
            self.api.delete('logs', rinfo['id'])

    def view(self, args, routers):
        filters = {}
        if args.level:
            filters['levelname'] = args.level.upper()
        for rinfo in routers:
            print("Logs for: %s (%s)" % (rinfo['name'], rinfo['id']))
            for x in self.api.get_pager('logs', rinfo['id'], **filters):
                x['mac'] = rinfo['mac']
                print('%(timestamp)s [%(mac)s] [%(levelname)8s] '
                      '[%(source)18s] %(message)s' % x)

command_classes = [Logs]
