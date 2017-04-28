"""
Get and set remote values on series 3 routers.
"""

import collections
import csv
import datetime
import itertools
import shellish
import syndicate.data
import time
from . import base


class DeviceSelectorsMixin(object):
    """ Add arguments used for selecting devices. """

    search_fields = ['name', 'desc', 'mac', ('account', 'account.name'),
                     'asset_id', 'custom1', 'custom2',
                     ('group', 'group.name'),
                     ('firmware', 'actual_firmware.version'), 'ip_address',
                     ('product', 'product.name'), 'serial_number', 'state']

    def setup_args(self, parser):
        sg = parser.add_argument_group('selection filters')
        self.add_argument('--disjunction', '--or', action='store_true',
                          help="Logical OR the selection arguments.",
                          parser=sg)
        self.add_argument('--skip-offline', action='store_true',
                          help='Ignore devices that are offline.',
                          parser=sg)
        self.add_group_argument('--group', parser=sg)
        self.add_router_argument('--router', parser=sg)
        self.add_account_argument('--account', parser=sg)
        self.add_product_argument('--product', parser=sg)
        self.add_firmware_argument('--firmware', parser=sg)
        searcher = self.make_searcher('routers', self.search_fields)
        self.search_lookup = searcher.lookup
        self.add_search_argument(searcher, '--search', nargs=1, parser=sg)
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
            hit = self.api_res_lookup('groups', args['group'])
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
            hit = self.api_res_lookup('routers', args['router'])
            if hit:
                rids.append(hit['id'])
        if args.get('search'):
            sids = self.search_lookup(args['search'])
            if not sids:
                rids.append('-1')  # Ensure no match is possible softly.
            else:
                rids.extend(x['id'] for x in sids)
        if rids:
            filters['id__in'] = ','.join(rids)
        if args.get('disjunction'):
            filters = dict(_or='|'.join('%s=%s' % x for x in filters.items()))
        if args.get('skip_offline'):
            filters['state'] = 'online'
        return filters

    @shellish.ttl_cache(300)
    def completion_router_elect(self, **filters):
        """ Cached lookup of a router meeting the filters criteria to be used
        for completion lookups. """
        for x in self.api.get_pager('routers', page_size=1, state='online',
                                    expand='product',
                                    fields='id,product.series', **filters):
            if x['product']['series'] == 3:
                return x['id']

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
                options[key + '.'] = None  # Prevent trailing space.
        return set('.'.join(path + [x]) for x in options)

    @shellish.hone_cache(maxage=3600, refineby='container')
    def remote_lookup(self, rid_and_path):
        rid = rid_and_path[0]
        path = rid_and_path[1:]
        resp = self.api.get('remote', *path, id=rid)
        if resp and resp[0]['success'] and 'data' in resp[0]:
            return base.todict(resp[0]['data'], str_array_keys=True)


class Get(DeviceSelectorsMixin, base.ECMCommand):
    """ Get configs for a selection of routers. """

    name = 'get'

    def setup_args(self, parser):
        super().setup_args(parser)
        output_options = parser.add_argument_group('output options')
        or_group = output_options.add_mutually_exclusive_group()
        self.inject_table_factory(skip_formats=True)
        for x in ('json', 'csv', 'xml', 'table', 'tree'):
            self.add_argument('--%s' % x, dest='output', action='store_const',
                              const=x, parser=or_group)
        self.add_argument('path', metavar='REMOTE_PATH', nargs='?',
                          complete=self.try_complete_path, default='',
                          help='Dot notation path to config value; Eg. '
                               'status.wan.rules.0.enabled')
        self.add_file_argument('--output-file', '-o', mode='w', default='-',
                               metavar="OUTPUT_FILE", parser=output_options)
        self.add_argument('--repeat', type=float, metavar="SECONDS",
                          help="Repeat the request every N seconds. Only "
                          "appropriate for table format.")

        advanced = parser.add_argument_group('advanced options')
        self.add_argument('--concurrency', type=int, parser=advanced,
                          help='Maximum number of concurrent connections.')
        self.add_argument('--timeout', type=float, default=300,
                          parser=advanced, help='Maximum time in seconds for '
                          'each connection.')

    def run(self, args):
        filters = self.gen_selection_filters(args)
        outformat = args.output
        fallback_format = self.tree_format if not args.repeat else \
            self.table_format
        with args.output_file as f:
            if not outformat and hasattr(f.name, 'rsplit'):
                outformat = f.name.rsplit('.', 1)[-1]
            formatter = {
                'json': self.json_format,
                'xml': self.xml_format,
                'csv': self.csv_format,
                'table': self.table_format,
                'tree': self.tree_format,
            }.get(outformat) or fallback_format
            feed = lambda: self.api.remote(args.path, timeout=args.timeout,
                                           concurrency=args.concurrency,
                                           **filters)
            formatter(args, feed, file=f)

    def data_flatten(self, args, datafeed):
        """ Flatten out the results a bit for a consistent data format. """

        def responses():
            for cres in datafeed:
                resmap = collections.OrderedDict((x['path'], x['data'])
                                                 for x in cres['results'])
                emit = {"results": resmap}
                for x in ('desc', 'custom1', 'custom2', 'asset_id',
                          'ip_address', 'mac', 'name', 'serial_number',
                          'state'):
                    emit[x] = cres['router'].get(x)
                yield emit
        args = vars(args).copy()
        for key, val in list(args.items()):
            if key.startswith('api_') or \
               key.startswith(self.arg_label_fmt.split('%', 1)[0]):
                del args[key]
            else:
                args[key] = repr(val)
        return {
            "time": datetime.datetime.utcnow().isoformat(),
            "args": args,
            "responses": responses()
        }

    def make_response_tree(self, resp):
        """ Render a tree of the response data if it was successful otherwise
        return a formatted error response.  The return type is iterable. """
        if resp['success']:
            resmap = collections.OrderedDict((x['path'], x['data'])
                                             for x in resp['results'])
            return shellish.treeprint(resmap, render_only=True)
        else:
            error = resp.get('message', resp.get('reason',
                                                 resp.get('exception')))
            return ['<b><red>%s</red></b>' % error]

    def tree_format(self, args, results_feed, file):
        if args.repeat:
            raise SystemExit('Repeat mode not supported for tree format.')
        worked = failed = 0

        def cook():
            nonlocal worked, failed
            for x in results_feed():
                if x['success']:
                    worked += 1
                    status = '<green>yes</green>'
                else:
                    failed += 1
                    status = '<red>no</red>'
                feeds = [
                    [x['router']['name']],
                    [x['router']['id']],
                    [status],
                    self.make_response_tree(x)
                ]
                for row in itertools.zip_longest(*feeds, fillvalue=''):
                    yield row

        headers = ['Name', 'ID', 'Success', 'Response']
        with self.make_table(headers=headers, file=file) as t:
            t.print(cook())
            if worked:
                t.print_footer('Succeeded: %d' % worked)
            if failed:
                t.print_footer('Failed: %d' % failed)

    def table_format(self, args, results_feed, file):
        table = None
        if not args.repeat:
            status = lambda x: ' - %s' % ('PASS' if x['success'] else 'FAIL')
        else:
            status = lambda x: ''
        while True:
            start = time.monotonic()
            results = list(results_feed())
            if table is None:
                headers = ['%s (%s)%s' % (x['router']['name'], x['id'],
                           status(x)) for x in results]
                order = [x['id'] for x in results]
                table = self.make_table(headers=headers, file=file)
            else:
                # Align columns with the first requests ordering.
                results.sort(key=lambda x: order.index(x['id']))
            trees = map(self.make_response_tree, results)
            table.print(itertools.zip_longest(*trees, fillvalue=''))
            if not args.repeat:
                break
            else:
                tillnext = args.repeat - (time.monotonic() - start)
                time.sleep(max(tillnext, 0))

    def json_format(self, args, results_feed, file):
        if args.repeat:
            raise SystemExit('Repeat mode not supported for json format.')
        jenc = syndicate.data.NormalJSONEncoder(indent=4, sort_keys=True)
        data = self.data_flatten(args, results_feed())
        data['responses'] = list(data['responses'])
        print(jenc.encode(data), file=file)

    def xml_format(self, args, results_feed, file):
        if args.repeat:
            raise SystemExit('Repeat mode not supported for xml format.')
        doc = base.toxml(self.data_flatten(args, results_feed()))
        print("<?xml encoding='UTF-8'?>", file=file)
        print(doc.toprettyxml(indent=' ' * 4), end='', file=file)

    def csv_format(self, args, results_feed, file):
        if args.repeat:
            raise SystemExit('Repeat mode not supported for csv format.')
        data = list(self.data_flatten(args, results_feed())['responses'])
        tuples = [[(('DATA:%s' % xx[0]).strip('.'), xx[1])
                   for xx in base.totuples(x.get('results', []))]
                  for x in data]
        keys = sorted(set(xx[0] for x in tuples for xx in x))
        static_fields = (
            ('id', 'ROUTER_ID'),
            ('mac', 'ROUTER_MAC'),
            ('name', 'ROUTER_NAME'),
            ('success', 'SUCCESS'),
            ('exception', 'ERROR')
        )
        fields = [x[0] for x in static_fields] + keys
        header = [x[1] for x in static_fields] + keys
        writer = csv.DictWriter(file, fieldnames=fields,
                                extrasaction='ignore')
        writer.writerow(dict(zip(fields, header)))
        for xtuple, x in zip(tuples, data):
            x.update(dict(xtuple))
            writer.writerow(x)


class Set(DeviceSelectorsMixin, base.ECMCommand):
    """ Set a config value on a selection of devices and/or groups. """

    name = 'set'

    def setup_args(self, parser):
        super().setup_args(parser)
        in_group = parser.add_mutually_exclusive_group(required=True)
        self.add_argument('--input-data', '-d', metavar="INPUT_DATA",
                          help="JSON formated input data.", parser=in_group)
        self.add_file_argument('--input-file', '-i', metavar="INPUT_FILE",
                               parser=in_group)
        self.add_argument('--dry-run', '--manifest', help="Do not set a "
                          "config.  Generate a manifest of what would be "
                          "done and the potential peril if executed.")

    def run(self, args):
        raise NotImplementedError()


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
        self.add_subcommand(Diff)

command_classes = [Remote]
