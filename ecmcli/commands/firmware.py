"""
Commands for managing firmware versions of routers.
"""

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
        self.tabulate(data, title='Active Firmware Stats',
                      accessors=[fw_field, 'id_count', standalone])


class Updates(AvailMixin, base.ECMCommand):
    """ Scan routers to see if a firmware update is available.
    If no updates are found show nothing, otherwise a report of the available
    updates is printed and the command produces a truthy return value. """

    name = 'updates'

    def run(self, args):
        fw_field = 'actual_firmware__version'
        no_updates = True
        for x in  self.api.get('routers', group_by=fw_field +
                               ',product__name'):
            if x[fw_field] is None:
                continue  # unsupported/dev fw
            avail = self.available_firmware(product_name=x['product__name'],
                                            version=x[fw_field])
            name = '%s v%s' % (x['product__name'], x[fw_field])
            if avail:
                no_updates = False
                self.vtmlprint("<b>Updates available for: %s</b>" % name)
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
            base.confirm('Confirm %sgrade of %s "%s" from %s to %s' % (
                         direction, type_, ent['name'], fromfw['version'],
                         tofw['version']))
        self.api.put(dict(target_firmware=tofw['resource_uri']),
                     urn=ent['resource_uri'])


class Firmware(base.ECMCommand):
    """ Manage ECM Routers. """

    name = 'firmware'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(Active, default=True)
        self.add_subcommand(Updates)
        self.add_subcommand(Upgrade)

command_classes = [Firmware]
