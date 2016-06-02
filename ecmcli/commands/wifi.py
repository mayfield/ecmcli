"""
WiFi commands.
"""

import collections
import shellish
from . import base
from .. import ui


class AccessPoints(base.ECMCommand):
    """ List access points seen by site surveys. """

    name = 'aps'

    def setup_args(self, parser):
        self.add_router_argument('idents', nargs='*')
        self.add_argument('-v', '--verbose', action='store_true', help='More '
                          'verbose display.')
        self.inject_table_factory()
        super().setup_args(parser)

    def run(self, args):
        if args.idents:
            ids = ','.join(self.api.get_by_id_or_name('routers', x)['id']
                           for x in args.idents)
            filters = {"survey__router__in": ids}
        else:
            filters = {}
        check = '<b>%s</b>' % shellish.beststr('✓', '*')
        if args.verbose:
            fields = collections.OrderedDict((
                ('SSID', 'wireless_ap.ssid'),
                ('BSSID', 'wireless_ap.bssid'),
                ('Manufacturer', 'wireless_ap.manufacturer'),
                ('Band', 'survey.band'),
                ('Mode', 'wireless_ap.mode'),
                ('Auth', 'wireless_ap.authmode'),
                ('Channel', 'survey.channel'),
                ('RSSI', 'survey.rssi'),
                ('First Seen', lambda x: ui.time_since(x['survey.created'])),
                ('Last Seen', lambda x: ui.time_since(x['survey.updated'])),
                ('Seen By', 'survey.router.name'),
                ('Trusted', lambda x: check if x['trust.trusted'] else ''),
            ))
        else:
            fields = collections.OrderedDict((
                ('SSID', 'wireless_ap.ssid'),
                ('Manufacturer', 'wireless_ap.manufacturer'),
                ('Band', 'survey.band'),
                ('Auth', 'wireless_ap.authmode'),
                ('Last Seen', lambda x: ui.time_since(x['survey.updated'])),
                ('Seen By', 'survey.router.name'),
                ('Trusted', lambda x: check if x['trust.trusted'] else ''),
            ))

        survey = self.api.get_pager('wireless_ap_survey_view',
                                    expand='survey.router,trust,wireless_ap',
                                    **filters)
        with self.make_table(headers=fields.keys(),
                             accessors=fields.values()) as t:
            t.print(map(dict, map(base.totuples, survey)))


class Survey(base.ECMCommand):
    """ Start a WiFi site survey on connected router(s). """

    name = 'survey'
    use_pager = False

    def setup_args(self, parser):
        self.add_router_argument('idents', nargs='*')

    def run(self, args):
        if args.idents:
            ids = [self.api.get_by_id_or_name('routers', x)['id']
                   for x in args.idents]
        else:
            ids = [x['id'] for x in self.api.get_pager('routers')]
        self.api.post('wireless_site_survey', ids)


class WiFi(base.ECMCommand):
    """ WiFi access points info and surveys. """

    name = 'wifi'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(AccessPoints, default=True)
        self.add_subcommand(Survey)

command_classes = [WiFi]
