"""
Get and set remote values on series 3 routers.
"""

import argparse
import csv
import itertools
import json
import shellish
import syndicate.data
import sys
from . import base


def todict(obj, str_array_keys=False):
    """ On a tree of list and dict types convert the lists to dict types. """
    if isinstance(obj, list):
        key_conv = str if str_array_keys else lambda x: x
        return dict((key_conv(k), todict(v, str_array_keys))
                    for k, v in zip(itertools.count(), obj))
    elif isinstance(obj, dict):
        obj = dict((k, todict(v, str_array_keys)) for k, v in obj.items())
    return obj


class DeviceSelectorsMixin(object):
    """ Add arguments used for selecting devices. """

    completer_cache = {}
    search_fields = ['name', 'desc', 'mac', ('account', 'account.name'),
                     'asset_id', 'custom1', 'custom2',
                     ('group', 'group.name'),
                     ('firmware', 'actual_firmware.version'), 'ip_address',
                     ('product', 'product.name'), 'serial_number', 'state']

    def setup_args(self, parser):
        self.add_argument('--disjunction', '--or', action='store_true',
                          help="Logical OR the selection arguments.")
        self.add_argument('--skip-offline', action='store_true',
                          help='Ignore devices that are offline.')
        self.add_group_argument('--group')
        self.add_router_argument('--router')
        self.add_account_argument('--account')
        self.add_product_argument('--product')
        self.add_firmware_argument('--firmware')
        searcher = self.make_searcher('routers', self.search_fields)
        self.search_lookup = searcher.lookup
        self.add_search_argument(searcher, '--search')
        super().setup_args(parser)

    @shellish.ttl_cache(300)
    def api_res_lookup(self, *args, **kwargs):
        """ Cached wrapper around get_by_id_or_name. """
        return self.api.get_by_id_or_name(*args, required=False, **kwargs)

    def gen_selection_filters(self, args_namespace):
        """ Return the api filters for the selection criteria.  Note that
        the group selection is only used to get a list of devices. """
        args = vars(args_namespace)
        filters = {}
        if args.get('group'):
            hit = self.api_res_lookup('groups', args['group'],
                                      product__series=3)
            if hit:
                filters['group'] = hit['id']
        if args.get('account'):
            hit = self.api_res_lookup('accounts', args['account'])
            if hit:
                filters['account'] = hit['id']
        if args.get('product'):
            hit = self.api_res_lookup('products', args['product'], series=3)
            if hit:
                filters['product'] = hit['id']
        if args.get('firmware'):
            filters['actual_firmware.version'] = args['firmware']
        rids = []
        if args.get('router'):
            hit = self.api_res_lookup('routers', args['router'],
                                      product__series=3)
            if hit:
                rids.append(hit['id'])
        if args.get('search'):
            rids.extend(x['id'] for x in self.search_lookup(args['search']))
        if rids:
            filters['id__in'] = ','.join(rids)
        if args.get('disjunction'):
            filters = dict(_or='|'.join('%s=%s' % x for x in filters.items()))
        if args.get('skip_offline'):
            filters['state'] = 'online'
        return filters

    def remote(self, path, routers, **query):
        routermap = dict((x['id'], x) for x in routers)
        if not routermap:
            return
        for x in self.api.get_pager('remote', path.replace('.', '/'),
                                    id__in=','.join(routermap), **query):
            x['router'] = routermap[str(x['id'])]
            if x['success']:
                x['dict'] = todict(x['data'])
            yield x

    @shellish.ttl_cache(300)
    def completion_router_elect(self, **filters):
        """ Cached lookup of a router meeting the filters criteria to be used
        for completion lookups. """
        filters.update({
            'state': 'online',
            'product__series': 3,
            'limit': 1,
            'fields': 'id'
        })
        r = self.api.get('routers', **filters)
        return r and r[0]['id']

    def try_complete_path(self, prefix, args=None):
        filters = self.gen_selection_filters(args)
        rid = self.completion_router_elect(**filters)
        if not rid:
            return set(('[NO ONLINE MATCHING ROUTERS FOUND]', ' '))
        parts = prefix.split('.')
        if len(parts) > 1:
            path = parts[:-1]
            prefix = parts[-1]
        else:
            path = []
        # Cheat for root paths to avoid huge lookup cost on naked tab.
        if not path:
            cs = dict.fromkeys(('config', 'status', 'control', 'state'), {})
        else:
            cs = self.remote_lookup((rid,) + tuple(path))
            if not cs:
                return set()
        options = dict((str(k), v) for k, v in cs.items()
                       if str(k).startswith(prefix))
        if len(options) == 1:
            key, value = list(options.items())[0]
            if isinstance(value, dict):
                options[key + '.'] = None # Prevent trailing space.
        return set('.'.join(path + [x]) for x in options)

    @shellish.hone_cache(maxage=3600, refineby='container')
    def remote_lookup(self, rid_and_path):
        rid = rid_and_path[0]
        path = rid_and_path[1:]
        resp = self.api.get('remote', *path, id=rid)
        if resp and resp[0]['success'] and 'data' in resp[0]:
            return todict(resp[0]['data'], str_array_keys=True)


class Get(DeviceSelectorsMixin, base.ECMCommand):
    """ Get configs for a selection of routers. """

    name = 'get'

    def setup_args(self, parser):
        super().setup_args(parser)
        group = parser.add_argument_group('output options')
        or_group = group.add_mutually_exclusive_group()
        for x in ('json', 'csv', 'xml', 'table'):
            self.add_argument('--%s' % x, dest='output', action='store_const',
                              const=x, parser=or_group)
        self.add_argument('path', metavar='REMOTE_PATH', nargs='?',
                          complete=self.try_complete_path, default='',
                          help='Dot notation path to config value; Eg. '
                               'status.wan.rules.0.enabled')
        self.add_argument('--output-file', '-o', type=argparse.FileType('w'),
                          metavar="OUTPUT_FILE")

    def run(self, args):
        filters = self.gen_selection_filters(args)
        routers = self.api.get_pager('routers', **filters)
        formatter = {
            'json': self.json_format,
            'xml': self.xml_format,
            'csv': self.csv_format,
            'table': self.table_format,
            None: self.tree_format
        }[args.output]
        formatter(args.path, self.remote(args.path, routers))

    def tree_format(self, path, results_gen):
        headers = ['Name', 'ID', 'Success', 'Response']
        worked = []
        failed = []
        title = 'Remote data for: %s' % path
        table = shellish.Table(title=title, headers=headers)
        def cook():
            for x in results_gen:
                if x['success']:
                    worked.append(x)
                    if not isinstance(x['dict'], dict):
                        resp = ['VALUE: <b>%s</b>' % x['dict']]
                    else:
                        resp = self.tree(dict(VALUE=x['dict']), render_only=True)
                else:
                    failed.append(x)
                    error = x.get('message', x.get('reason',
                                                   x.get('exception')))
                    resp = ['ERROR: <b>%s</b>' % error]
                feeds = [
                    [x['router']['name']],
                    [x['router']['id']],
                    ['yes' if x['success'] else 'no'],
                    resp
                ]
                for row in itertools.zip_longest(*feeds, fillvalue=''):
                    yield row
        table.print(cook())
        if worked:
            table.print_footer('Succeeded: %d' % len(worked))
        if failed:
            table.print_footer('Failed: %d' % len(failed))

    def data_flatten(self, data):
        """ Flatten out the results a bit for a consistent data format. """
        for result in data:
            for x in ('desc', 'custom1', 'custom2', 'asset_id', 'ip_address',
                      'mac', 'name', 'serial_number', 'state'):
                result[x] = result['router'].get(x)
            result.pop('router', None)
            result.pop('dict', None)
            yield result

    def json_format(self, path, results_gen):
        jenc = syndicate.data.NormalJSONEncoder(indent=4, sort_keys=True)
        print("[", end='')
        first = True
        for result in self.data_flatten(results_gen):
            if not first:
                print(", ", end='')
            else:
                first = False
            print(jenc.encode(result), end='')
        print("]")

    def xml_format(self):
        pass

    def csv_format(self, path, results_gen):
        fields = ('data', 'id', 'success', 'mac', 'name', 'exception')
        writer = csv.DictWriter(sys.stdout, fieldnames=fields,
                                extrasaction='ignore')
        writer.writeheader()
        writer.writerows(self.data_flatten(results_gen))

    def table_format(self):
        pass


class Set(DeviceSelectorsMixin, base.ECMCommand):
    """ Set a config value on a selection of devices and/or groups. """

    name = 'set'

    def setup_args(self, parser):
        super().setup_args(parser)
        in_group = parser.add_mutually_exclusive_group(required=True)
        self.add_argument('--input-data', '-d', metavar="INPUT_DATA",
                          help="JSON formated input data.", parser=in_group)
        self.add_argument('--input-file', '-i', type=argparse.FileType('r'),
                          metavar="INPUT_FILE", parser=in_group)
        self.add_argument('--dry-run', '--manifest', help="Do not set a "
                          "config.  Generate a manifest of what would be "
                          "done and the potential peril if executed.")

    def run(self, args):
        try:
            value = json.loads(value)
        except ValueError as e:
            raise SystemExit('Invalid JSON Value: %s' % e)
        for x in routers:
            ok = self.remote('config', key.replace('.', '/'),
                             value, id=x['id'])[0]
            status = 'okay' if ok['success'] else \
                     '%s %s' % (ok['exception'], ok.get('message', ''))
            print('%s:' % x['name'], status)


class ConfigDefinition(base.ECMCommand):
    """ Display config store data definition (dtd) for a specific product and
    firmware.  Each router supports different config settings and this command
    is useful to introspect the config structure for a particular device
    variant. """

    name = 'dtd'

    def setup_args(self, parser):
        super().setup_args(parser)
        self.add_product_argument('--product', default="MBR1400")
        self.add_firmware_argument('--firmware', default="5.4.1")
        self.add_argument('path', complete=self.complete_dtd_path)

    def complete_dtd_path(self, prefix, args=None):
        return set('wan', 'lan', 'system', 'firewall')

    def run(self, args):
        filters = {
            "product.name": args.product,
            "firmware.version": args.firmware
        }
        firmwares = self.api.get('firmwares', **filters)
        if not firmwares:
            raise SystemExit("Firmware not found: %s v%s" % (args.product,
                             args.firmware))
        dtd = self.api.get(urn=firmwares[0]['dtd'])
        print(dtd)


class Diff(base.ECMCommand):
    """ Produce an N-way diff of a particular config-store path between any
    selection of routers. """

    name = 'diff'

    def setup_args(self, parser):
        super().setup_args(parser)
        self.add_product_argument('--product', default="MBR1400")
        self.add_firmware_argument('--firmware', default="5.4.1")
        self.add_argument('path', complete=self.complete_dtd_path)

    def complete_dtd_path(self, prefix, args=None):
        return set('wan', 'lan', 'system', 'firewall')

    def run(self, args):
        filters = {
            "product.name": args.product,
            "firmware.version": args.firmware
        }
        firmwares = self.api.get('firmwares', **filters)
        if not firmwares:
            raise SystemExit("Firmware not found: %s v%s" % (args.product,
                             args.firmware))
        dtd = self.api.get(urn=firmwares[0]['dtd'])
        print(dtd)


class Remote(base.ECMCommand):
    """ Remote control live routers.

    The remote interface gives direct access to online routers.  Generally
    this provides the ability to view status and configuration as well as set
    configuration and activate certain router control features.  All the
    commands operate under the pretense of a router being online and connected
    to ECM.

    The endpoint of these remote calls is one or more Cradlepoint series 3
    routers.  More specifically it is to the config-store of these routers.
    The config-store is the information hub for everything the router exposes
    publicly.  It provides access to real-time status, logs, and current state
    as well as read/write access to the non-volatile configuration.  There is
    also a control tree to instruct the router to perform various actions such
    as rebooting, doing a traceroute or even  pulling GPIO pins up and down.

    <u><b>DISCLAIMER: All the actions performed with this command are done
    optimistically and without regard to firmware versions.  It is an
    exercise for the reader to understand the affects of these commands as
    well as the applicability of any input values provided.</b></u>
    """

    name = 'remote'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(Get, default=True)
        self.add_subcommand(Set)
        self.add_subcommand(ConfigDefinition)
        self.add_subcommand(Diff)

command_classes = [Remote]
