"""
Some API handling code.  Predominantly this is to centralize common
alterations we make to API calls, such as filtering by router ids.
"""

import asyncio
import cellulario
import collections
import collections.abc
import fnmatch
import html
import html.parser
import itertools
import logging
import os
import re
import requests
import shellish
import shelve
import shutil
import syndicate
import syndicate.client
import syndicate.data
import warnings
from syndicate.adapters.sync import SyncPager

logger = logging.getLogger('ecm.api')
JWT_COOKIE = 'cpAccountsJwt'
LEGACY_COOKIE = 'sessionid'


class HTMLJSONDecoder(syndicate.data.NormalJSONDecoder):

    def parse_object(self, data):
        data = super().parse_object(data)
        for key, value in data.items():
            if isinstance(value, str):
                data[key] = html.unescape(value)
        return data


syndicate.data.serializers['htmljson'] = syndicate.data.Serializer(
    'application/json',
    syndicate.data.serializers['json'].encode,
    HTMLJSONDecoder().decode
)


class AuthFailure(SystemExit):
    pass


class Unauthorized(AuthFailure):
    """ Either the login is bad or the session is expired. """
    pass


class TOSRequired(AuthFailure):
    """ The terms of service have not been accepted yet. """
    pass


class ECMLogin(object):

    sso_url = 'https://accounts.cradlepointecm.com/login'
    primer_url = 'https://cradlepointecm.com/api/v1/products/?limit=1'
    legacy_url = 'https://cradlepointecm.com/api/v1/login/'

    def __init__(self, api):
        self._site = api.site
        self._session = api.adapter.session
        self._login_attempted = None
        self.sso = None

    def set_creds(self, username, password):
        self.session_mode = False
        self._login_attempted = False
        self._username = username
        self._password = password

    def set_session(self, id, jwt):
        self.session_mode = True
        self.initial_session_id = id
        self.initial_session_jwt = jwt

    def reset(self, request):
        try:
            del request.headers['Cookie']
        except KeyError:
            pass

    def __call__(self, request):
        if self.session_mode:
            if self.initial_session_jwt:
                self.reset(request)
                logger.info("Attempting to use saved session for login...")
                self._session.cookies.update({
                    JWT_COOKIE: self.initial_session_jwt,
                    LEGACY_COOKIE: self.initial_session_id
                })
                self.initial_session_jwt = None
                self.initial_session_id = None
                logger.info("Loaded Session for SSO")
                self.sso = True
            elif self.initial_session_id:
                self.reset(request)
                self._session.cookies[LEGACY_COOKIE] = self.initial_session_id
                self.initial_session_id = None
                logger.info("Loaded Session for Legacy Auth")
                self.sso = False
        elif not self._login_attempted:
            self._login_attempted = True
            self.reset(request)
            logger.info("Attempting to login with credentials...")
            creds = {
                "username": self._username,
                "password": self._password,
            }
            resp = requests.post(self.sso_url, data=creds,
                                 allow_redirects=False)
            if JWT_COOKIE in resp.cookies:
                logger.info("SSO Login Success")
                self._session.cookies[JWT_COOKIE] = resp.cookies[JWT_COOKIE]
                logger.debug("Priming session...")
                self._session.get(self.primer_url)
                self.sso = True
            else:
                logger.info("SSO auth failed, trying legacy auth")
                resp = requests.post(self.legacy_url, json=creds)
                if resp.status_code not in (200, 201):
                    raise Unauthorized('Invalid Login')
                self._session.cookies[LEGACY_COOKIE] = resp.cookies[LEGACY_COOKIE]
                self.sso = False
        request.prepare_cookies(self._session.cookies)
        return request


class AberrantPager(SyncPager):
    """ The time-series resources in ECM have broken paging.  limit and offset
    mean different things, next is erroneous and total_count is a lie. """

    def __init__(self, getter, path, kwargs):
        self._limit = kwargs.pop('limit')
        self._offset = kwargs.pop('offset', 0)
        self._done = False
        super().__init__(getter, path, kwargs)

    def __len__(self):
        """ Count is not supported but we'd like to support truthy tests
        still. """
        return 0 if self._done else 1

    def _get_next_page(self):
        assert not self._done, 'iterator exhausted'
        page = self.getter(*self.path, limit=self._limit,
                           offset=self._offset, **self.kwargs)
        size = len(page)
        if not size:
            self._done = True
            raise StopIteration()
        self._offset += size
        self._limit += size
        return page

    def __next__(self):
        if self._done:
            raise StopIteration()
        if not self.page:
            self.page = self._get_next_page()
        return self.page.pop(0)


class ECMService(shellish.Eventer, syndicate.Service):

    site = 'https://cradlepointecm.com'
    api_prefix = '/api/v1'
    session_file = os.path.expanduser('~/.ecm_session')
    globs = {
        'seq': r'\[.*\]',
        'wild': r'[*?]',
        'set': r'\{.*\}'
    }
    re_glob_matches = re.compile('|'.join('(?P<%s>%s)' % x
                              for x in globs.items()))
    re_glob_sep = re.compile('(%s)' % '|'.join(globs.values()))
    default_remote_concurrency = 20
    # Resources that don't page correctly.
    aberrant_pager_resources = {
        'router_alerts',
        'activity_logs',
    }

    def __init__(self, **kwargs):
        super().__init__(uri='nope', urn=self.api_prefix,
                         serializer='htmljson', **kwargs)
        if not self.async:
            a = requests.adapters.HTTPAdapter(max_retries=3)
            self.adapter.session.mount('https://', a)
            self.adapter.session.mount('http://', a)
        self.username = None
        self.session_id = None
        self.session_jwt = None
        self.add_events([
            'start_request',
            'finish_request',
            'reset_auth'
        ])
        self.call_count = itertools.count()

    def clone(self, **varations):
        """ Produce a cloned instance of ourselves, including state. """
        clone = type(self)(**varations)
        copy = ('parent_account', 'session_id', 'session_jwt', 'username',
                'ident', 'uri', '_events', 'call_count')
        for x in copy:
            value = getattr(self, x)
            if hasattr(value, 'copy'):  # containers
                value = value.copy()
            setattr(clone, x, value)
        clone.adapter.set_cookie(LEGACY_COOKIE, clone.session_id)
        clone.adapter.set_cookie(JWT_COOKIE, clone.session_jwt)
        return clone

    @property
    def default_page_size(self):
        """ Dynamically change the page size to the screen height. """
        # Underflow the term height by a few rows to give a bit of context
        # for each page.  For simple cases the output will pause on each
        # page and this gives them a bit of old data or header data to look
        # at while the next page is being loaded.
        page_size = shutil.get_terminal_size()[1] - 4
        return max(20, min(100, page_size))

    def connect(self, site=None, username=None, password=None):
        if site:
            self.site = site
        self.parent_account = None
        self.uri = self.site
        self.adapter.auth = ECMLogin(self)
        if username:
            self.login(username, password)
        elif not self.load_session(try_last=True):
            raise Unauthorized('No valid sessions found')

    def reset_auth(self):
        self.fire_event('reset_auth')
        self.adapter.set_cookie(LEGACY_COOKIE, None)
        self.adapter.set_cookie(JWT_COOKIE, None)
        self.save_session(None)
        self.ident = None

    def login(self, username=None, password=None):
        if not self.load_session(username):
            self.set_auth(username, password)

    def set_auth(self, username, password=None, session_id=None,
                 session_jwt=None):
        if password is not None:
            self.adapter.auth.set_creds(username, password)
        elif session_id:
            self.adapter.auth.set_session(session_id, session_jwt)
        else:
            raise TypeError("password or session_id required")
        self.save_last_username(username)
        self.username = username
        self.ident = self.get('login')
        if self.adapter.auth.sso:
            self.ident['user']['username'] = self.ident['user']['email']

    def get_session(self, username=None, use_last=False):
        if use_last:
            if username is not None:
                raise RuntimeError("use_last and username are exclusive")
        elif username is None:
            raise TypeError("username required unless use_last=True")
        with shelve.open(self.session_file) as s:
            try:
                site = s[self.uri]
                if not username:
                    username = site['last_username']
                return username, site['sessions'][username]
            except KeyError:
                return None, None

    def save_last_username(self, username):
        with shelve.open(self.session_file) as s:
            site = s.get(self.uri, {})
            site['last_username'] = username
            s[self.uri] = site  # Required to persist; see shelve docs.

    def save_session(self, session):
        with shelve.open(self.session_file) as s:
            site = s.get(self.uri, {})
            sessions = site.setdefault('sessions', {})
            sessions[self.username] = session
            s[self.uri] = site  # Required to persist; see shelve docs.

    def load_session(self, username=None, try_last=False):
        username, session = self.get_session(username, use_last=try_last)
        self.session_id = session['id'] if session else None
        self.session_jwt = session.get('jwt') if session else None
        if self.session_id:
            self.set_auth(username, session_id=self.session_id,
                          session_jwt=self.session_jwt)
            return True
        else:
            self.username = None
            return False

    def check_session(self):
        """ ECM sometimes updates the session token. We make sure we are in
        sync. """
        try:
            session_id = self.adapter.get_cookie(LEGACY_COOKIE)
        except KeyError:
            session_id = None
        try:
            session_jwt = self.adapter.get_cookie(JWT_COOKIE)
        except KeyError:
            session_jwt = None
        if session_id != self.session_id or session_jwt != self.session_jwt:
            logger.info("Saving Session: %s %s" % (session_id, session_jwt))
            self.save_session({
                "id": session_id,
                "jwt": session_jwt
            })
            self.session_id = session_id
            self.session_jwt = session_jwt

    def finish_do(self, callid, result_func, *args, reraise=True, **kwargs):
        try:
            result = result_func(*args, **kwargs)
        except BaseException as e:
            self.fire_event('finish_request', callid, exc=e)
            if reraise:
                raise e
            else:
                return
        else:
            self.fire_event('finish_request', callid, result=result)
        return result

    def do(self, *args, **kwargs):
        """ Wrap some session and error handling around all API actions. """
        callid = next(self.call_count)
        self.fire_event('start_request', callid, args=args, kwargs=kwargs)
        if self.async:
            on_fin = lambda f: self.finish_do(callid, f.result, reraise=False)
            future = asyncio.ensure_future(self._do(*args, **kwargs))
            future.add_done_callback(on_fin)
            return future
        else:
            return self.finish_do(callid, self._do, *args, **kwargs)

    def _do(self, *args, **kwargs):
        if self.parent_account is not None:
            kwargs['parentAccount'] = self.parent_account
        try:
            result = super().do(*args, **kwargs)
        except syndicate.client.ResponseError as e:
            self.handle_error(e)
            result = super().do(*args, **kwargs)
        except Unauthorized as e:
            self.reset_auth()
            raise e
        self.check_session()
        return result

    def handle_error(self, error):
        """ Pretty print error messages and exit. """
        resp = error.response
        if resp.get('exception') == 'precondition_failed' and \
           resp['message'] == 'must_accept_tos':
            raise TOSRequired('Must accept TOS')
        err = resp.get('exception') or resp.get('error_code')
        if err in ('login_failure', 'unauthorized'):
            self.reset_auth()
            raise Unauthorized(err)
        if resp.get('message'):
            err += '\n%s' % resp['message'].strip()
        raise SystemExit("Error: %s" % err)

    def glob_match(self, string, pattern):
        """ Add bash style {a,b?,c*c} set matching to fnmatch. """
        sets = []
        for x in self.re_glob_matches.finditer(pattern):
            match = x.group('set')
            if match is not None:
                prefix = pattern[:x.start()]
                suffix = pattern[x.end():]
                for s in match[1:-1].split(','):
                    sets.append(prefix + s + suffix)
        if not sets:
            sets = [pattern]
        return any(fnmatch.fnmatchcase(string, x) for x in sets)

    def glob_field(self, field, criteria):
        """ Convert the criteria into an API filter and test function to
        further refine the fetched results.  That is, the glob pattern will
        often require client side filtering after doing a more open ended
        server filter.  The client side test function will only be truthy
        when a value is in full compliance.  The server filters are simply
        to reduce high latency overhead. """
        filters = {}
        try:
            start, *globs, end = self.re_glob_sep.split(criteria)
        except ValueError:
            filters['%s__exact' % field] = criteria
        else:
            if start:
                filters['%s__startswith' % field] = start
            if end:
                filters['%s__endswith' % field] = end
        return filters, lambda x: self.glob_match(x.get(field), criteria)

    def get_by(self, selectors, resource, criteria, required=True, **options):
        if isinstance(selectors, str):
            selectors = [selectors]
        for field in selectors:
            sfilters, test = self.glob_field(field, criteria)
            filters = options.copy()
            filters.update(sfilters)
            for x in self.get_pager(resource, **filters):
                if test is None or test(x):
                    return x
        if required:
            raise SystemExit("%s not found: %s" % (resource[:-1].capitalize(),
                             criteria))

    def get_by_id_or_name(self, resource, id_or_name, **kwargs):
        selectors = ['name']
        if id_or_name.isnumeric():
            selectors.insert(0, 'id')
        return self.get_by(selectors, resource, id_or_name, **kwargs)

    def glob_pager(self, *args, **kwargs):
        """ Similar to get_pager but use glob filter patterns.  If arrays are
        given to a filter arg it is converted to the appropriate disjunction
        filters.  That is, if you ask for field=['foo*', 'bar*'] it will return
        entries that start with `foo` OR `bar`.  The normal behavior would
        produce a paradoxical query staying it had to start with both. """
        exclude = {"expand", "limit", "timeout", "_or", "page_size", "urn",
                   "data", "callback"}
        iterable = lambda x: isinstance(x, collections.abc.Iterable) and \
                             not isinstance(x, str)
        glob_tests = []
        glob_filters = collections.defaultdict(list)
        for fkey, fval in list(kwargs.items()):
            if fkey in exclude or '__' in fkey or '.' in fkey:
                continue
            kwargs.pop(fkey)
            fvals = [fval] if not iterable(fval) else fval
            gcount = 0
            for gval in fvals:
                gcount += 1
                filters, test = self.glob_field(fkey, gval)
                for query, term in filters.items():
                    glob_filters[query].append(term)
                if test:
                    glob_tests.append(test)
            # Scrub out any exclusive queries that will prevent certain client
            # side matches from working.  Namely if one pattern can match by
            # `startswith`, for example, but others can't we must forgo
            # inclusion of this server side filter to prevent stripping out
            # potentially valid responses for the other more open-ended globs.
            for gkey, gvals in list(glob_filters.items()):
                if len(gvals) != gcount:
                    del glob_filters[gkey]
        disjunctions = []
        disjunct = kwargs.pop('_or', None)
        if disjunct is not None:
            if isinstance(disjunct, collections.abc.Iterable) and \
               not isinstance(disjunct, str):
                disjunctions.extend(disjunct)
            else:
                disjunctions.append(disjunct)
        disjunctions.extend('|'.join('%s=%s' % (query, x) for x in terms)
                            for query, terms in glob_filters.items())
        if disjunctions:
            kwargs['_or'] = disjunctions
        stream = self.get_pager(*args, **kwargs)
        if not glob_tests:
            return stream
        else:

            def glob_scrub():
                for x in stream:
                    if any(t(x) for t in glob_tests):
                        yield x
            return glob_scrub()

    def _routers_slice(self, routers, size):
        """ Pull a slice of s3 routers out of a generator. """
        while True:
            page = list(itertools.islice(routers, size))
            if not page:
                return {}
            idmap = dict((x['id'], x) for x in page
                         if x['product']['series'] == 3)
            if idmap:
                return idmap

    def remote(self, path, **kwargs):
        """ Generator for remote data with globing support and smart
        paging. """
        if '/' in path:
            warnings.warn("Use '.' instead of '/' for path argument.")
        path_parts = path.split('.')
        server_path = []
        globs = []
        for i, x in enumerate(path_parts):
            if self.re_glob_sep.search(x):
                globs.extend(path_parts[i:])
                break
            else:
                server_path.append(x)

        def expand_globs(base, tests, context=server_path):
            if not tests:
                yield '.'.join(context), base
                return
            if isinstance(base, dict):
                items = base.items()
            elif isinstance(base, list):
                items = [(str(i), x) for i, x in enumerate(base)]
            else:
                return
            test = tests[0]
            for key, val in items:
                if self.glob_match(key, test):
                    if len(tests) == 1:
                        yield '.'.join(context + [key]), val
                    else:
                        yield from expand_globs(val, tests[1:],
                                                context + [key])
        for x in self.fetch_remote(server_path, **kwargs):
            if 'data' in x:
                x['results'] = [{"path": k, "data": v}
                                for k, v in expand_globs(x['data'], globs)]
                x['_data'] = x['data']
                del x['data']
            else:
                x['results'] = []
            yield x

    def fetch_remote(self, path, concurrency=None, timeout=None, **query):
        cell = cellulario.IOCell(coord='pool')
        if concurrency is None:
            concurrency = self.default_remote_concurrency
        elif concurrency < 1:
            raise ValueError("Concurrency less than 1")
        page_concurrency = min(4, concurrency)
        page_slice = max(10, round((concurrency / page_concurrency) * 1.20))
        api = self.clone(async=True, loop=cell.loop, request_timeout=timeout,
                         connect_timeout=timeout)

        @cell.tier()
        def start(route):
            probe = yield from api.get('routers', limit=1, fields='id',
                                       **query)
            for i in range(0, probe.meta['total_count'], page_slice):
                yield from route.emit(i, page_slice)

        @cell.tier(pool_size=page_concurrency)
        def get_page(route, offset, limit):
            page = yield from api.get('routers', expand='product',
                                      offset=offset, limit=limit, **query)
            for router in page:
                if router['product']['series'] != 3:
                    continue
                yield from route.emit(router)

        @cell.tier(pool_size=concurrency)
        def get_remote(route, router):
            try:
                res = (yield from api.get('remote', *path, id=router['id']))[0]
            except Exception as e:
                res = {
                    "success": False,
                    "exception": type(e).__name__,
                    "message": str(e),
                    "id": int(router['id'])
                }
            res['router'] = router
            yield from route.emit(res)

        @cell.cleaner
        def close():
            api.close()
        return cell

    def get_pager(self, *path, **kwargs):
        resource = path[0].split('/', 1)[0] if path else None
        if resource in self.aberrant_pager_resources:
            assert not self.async, 'Only sync mode supported for: %s' % resource
            page_arg = kwargs.pop('page_size', None)
            limit_arg = kwargs.pop('limit', None)
            kwargs['limit'] = page_arg or limit_arg or self.default_page_size
            return AberrantPager(self.get, path, kwargs)
        else:
            return super().get_pager(*path, **kwargs)
