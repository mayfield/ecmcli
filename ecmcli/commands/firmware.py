"""
Commands for managing firmware versions of routers.
"""

import json
import shellish
import sys
from . import base


class AvailMixin(object):

    _fw_avail_cache = {}

    def available_firmware(self, product_urn=None, product_name=None,
                           version=None):
        """ Lookup available firmware versions by product/version tuple. """
        key = product_urn or product_name
        try:
            avail = self._fw_avail_cache[key]
        except KeyError:
            if product_urn:
                query = dict(product=product_urn.split('/')[-2])
            elif product_name:
                query = dict(product__name=product_name)
            else:
                raise TypeError('product_urn or product_name required')
            avail = list(self.api.get_pager('firmwares', expand='product',
                                            order_by='release_date', **query))
            if not avail:
                raise ValueError("Invalid product query: %s" % (query))
            product = avail[0]['product']
            self._fw_avail_cache[product['resource_uri']] = avail
            self._fw_avail_cache[product['name']] = avail
        return [x for x in avail if x['version'] > (version or "")]


class Active(base.ECMCommand):
    """ Show the firmware versions being actively used. """

    name = 'active'

    def run(self, args):
        data = [['Firmware Version', 'Routers', 'Standalone']]
        fw_field = 'actual_firmware__version'
        data.extend(self.api.get('routers', group_by=fw_field,
                                 count='id,group'))
        standalone = lambda x: x['id_count'] - x['group_count']
        shellish.tabulate(data, title='Active Firmware Stats',
                          accessors=[fw_field, 'id_count', standalone])


class Updates(AvailMixin, base.ECMCommand):
    """ Scan routers to see if a firmware update is available.
    If no updates are found show nothing, otherwise a report of the available
    updates is printed and the command produces a truthy return value. """

    name = 'updates'

    def run(self, args):
        fw_field = 'actual_firmware__version'
        no_updates = True
        for x in self.api.get('routers', group_by=fw_field +
                              ',product__name', count='id'):
            if x[fw_field] is None:
                continue  # unsupported/dev fw
            avail = self.available_firmware(product_name=x['product__name'],
                                            version=x[fw_field])
            name = '%s v%s (%s devices)' % (x['product__name'], x[fw_field],
                                            x['id_count'])
            if avail:
                no_updates = False
                shellish.vtmlprint("<b>Updates available for: %s</b>" % name)
                for xx in avail:
                    print("\tv%s (Release Date: %s)" % (xx['version'],
                          xx['release_date'].date()))
        if not no_updates:
            raise SystemExit(1)


class Upgrade(AvailMixin, base.ECMCommand):
    """ Upgrade firmware for one routers or a group of routers.
    For ungrouped routers we can start a firmware upgrade directly.  For
    grouped devices the target firmware version for the group can be altered.
    """

    name = 'upgrade'
    use_pager = False

    def setup_args(self, parser):
        or_group = parser.add_mutually_exclusive_group(required=True)
        self.add_router_argument('--router', parser=or_group)
        self.add_group_argument('--group', parser=or_group)
        self.add_firmware_argument('--upgrade-to')
        self.add_argument('--force', '-f', action='store_true',
                          help='Do not confirm upgrade.')

    def run(self, args):
        router = group = None
        if args.router:
            router = self.api.get_by_id_or_name('routers', args.router)
            if router['group']:
                raise SystemExit('Cannot upgrade router in group')
            product = router['product']
            firmware = router['actual_firmware']
            ent = router
            type_ = 'router'
        elif args.group:
            group = self.api.get_by_id_or_name('groups', args.group)
            product = group['product']
            firmware = group['target_firmware']
            ent = group
            type_ = 'group'
        else:
            raise RuntimeError("Arguments misconfigured")
        avail = self.available_firmware(product_urn=product)
        for fromfw in avail:
            if firmware == fromfw['resource_uri']:
                break
        else:
            raise RuntimeError("Originating firmware not found in system")
        if not args.upgrade_to:
            tofw = avail[-1]
        else:
            for tofw in avail:
                if args.upgrade_to == tofw['version']:
                    break
            else:
                raise SystemExit("Invalid firmware for product")
        if tofw == fromfw:
            raise SystemExit("Target version matches current version")
        direction = 'down' if tofw['version'] < fromfw['version'] else 'up'
        if not args.force:
            self.confirm('Confirm %sgrade of %s "%s" from %s to %s' % (
                         direction, type_, ent['name'], fromfw['version'],
                         tofw['version']))
        self.api.put(dict(target_firmware=tofw['resource_uri']),
                     urn=ent['resource_uri'])


class DTD(base.ECMCommand):
    """ Show the DTD for a firmware version.
    Each firmware has a configuration data-type-definition which describes and
    regulates the structure and types that go into a router's config. """

    name = 'dtd'

    def setup_args(self, parser):
        self.add_firmware_argument('--firmware', help='Limit display to this '
                                   'firmware version.')
        self.add_product_argument('--product', help='Limit display to this '
                                  'product type.')
        self.add_argument('path', nargs='?', help='Dot notation offset into '
                          'the DTD tree.')
        self.add_argument('--shallow', '-s', action='store_true',
                          help='Only show one level of the DTD.')
        output = parser.add_argument_group('output formats', 'Change the '
                                           'DTD output format.')
        for x in ('json', 'tree'):
            self.add_argument('--%s' % x, dest='format', action='store_const',
                              const=x, parser=output)
        self.add_file_argument('--output-file', '-o', mode='w', default='-',
                               metavar="OUTPUT_FILE", parser=output)
        super().setup_args(parser)

    def walk_dtd(self, dtd, path=None):
        """ Walk into a DTD tree.  The path argument is the path as it relates
        to a rendered config and not the actual dtd structure which is double
        nested to contain more information about the structure. """
        offt = {'nodes': dtd}
        if path:
            for x in path.split('.'):
                try:
                    offt = offt['nodes'][x]
                except KeyError:
                    raise SystemExit('DTD path not found: %s' % path)
        else:
            path = '<root>'
        return {path: offt}

    def run(self, args):
        filters = {}
        if args.firmware:
            filters['version'] = args.firmware
        if args.product:
            filters['product__name'] = args.product
        firmwares = self.api.get('firmwares', expand='dtd', limit=1, **filters)
        if not firmwares:
            raise SystemExit("No firmware DTD matches this specification.")
        if firmwares.meta['total_count'] > 1:
            shellish.vtmlprint('<red><b>WARNING:</b></red> More than one '
                               'firmware DTD found for this specification.',
                               file=sys.stderr)
        dtd = firmwares[0]['dtd']['value']
        with args.output_file as f:
            dtd = self.walk_dtd(dtd, args.path)
            if args.shallow:
                if 'nodes' in dtd:
                    dtd['nodes'] = list(dtd['nodes'])
            if args.format == 'json':
                print(json.dumps(dtd, indent=4, sort_keys=True), file=f)
            else:
                shellish.treeprint(dtd, file=f)


class Firmware(base.ECMCommand):
    """ Manage ECM Firmware. """

    name = 'firmware'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(Active, default=True)
        self.add_subcommand(Updates)
        self.add_subcommand(Upgrade)
        self.add_subcommand(DTD)

command_classes = [Firmware]
