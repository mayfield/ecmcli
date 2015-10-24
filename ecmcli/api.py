"""
Some API handling code.  Predominantly this is to centralize common
alterations we make to API calls, such as filtering by router ids.
"""

import collections
import collections.abc
import fnmatch
import getpass
import html
import html.parser
import itertools
import os
import re
import shellish
import shelve
import shutil
import syndicate
import syndicate.client
import syndicate.data
import textwrap
import tornado
from syndicate.adapters.sync import LoginAuth


class HTMLJSONDecoder(syndicate.data.NormalJSONDecoder):

    def parse_object(self, data):
        data = super().parse_object(data)
        for key, value in data.items():
            if isinstance(value, str):
                data[key] = html.unescape(value)
        return data


def text_pager(data):
    width, height = shutil.get_terminal_size()
    i = 0
    for section in data:
        lines = textwrap.wrap(section, width-4)
        if not lines:
            i += 1
            print()
        for x in lines:
            i += 1
            if i >= height - 2:
                input("<Press enter to view next page>")
                i = 0
            print(x)


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


class ECMLogin(LoginAuth):

    def __init__(self, *args, **kwargs):
        self.initial_session_id = None
        self.session_mode = None
        super().__init__(*args, **kwargs)

    def use_login(self, username, password):
        self.login = None
        self.session_mode = False
        self.initial_session_id = None
        self.req_kwargs = dict(data=self.serializer({
            "username": username,
            "password": password
        }))

    def use_session(self, session_id):
        self.session_mode = True
        self.initial_session_id = session_id

    def check_login_response(self):
        super().check_login_response()
        resp = self.login.json()['data']
        if resp.get('success') is False:
            raise Unauthorized(resp['error_code'])

    def reset(self, request):
        try:
            del request.headers['Cookie']
        except KeyError:
            pass

    def __call__(self, request):
        if self.session_mode:
            if self.initial_session_id:
                self.reset(request)
                request.prepare_cookies({"sessionid": self.initial_session_id})
                self.initial_session_id = None
        elif self.login is None:
            self.reset(request)
            return super().__call__(request)
        return request


class ECMService(shellish.Eventer, syndicate.Service):

    site = 'https://cradlepointecm.com'
    api_prefix = '/api/v1'
    session_file = os.path.expanduser('~/.ecm_session')

    def __init__(self, **kwargs):
        super().__init__(uri='nope', urn=self.api_prefix,
                         serializer='htmljson', **kwargs)
        self.username = None
        self.session_id = None
        self.add_events([
            'start_request',
            'finish_request',
            'reset_auth'
        ])
        self.call_count = itertools.count()

    def clone(self, **varations):
        """ Produce a cloned instance of ourselves, including state. """
        clone = type(self)(**varations)
        copy = ('account', 'session_id', 'username', 'ident', 'uri', 'events',
                'call_count')
        for x in copy:
            value = getattr(self, x)
            if hasattr(value, 'copy'):  # containers
                value = value.copy()
            setattr(clone, x, value)
        clone.adapter.set_cookie('sessionid', clone.session_id)
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
        self.account = None
        self.uri = self.site
        self.adapter.auth = ECMLogin(url='%s%s/login/' % (self.site,
                                     self.api_prefix))
        if username or not self.load_session(try_last=True):
            self.login(username, password)

    def reset_auth(self):
        self.fire_event('reset_auth')
        self.adapter.set_cookie('sessionid', None)
        self.save_session(None)
        self.login()

    def login(self, username=None, password=None):
        try:
            username = username or input('Username: ')
        except RuntimeError:  # Readline (input) is not reentrant.
            raise Unauthorized('Unable to login in this context')
        if not self.load_session(username):
            self.set_auth(username, password or getpass.getpass())

    def set_auth(self, username, password=None, session_id=None):
        if password is not None:
            self.adapter.auth.use_login(username, password)
        elif session_id:
            self.adapter.auth.use_session(session_id)
        else:
            raise TypeError("password or session_id required")
        self.save_last_username(username)
        self.username = username
        self.ident = self.get('login')

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
        if self.session_id:
            self.set_auth(username, session_id=self.session_id)
            return True
        else:
            self.username = None
            return False

    def check_session(self):
        """ ECM sometimes updates the session token. We make sure we are in
        sync. """
        session_id = self.adapter.get_cookie('sessionid')
        if session_id != self.session_id:
            self.save_session({
                "id": session_id
            })
            self.session_id = session_id

    def finish_do(self, callid, result_func, *args, reraise=True, **kwargs):
        try:
            result = result_func(*args, **kwargs)
        except BaseException as e:
            self.fire_event('finish_request', callid, error=e)
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
            future = self._do(*args, **kwargs)
            on_fin = lambda f: self.finish_do(callid, f.result, reraise=False)
            tornado.ioloop.IOLoop.current().add_future(future, on_fin)
            return future
        else:
            return self.finish_do(callid, self._do, *args, **kwargs)

    def _do(self, *args, **kwargs):
        if self.account is not None:
            kwargs['account'] = self.account
        try:
            result = super().do(*args, **kwargs)
        except syndicate.client.ResponseError as e:
            self.handle_error(e)
            result = super().do(*args, **kwargs)
        except Unauthorized as e:
            print('Auth Error:', e)
            self.reset_auth()
            result = super().do(*args, **kwargs)
        self.check_session()
        return result

    def handle_error(self, error):
        """ Pretty print error messages and exit. """
        resp = error.response
        if resp.get('exception') == 'precondition_failed' and \
           resp['message'] == 'must_accept_tos':
            if self.accept_tos():
                return
            raise TOSRequired("WARNING: User did not accept terms")
        err = resp.get('exception') or resp.get('error_code')
        if err in ('login_failure', 'unauthorized'):
            self.reset_auth()
            return
        if resp.get('message'):
            err += '\n%s' % resp['message'].strip()
        raise SystemExit("Error: %s" % err)

    def accept_tos(self):
        for tos in self.get_pager('system_message', type='tos'):
            input("You must read and accept the terms of service to "
                  "continue: <press enter>")
            text_pager(str(shellish.htmlrender(tos['message'])).splitlines())
            print()
            accept = input('Type "accept" to comply with the TOS: ')
            if accept != 'accept':
                return False
            self.post('system_message_confirm', {
                "message": tos['resource_uri']
            })
            return True

    def glob_field(self, field, criteria):
        """ Convert the criteria into an API filter and test function to
        further refine the fetched results.  That is, the glob pattern will
        often require client side filtering after doing a more open ended
        server filter.  The client side test function will only be truthy
        when a value is in full compliance.  The server filters are simply
        to reduce high latency overhead. """
        filters = {}
        try:
            start, *globs, end = re.split(r'(\[.*\]|[\*?])', criteria)
        except ValueError:
            filters['%s__exact' % field] = criteria
        else:
            if start:
                filters['%s__startswith' % field] = start
            if end:
                filters['%s__endswith' % field] = end
        return filters, lambda x: fnmatch.fnmatchcase(x.get(field), criteria)

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
