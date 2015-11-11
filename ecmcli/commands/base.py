"""
Foundation components for commands.
"""

import collections
import functools
import itertools
import shellish
from xml.dom import minidom


def toxml(data, root_tag='ecmcli'):
    """ Convert python container tree to xml. """
    dom = minidom.getDOMImplementation()
    document = dom.createDocument(None, root_tag, None)
    root = document.documentElement

    def crawl(obj, parent):
        try:
            for key, value in sorted(obj.items()):
                el = document.createElement(key)
                parent.appendChild(el)
                crawl(value, el)
        except AttributeError:
            if not isinstance(obj, str) and hasattr(obj, '__iter__'):
                obj = list(obj)
                for i, value in enumerate(obj, 1):
                    try:
                        array_id = value.pop('_id_')
                    except (TypeError, KeyError, AttributeError):
                        pass
                    else:
                        parent.setAttribute('id', array_id)
                    crawl(value, parent)
                    if i < len(obj):
                        newparent = document.createElement(parent.tagName)
                        parent.parentNode.appendChild(newparent)
                        parent = newparent
            elif obj is not None:
                parent.setAttribute('type', type(obj).__name__)
                parent.appendChild(document.createTextNode(str(obj)))
    crawl(data, root)
    return root


def totuples(data):
    """ Convert python container tree to key/value tuples. """

    def crawl(obj, path):
        try:
            for key, value in sorted(obj.items()):
                yield from crawl(value, path + (key,))
        except AttributeError:
            if not isinstance(obj, str) and hasattr(obj, '__iter__'):
                for i, value in enumerate(obj):
                    yield from crawl(value, path + (i,))
            else:
                yield '.'.join(map(str, path)), obj
    return crawl(data, ())


def todict(obj, str_array_keys=False):
    """ On a tree of list and dict types convert the lists to dict types. """
    if isinstance(obj, list):
        key_conv = str if str_array_keys else lambda x: x
        return dict((key_conv(k), todict(v, str_array_keys))
                    for k, v in zip(itertools.count(), obj))
    elif isinstance(obj, dict):
        obj = dict((k, todict(v, str_array_keys)) for k, v in obj.items())
    return obj


class ECMCommand(shellish.Command):
    """ Extensions for dealing with ECM's APIs. """

    use_pager = True
    Searcher = collections.namedtuple('Searcher', 'lookup, completer, help')

    def api_complete(self, resource, field, startswith):
        options = {}
        if '.' in field:
            options['expand'] = field.rsplit('.', 1)[0]
        if startswith:
            options['%s__startswith' % field] = startswith
        resources = self.api.get_pager(resource, fields=field, **options)
        return set(self.res_flatten(x, {field: field})[field]
                   for x in resources)

    def make_completer(self, resource, field):
        """ Return a function that completes for the API .resource and
        returns a list of .field values.  The function returned takes
        one argument to filter by an optional 'startswith' criteria. """

        @shellish.hone_cache(maxage=300)
        def cached(startswith):
            return self.api_complete(resource, field, startswith)

        def wrap(startswith, *args):
            return cached(startswith)

        wrap.__name__ = '<completer for %s:%s>' % (resource, field)
        return wrap

    def api_search(self, resource, fields, terms, match='icontains',
                   **options):
        fields = fields.copy()
        or_terms = []
        for term in terms:
            if ':' in term:
                field, value = term.split(':', 1)
                if field in fields:
                    options['%s__%s' % (fields[field], match)] = value
                    fields.pop(field)
                    continue
            query = [('%s__%s' % (x, match), term)
                     for x in fields.values()]
            or_terms.extend('='.join(x) for x in query)
        if or_terms:
            options['_or'] = '|'.join(or_terms)
        return self.api.get_pager(resource, **options)

    def res_flatten(self, resource, fields):
        """ Flat version of resource based on field_desc. """
        resp = {}
        for friendly, dotpath in fields.items():
            offt = resource
            for x in dotpath.split('.'):
                try:
                    offt = offt[x]
                except (ValueError, TypeError, KeyError):
                    offt = None
                    break
            resp[friendly] = offt
        return resp

    def confirm(self, msg, exit=True):
        assert not self.use_pager
        if input('%s (type "yes" to confirm)? ' % msg) != 'yes':
            if not exit:
                return False
            raise SystemExit('Aborted')
        return True

    def make_searcher(self, resource, field_desc, **search_options):
        """ Return a Searcher instance for doing API based lookups.  This
        is primarily designed to meet needs of argparse arguments and tab
        completion. """

        field_completers = {}
        fields = {}
        for x in field_desc:
            label, field = x if isinstance(x, tuple) else (x, x)
            fields[label] = field
            field_completers[label] = self.make_completer(resource, field)

        def lookup(terms, **options):
            merged_options = search_options.copy()
            merged_options.update(options)
            return self.api_search(resource, fields, terms,
                                   **merged_options)

        def complete(startswith, args):
            if ':' in startswith:
                field, value = startswith.split(':', 1)
                if field in fields:
                    results = field_completers[field](value)
                    return set('%s:%s' % (field, x) for x in results
                               if x is not None)
            if not startswith:
                terms = set('%s:<MATCH_CRITERIA>' % x for x in fields)
                return terms | {'<SEARCH_CRITERIA>'}
            else:
                expands = [x.rsplit('.', 1)[0] for x in fields.values()
                           if '.' in x]
                options = {"expand": ','.join(expands)} if expands else {}

                results = self.api_search(resource, fields, [startswith],
                                          match='startswith', **options)
                return set(val for res in results
                           for val in self.res_flatten(res, fields).values()
                           if val and str(val).startswith(startswith))

        help = 'Search "%s" on fields: %s' % (resource, ', '.join(fields))
        return self.Searcher(lookup, complete, help)

    def add_completer_argument(self, *keys, resource=None, res_field=None,
                               **options):
        if not keys:
            keys = ('ident',)
            nargs = options.get('nargs')
            if (isinstance(nargs, int) and nargs > 1) or \
               nargs and nargs in '+*':
                keys = ('idents',)
        options["complete"] = self.make_completer(resource, res_field)
        return self.add_argument(*keys, **options)

    def add_router_argument(self, *keys, **options):
        options.setdefault('metavar', 'ROUTER_ID_OR_NAME')
        options.setdefault('help', 'The ID or name of a router.')
        return self.add_completer_argument(*keys, resource='routers',
                                           res_field='name', **options)

    def add_group_argument(self, *keys, **options):
        options.setdefault('metavar', 'GROUP_ID_OR_NAME')
        options.setdefault('help', 'The ID or name of a group.')
        return self.add_completer_argument(*keys, resource='groups',
                                           res_field='name', **options)

    def add_account_argument(self, *keys, **options):
        options.setdefault('metavar', 'ACCOUNT_ID_OR_NAME')
        options.setdefault('help', 'The ID or name of an account.')
        return self.add_completer_argument(*keys, resource='accounts',
                                           res_field='name', **options)

    def add_product_argument(self, *keys, **options):
        options.setdefault('metavar', 'PRODUCT_ID_OR_NAME')
        options.setdefault('help', 'Product name, Eg. "MBR1400".')
        return self.add_completer_argument(*keys, resource='products',
                                           res_field='name', **options)

    def add_firmware_argument(self, *keys, **options):
        options.setdefault('metavar', 'FIRMWARE_VERSION')
        options.setdefault('help', 'Version identifier, Eg. "5.4.1".')
        return self.add_completer_argument(*keys, resource='firmwares',
                                           res_field='version', **options)

    def add_role_argument(self, *keys, **options):
        options.setdefault('metavar', 'ROLE')
        options.setdefault('help', 'Authorization role, Eg. "admin".')
        return self.add_completer_argument(*keys, resource='roles',
                                           res_field='name', **options)

    def add_user_argument(self, *keys, **options):
        options.setdefault('metavar', 'USERNAME')
        options.setdefault('help', 'Login user.')
        return self.add_completer_argument(*keys, resource='users',
                                           res_field='username', **options)

    def add_search_argument(self, searcher, *keys, **options):
        if not keys:
            keys = ('search',)
        options.setdefault('metavar', 'SEARCH_CRITERIA')
        options.setdefault('nargs', '+')
        return self.add_argument(*keys, help=searcher.help,
                                 complete=searcher.completer, **options)

    def inject_table_factory(self, *args, **kwargs):
        """ Use this in setup_args to produce a shellish.Table factory.  The
        resultant factory will have defaults provided from the command line
        args added in this method.  It can be called with any standard Table
        arguments too. """
        make_table_options = self.add_table_arguments(*args, **kwargs)

        def setup_make_table(argument_ns):
            options = make_table_options(argument_ns)
            self.make_table = functools.partial(shellish.Table, **options)
        self.add_listener('prerun', setup_make_table)
