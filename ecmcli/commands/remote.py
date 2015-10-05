"""
Get and set configs for routers and groups.
"""

import argparse
import functools
import itertools
import json
import shellish
import time
from . import base


def walk_config(key, config):
    if key is None:
        return config
    offt = config
    for x in key.split('.'):
        try:
            offt = offt[x]
        except KeyError:
            return None
        except TypeError:
            if x.isnumeric():
                try:
                    offt = offt[int(x)]
                except IndexError:
                    return None
            else:
                return None
    return offt


def todict(obj):
    """ On a tree of list and dict types convert the lists to dict types. """
    if isinstance(obj, list):
        return dict((k, todict(v)) for k, v in zip(itertools.count(), obj))
    elif isinstance(obj, dict):
        obj = dict((k, todict(v)) for k, v in obj.items())
    return obj


class DeviceSelectorsMixin(object):
    """ Add arguments used for selecting devices. """

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

    def get_selection(self, args_namespace, **pager_filters):
        """ Return the routers matched by our selection criteria.  Note that
        the group selection is only used to get a list of devices. """
        args = vars(args_namespace)
        filters = {}
        if args.get('group'):
            hit = self.api.get_by_id_or_name('groups', args['group'],
                                             product__series=3,
                                             required=False)
            if hit:
                filters['group'] = hit['id']
        if args.get('router'):
            hit = self.api.get_by_id_or_name('routers', args['router'],
                                             product__series=3,
                                             state='online', required=False)
            if hit:
                filters['id'] = hit['id']
        if args.get('account'):
            hit = self.api.get_by_id_or_name('accounts', args['account'],
                                             required=False)
            if hit:
                filters['account'] = hit['id']
        if args.get('product'):
            hit = self.api.get_by_id_or_name('products', args['product'],
                                             series=3, required=False)
            if hit:
                filters['product'] = hit['id']
        if args.get('firmware'):
            filters['actual_firmware.version'] = args['firmware']
        if args.get('disjunction'):
            filters = dict(_or='|'.join('%s=%s' % x for x in filters.items()))
        if args.get('skip_offline'):
            filters['state'] = 'online'
        filters.update(pager_filters)
        return self.api.get_pager('routers', product__series=3, **filters)

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

    def try_complete_path(self, prefix, args=None):
        for x in self.get_selection(args, state='online', page_size=1):
            if x['state'] == 'online':
                rid = x['id']
                break
        else:
            return set(('[NO ONLINE ROUTERS FOUND]', ' '))
        parts = prefix.split('.')
        if len(parts) > 1:
            path = parts[:-1]
            prefix = parts[-1]
        else:
            path = []
        cs = self.cached_remote_single(tuple(path), rid)
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

    @functools.lru_cache()
    def cached_remote_single(self, path, rid):
        resp = self.api.get('remote', *path, id=rid)
        if resp and resp[0]['success'] and 'data' in resp[0]:
            return todict(resp[0]['data'])

    def run(self, args):
        routers = self.get_selection(args)
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
                    resp = ['ERROR: <b>%s</b>' % x['reason']]
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
