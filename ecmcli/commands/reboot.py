"""
Reboot connected router(s).
"""

from . import base


class Reboot(base.ECMCommand):
    """ Reboot connected router(s). """

    name = 'reboot'

    def setup_args(self, parser):
        parser.add_argument('idents', metavar='ROUTER_ID_OR_NAME', nargs='*')
        parser.add_argument('-f', '--force', action='store_true')

    def run(self, args):
        if args.idents:
            routers = map(self.api.get_by_id_or_name, args.idents)
        else:
            routers = self.api.get_pager('routers')
        for x in routers:
            if not args.force and \
               not base.confirm("Reboot %s (%s)" % (x['name'], x['id']),
                                exit=False):
                continue
            print("Rebooting: %s (%s)" % (x['name'], x['id']))
            self.api.put('remote', '/control/system/reboot', 1, timeout=0,
                         id=x['id'])

command_classes = [Reboot]
