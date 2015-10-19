"""
Manage ECM Groups.
"""

import collections
import difflib
import json
import shellish
import sys
from . import base


PatchStat = collections.namedtuple('PatchStat', 'adds, removes')


def patch_stats(patch):
    adds, removes = patch
    adds = list(base.totuples(adds))
    return PatchStat(len(adds), len(removes))


def patch_validate(patch):
    if not isinstance(patch, list) or len(patch) != 2:
        raise TypeError('Patch must be a 2 item list')
    for x in patch[1]:
        if not isinstance(x, list):
            raise TypeError('Removals must be lists')
    if not isinstance(patch[0], dict):
        raise TypeError('Additions must be an dict tree')


class Printer(object):
    """ Mixin for printing commands. """

    expands = ','.join([
        'statistics',
        'product',
        'account',
        'target_firmware',
        'configuration'
    ])

    def setup_args(self, parser):
        self.inject_table_factory()
        super().setup_args(parser)

    def bundle_group(self, group):
        group['product'] = group['product']['name']
        group['firmware'] = group['target_firmware']['version']
        stats = group['statistics']
        group['online'] = stats['online_count']
        group['offline'] = stats['offline_count']
        group['total'] = stats['device_count']
        group['account_name'] = group['account']['name']
        group['suspended'] = stats['suspended_count']
        group['synchronized'] = stats['synched_count']
        return group

    def ratio_format(self, actual, possible, high=0.99, med=0.90, low=0.90):
        """ Color format output for a ratio. Bigger is better. """
        if not possible:
            return ''
        pct = round((actual / possible) * 100)
        if pct > .99:
            color = 'green'
        elif pct > .90:
            color = 'yellow'
        else:
            color = 'red'
        return '%s/%s (<%s>%d%%</%s>)' % (actual, possible, color, pct, color)

    def online_accessor(self, group):
        """ Table accessor for online column. """
        return self.ratio_format(group['online'], group['total'])

    def sync_accessor(self, group):
        """ Table accessor for config sync stats. """
        suspended = group['suspended']
        sync = group['synchronized']
        total = group['total']
        ret = self.ratio_format(sync, total)
        if suspended:
            ret += ', <red>%d suspended</red>' % suspended
        return ret

    def patch_accessor(self, group):
        """ Table accessor for patch stats. """
        stat = patch_stats(group['configuration'])
        output = []
        if stat.adds:
            output.append('<cyan>+%d</cyan>' % stat.adds)
        if stat.removes:
            output.append('<magenta>-%d</magenta>' % stat.removes)
        return '/'.join(output)

    def printer(self, groups):
        fields = (
            ("name", 'Name'),
            ("id", 'ID'),
            ("account_name", 'Account'),
            ("product", 'Product'),
            ("firmware", 'Firmware'),
            (self.online_accessor, 'Online'),
            (self.sync_accessor, 'Config Sync'),
            (self.patch_accessor, 'Config Patch'),
        )
        with self.make_table(headers=[x[1] for x in fields],
                             accessors=[x[0] for x in fields]) as t:
            t.print(map(self.bundle_group, groups))


class List(Printer, base.ECMCommand):
    """ List group(s). """

    name = 'ls'

    def setup_args(self, parser):
        self.add_group_argument(nargs='?')
        super().setup_args(parser)

    def run(self, args):
        if args.ident:
            groups = [self.api.get_by_id_or_name('groups', args.ident,
                                                 expand=self.expands)]
        else:
            groups = self.api.get_pager('groups', expand=self.expands)
        self.printer(groups)


class Create(base.ECMCommand):
    """ Create a new group.
    A group mostly represents configuration for more than one device, but
    also manages settings such as alerts and log acquisition. """

    name = 'create'

    def setup_args(self, parser):
        self.add_argument('--name')
        self.add_product_argument('--product')
        self.add_firmware_argument('--firmware')

    def run(self, args):
        name = args.name or input('Name: ')
        if not name:
            raise SystemExit("Name required")

        product = args.product or input('Product: ')
        products = dict((x['name'], x)
                        for x in self.api.get_pager('products'))
        if product not in products:
            if not product:
                print("Product required")
            else:
                print("Invalid product:", product)
            print("\nValid products...")
            for x in sorted(products):
                print("\t", x)
            raise SystemExit(1)

        fw = args.firmware or input('Firmware: ')
        firmwares = dict((x['version'], x)
                         for x in self.api.get_pager('firmwares',
                         product=products[product]['id']))
        if fw not in firmwares:
            if not fw:
                print("Firmware required")
            else:
                print("Invalid firmware:", fw)
            print("\nValid firmares...")
            for x in sorted(firmwares):
                print("\t", x)
            raise SystemExit(1)

        self.api.post('groups', {
            "name": name,
            "product": products[product]['resource_uri'],
            "target_firmware": firmwares[fw]['resource_uri']
        })


class Config(base.ECMCommand):
    """ Show or alter the group configuration.
    The configuration stored in a group consists of a patch tuple;
    (additions, removals) respectively.  The patch format is a JSON array with
    exactly 2 entries to match the aforementioned tuple.

    Additions are a JSON object that holds a subset of a routers configuration
    tree.  When paths, or nodes, are absent they are simply ignored.  The
    config system will crawl the object looking for "leaf" nodes, which are
    applied as an overlay on the device.

    The actual algo for managing this layering is rather complex, so it is
    advised that you experiment with this feature in a test environment before
    attempting action on a production environment.

    The deletions section contains lists of paths to be removed from the
    router's config.  This is used in cases where you want to explicitly take
    out a configuration that is on the router by default.  A common case is
    removing one of the default LAN networks, such as the guest network.

    Example patch that updates config.system.desc and has no deletions.

        [{"system": {"desc": "New Value Here"}}, []]
    """

    name = 'config'

    def setup_args(self, parser):
        self.add_group_argument()
        edit_options = parser.add_argument_group('patch options (DANGEROUS)')
        or_group = edit_options.add_mutually_exclusive_group()
        self.add_argument('--patch-file', parser=or_group, help='JSON patch '
                          'file or - to read from stdin.')
        self.add_argument('--purge', action='store_true', parser=or_group,
                          help='Completely remove configuration.')
        self.add_argument('--force', '-f', action='store_true',
                          parser=edit_options, help='Do not prompt for '
                          'confirmation.')
        output_options = parser.add_argument_group('output options')
        self.add_argument('--json', action='store_true',
                          parser=output_options)
        self.add_argument('--output-file', '-o', parser=output_options)

    def run(self, args):
        group = self.api.get_by_id_or_name('groups', args.ident,
                                           expand='configuration')
        if args.purge or args.patch_file:
            return self.update(group, args)
        else:
            return self.show(group, args)

    def update(self, group, args):
        if args.purge:
            if not args.force:
                base.confirm('Confirm config purge of: %s' % group['name'])
        elif args.patch_file:
            with open(args.patch_file) as f:
                patch = json.load(f)
            patch_validate(patch)
            oldpatch = group['configuration']
            oldjson = json.dumps(oldpatch, indent=4, sort_keys=True)
            newjson = json.dumps(patch, indent=4, sort_keys=True)
            old_adds = list('='.join(map(str, x))
                            for x in base.totuples(group['configuration'][0]))
            new_adds = list('='.join(map(str, x))
                            for x in base.totuples(patch[0]))
            for line in difflib.unified_diff(oldjson.splitlines(True),
                                             newjson.splitlines(True),
                                             fromfile='current config',
                                             tofile='proposed config', n=10):
                print(line, end='')
            for line in difflib.unified_diff(old_adds, new_adds, n=0):
                if line[0] not in '-+':
                    continue
                print(line)
            base.confirm('Confirm update of config of: %s' % group['name'])
        else:
            raise RuntimeError('invalid call to update')

    def show(self, group, args):
        adds, removes = group['configuration']
        if args.output_file:
            args.json = True
            outfd = open(args.output_file, 'w')
        else:
            outfd = sys.stdout
        if args.json:
            print(json.dumps([adds, removes], indent=4), file=outfd)
        else:
            treelines = shellish.dicttree(base.todict({
                "<additions>": adds,
                "<removes>": removes
            }), render_only=True)
            for x in treelines:
                print(x, file=outfd)
        if outfd is not sys.stdout:
            outfd.close()


class Edit(base.ECMCommand):
    """ Edit group attributes. """

    name = 'edit'

    def setup_args(self, parser):
        self.add_group_argument()
        self.add_argument('--name')
        self.add_firmware_argument('--firmware')

    def run(self, args):
        group = self.api.get_by_id_or_name('groups', args.ident,
                                           expand='product')
        updates = {}
        if args.name:
            updates['name'] = args.name
        if args.firmware:
            fw = self.api.get_by(['version'], 'firmwares', args.firmware,
                                 product=group['product']['id'])
            updates['target_firmware'] = fw['resource_uri']
        self.api.put('groups', group['id'], updates)


class Delete(base.ECMCommand):
    """ Delete one or more groups. """

    name = 'delete'

    def setup_args(self, parser):
        self.add_group_argument('idents', nargs='+')
        self.add_argument('-f', '--force', action="store_true")

    def run(self, args):
        for ident in args.idents:
            group = self.api.get_by_id_or_name('groups', ident)
            if not args.force and \
               not base.confirm('Delete group: %s' % group['name'],
                                exit=False):
                continue
            self.api.delete('groups', group['id'])


class Move(base.ECMCommand):
    """ Move group to a different account. """

    name = 'move'

    def setup_args(self, parser):
        self.add_group_argument()
        self.add_account_argument('new_account',
                                  metavar='NEW_ACCOUNT_ID_OR_NAME')
        self.add_argument('-f', '--force', action="store_true")

    def run(self, args):
        group = self.api.get_by_id_or_name('groups', args.ident)
        account = self.api.get_by_id_or_name('accounts', args.new_account)
        self.api.put('groups', group['id'],
                     {"account": account['resource_uri']})


class Search(Printer, base.ECMCommand):
    """ Search for groups. """

    name = 'search'
    fields = ['name', ('firmware', 'target_firmware.version'),
              ('product', 'product.name'), ('account', 'account.name')]

    def setup_args(self, parser):
        searcher = self.make_searcher('groups', self.fields)
        self.lookup = searcher.lookup
        self.add_search_argument(searcher)
        super().setup_args(parser)

    def run(self, args):
        results = list(self.lookup(args.search, expand=self.expands))
        if not results:
            raise SystemExit("No Results For: %s" % ' '.join(args.search))
        self.printer(results)


class Groups(base.ECMCommand):
    """ Manage ECM Groups. """

    name = 'groups'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(List, default=True)
        self.add_subcommand(Create)
        self.add_subcommand(Edit)
        self.add_subcommand(Delete)
        self.add_subcommand(Move)
        self.add_subcommand(Search)
        self.add_subcommand(Config)

command_classes = [Groups]
