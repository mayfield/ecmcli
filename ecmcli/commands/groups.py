"""
Manage ECM Groups.
"""

import collections
import copy
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
    if not isinstance(patch, (list, tuple)) or len(patch) != 2:
        raise TypeError('Patch must be a 2 item sequence')
    for x in patch[1]:
        if not isinstance(x, (list, tuple)):
            raise TypeError('Removals must be sequences')
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
            ("id", 'ID'),
            ("name", 'Name'),
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
    use_pager = False

    def setup_args(self, parser):
        self.add_argument('--name')
        self.add_product_argument('--product')
        self.add_firmware_argument('--firmware')
        self.add_account_argument('--account')

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

        group = {
            "name": name,
            "product": products[product]['resource_uri'],
            "target_firmware": firmwares[fw]['resource_uri']
        }
        if args.account:
            account = self.api.get_by_id_or_name('accounts', args.account)
            group['account'] = account['resource_uri']
        self.api.post('groups', group)


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(ConfigShow, default=True)
        self.add_subcommand(ConfigSet)
        self.add_subcommand(ConfigClear)


class ConfigShow(base.ECMCommand):
    """ Show the config patch used for a group. """

    name = 'show'

    def setup_args(self, parser):
        self.add_group_argument()
        self.add_argument('--json', action='store_true')
        self.add_file_argument('--output-file', '-o', default='-', mode='w')

    def run(self, args):
        group = self.api.get_by_id_or_name('groups', args.ident,
                                           expand='configuration')
        adds, removes = group['configuration']
        with args.output_file as f:
            if f is not sys.stdout:
                args.json = True
            if args.json:
                print(json.dumps([adds, removes], indent=4), file=f)
            else:
                treelines = shellish.treeprint({
                    "<additions>": adds,
                    "<removes>": removes
                }, render_only=True)
                for x in treelines:
                    print(x, file=f)


class ConfigSet(base.ECMCommand):
    """ Update the config of a group. """

    name = 'set'
    use_pager = False

    def setup_args(self, parser):
        self.add_group_argument()
        ex = parser.add_mutually_exclusive_group(required=True)
        self.add_file_argument('--replace', metavar='PATCH_FILE', parser=ex,
                               help='Replace entire group config.')
        self.add_file_argument('--merge', metavar='PATCH_FILE', parser=ex,
                               help='Merge new patch into existing group '
                               'config.')
        self.add_argument('--set', metavar='KEY=JSON_VALUE', parser=ex,
                          help='Set a single value in the group config.')
        self.add_argument('--force', '-f', action='store_true', help='Do not '
                          'prompt for confirmation.')
        self.add_argument('--json-diff', action='store_true', help='Show diff '
                          'of JSON values instead of key=value tuples.')

    def inplace_merge(self, dst, src):
        """ Copy bits from src into dst. """
        for key, val in src.items():
            if not isinstance(val, dict) or key not in dst:
                dst[key] = val
            else:
                self.inplace_merge(dst[key], src[key])

    def merge(self, orig, overlay):
        updates = copy.deepcopy(orig[0])
        self.inplace_merge(updates, overlay[0])
        removes = list(set(map(tuple, orig[1])) | set(map(tuple, overlay[1])))
        return updates, removes

    def run(self, args):
        group = self.api.get_by_id_or_name('groups', args.ident,
                                           expand='configuration')
        cur_patch = group['configuration']
        if args.replace:
            with args.replace as f:
                patch = json.load(f)
            patch_validate(patch)
        elif args.merge:
            with args.merge as f:
                overlay = json.load(f)
            patch_validate(overlay)
            patch = self.merge(cur_patch, overlay)
        elif args.set:
            path, value = args.set.split('=', 1)
            path = path.strip().split('.')
            value = json.loads(value)
            updates = copy.deepcopy(cur_patch[0])
            offt = updates
            for x in path[:-1]:
                if x in offt:
                    offt = offt[x]
                else:
                    offt[x] = {}
            offt[path[-1]] = value
            patch = [updates, cur_patch[1]]
        patch_validate(patch)
        if args.json_diff:
            oldjson = json.dumps(cur_patch, indent=4, sort_keys=True)
            newjson = json.dumps(patch, indent=4, sort_keys=True)
            printed = False
            for line in difflib.unified_diff(oldjson.splitlines(True),
                                             newjson.splitlines(True),
                                             fromfile='current config',
                                             tofile='proposed config', n=10):
                if line.startswith('---') or line.startswith('+++'):
                    line = '<b>%s</b>' % line
                elif line.startswith('@@'):
                    line = '<cyan>%s</cyan>' % line
                elif line[0] == '-':
                    line = '<red>%s</red>' % line
                elif line[0] == '+':
                    line = '<green>%s</green>' % line
                shellish.vtmlprint(line, end='')
                printed = True
            if printed:
                print()
        else:
            old_adds = dict(base.totuples(cur_patch[0]))
            new_adds = dict(base.totuples(patch[0]))
            old_add_keys = set(old_adds)
            new_add_keys = set(new_adds)
            for x in old_add_keys - new_add_keys:
                shellish.vtmlprint('<red>Unsetting:</red> %s=%s' % (
                                   x, old_adds[x]))
            for x in new_add_keys - old_add_keys:
                shellish.vtmlprint('<green>Adding:</green> %s=%s' % (
                                   x, new_adds[x]))
            for x in new_add_keys & old_add_keys:
                if old_adds[x] != new_adds[x]:
                    shellish.vtmlprint('<yellow>Changing:</yellow> %s (%s'
                                       '<b> -> </b>%s)' % (x, old_adds[x],
                                       new_adds[x]))
            old_removes = set(map(tuple, cur_patch[1]))
            new_removes = set(map(tuple, patch[1]))
            for x in old_removes - new_removes:
                shellish.vtmlprint('<red>Unsetting removal:</red> %s' % (
                                   '.'.join(map(str, x))))
            for x in new_removes - old_removes:
                shellish.vtmlprint('<green>Adding removal:</green> %s' % (
                                   '.'.join(map(str, x))))
        self.confirm('Confirm update of config of: %s' % group['name'])
        self.api.put('groups', group['id'], {"configuration": patch})


class ConfigClear(base.ECMCommand):
    """ Clear the config of a group. """

    name = 'clear'
    use_pager = False

    def setup_args(self, parser):
        self.add_group_argument()
        self.add_argument('--force', '-f', action='store_true',
                          help='Do not prompt for confirmation.')

    def run(self, args):
        group = self.api.get_by_id_or_name('groups', args.ident,
                                           expand='configuration')
        if not args.force:
            self.confirm('Confirm config clear of: %s' % group['name'])
        self.api.put('groups', group['id'], {"configuration": [{}, []]})


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

    name = 'rm'
    use_pager = False

    def setup_args(self, parser):
        self.add_group_argument('idents', nargs='+')
        self.add_argument('-f', '--force', action="store_true")

    def run(self, args):
        for ident in args.idents:
            group = self.api.get_by_id_or_name('groups', ident)
            if not args.force and \
               not self.confirm('Delete group: %s' % group['name'],
                                exit=False):
                continue
            self.api.delete('groups', group['id'])


class Move(base.ECMCommand):
    """ Move group to a different account. """

    name = 'mv'

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
        results = self.lookup(args.search, expand=self.expands)
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
