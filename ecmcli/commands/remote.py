"""
Get and set configs for routers and groups.
"""

import argparse
import itertools
import json
import shellish
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
        if args.get('router'):
            hit = self.api_res_lookup('routers', args['router'],
                                      product__series=3, state='online')
            if hit:
                filters['id'] = hit['id']
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
        cs = self.remote_lookup((rid,) + tuple(path))
        if not cs:
            return set()
        else:
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
        print()
        print('Succeeded: %d, failed: %d' % (len(worked), len(failed)))

    def json_format(self):
        pass

    def xml_format(self):
        pass

    def csv_format(self):
        pass

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


class Remote(base.ECMCommand):
    """ Interact with remote router's config stores. """

    name = 'remote'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(Get, default=True)
        self.add_subcommand(Set)
        self.add_subcommand(ConfigDefinition)

command_classes = [Remote]
