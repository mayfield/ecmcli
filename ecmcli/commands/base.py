"""
Foundation components for commands.
"""

import collections
import shellish
from ecmcli import shell


def confirm(msg, exit=True):
    if input('%s (type "yes" to confirm)? ' % msg) != 'yes':
        if not exit:
            return False
        raise SystemExit('Aborted')
    return True


class ECMCommand(shellish.Command):
    """ Extensions for dealing with ECM's APIs. """

    Searcher = collections.namedtuple('Searcher', 'lookup, completer, help')
    Shell = shell.ECMShell

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

        def fn(startswith):
            return self.api_complete(resource, field, startswith)

        fn.__name__ = '<completer for %s:%s>' % (resource, field)
        return fn

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

    def make_searcher(self, resource, field_desc, **search_options):
        """ Return a Searcher instance for doing API based lookups.  This
        is primarily designed to meet needs of argparse arguments and tab
        completion. """

        fields = {}
        for x in field_desc:
            if isinstance(x, tuple):
                fields[x[0]] = x[1]
            else:
                fields[x] = x

        def lookup(terms, **options):
            merged_options = search_options.copy()
            merged_options.update(options)
            return self.api_search(resource, fields, terms,
                                   **merged_options)

        def complete(startswith):
            if ':' in startswith:
                field, value = startswith.split(':', 1)
                if field in fields:
                    results = self.api_complete(resource, fields[field], value)
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
