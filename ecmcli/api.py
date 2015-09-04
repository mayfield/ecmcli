"""
Some API handling code.  Predominantly this is to centralize common
alterations we make to API calls, such as filtering by router ids.
"""

import getpass
import hashlib
import html
import html.parser
import json
import os
import shutil
import syndicate
import syndicate.client
import syndicate.data
import textwrap
from syndicate.adapters.sync import LoginAuth


class HTMLJSONDecoder(syndicate.data.NormalJSONDecoder):

    def parse_object(self, data):
        data = super().parse_object(data)
        for key, value in data.items():
            if isinstance(value, str):
                data[key] = html.unescape(value)
        return data


class TOSParser(html.parser.HTMLParser):

    end = '\033[0m'
    tags = {
        'b': ('\033[1m', end),
        'h2': ('\n\033[1m', end+'\n'),
        'h1': ('\n\033[1m', end+'\n'),
        'ul': ('\033[4m', end),
        'p': ('\n', '\n')
    }
    ignore = [
        'style',
        'script',
        'head'
    ]

    def __init__(self):
        self.fmt_stack = []
        self.ignore_stack = []
        self.buf = []
        super().__init__()

    def handle_starttag(self, tag, attrs):
        if tag in self.tags:
            start, end = self.tags[tag]
            self.buf.append(start)
            self.fmt_stack.append((tag, end))
        if tag in self.ignore:
            self.ignore_stack.append(tag)

    def handle_endtag(self, tag):
        if self.fmt_stack and tag == self.fmt_stack[-1][0]:
            self.buf.append(self.fmt_stack.pop()[1])
        elif self.ignore_stack and tag == self.ignore_stack[-1]:
            self.ignore_stack.pop()

    def handle_data(self, data):
        if not self.ignore_stack:
            self.buf.append(data.replace('\n', ' '))

    def pager(self):
        width, height = shutil.get_terminal_size()
        data = []
        buf = ''.join(self.buf)
        del self.buf[:]
        for line in buf.splitlines():
            data.extend(textwrap.wrap(line, width-4))
        i = 0
        for x in data:
            i += 1
            if i == height - 1:
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

    def setup(self, username, password):
        self.login = None
        try:
            self.username = username or input('Username: ')
        except RuntimeError:  # Readline (input) is not reentrant.
            raise Unauthorized('Unable to login in this context')
        self.req_kwargs = dict(data=self.serializer({
            "username": self.username,
            "password": password or getpass.getpass()
        }))

    def check_login_response(self):
        super().check_login_response()
        resp = self.login.json()['data']
        if resp.get('success') is False:
            raise Unauthorized(resp['error_code'])

    def __call__(self, request):
        try:
            del request.headers['Cookie']
        except KeyError:
            pass
        return super().__call__(request)

    @property
    def signature(self):
        return self.gen_signature(self.username)

    @staticmethod
    def gen_signature(key):
        return key and hashlib.sha256(key.encode()).hexdigest()


class Eventer(object):
    """ Very simple event framework. """

    def __init__(self, *args, **kwargs):
        self.events = {}
        super().__init__(*args, **kwargs)

    def add_events(self, events):
        """ Setup events for this instance.  Just a list of strings. """
        for x in events:
            self.events.setdefault(x, [])

    def add_listener(self, event, callback, single=False, priority=None):
        event_stack = self.events[event]
        if priority is None:
            try:
                priority = event_stack[-1]['priority'] + 1
            except IndexError:
                priority = 1
        event_stack.append({
            "callback": callback,
            "single": single,
            "priority": priority
        })
        event_stack.sort(key=lambda x: x['priority'])

    def remove_listener(self, event, callback, single=None, priority=None):
        """ Remove the event listener matching the signature used for adding
        it.  This will remove at most one entry meeting the signature
        requirements. """
        event_stack = self.events[event]
        for x in event_stack:
            if x['callback'] is callback and \
               (single is not None and x['single'] == single) and \
               (priority is not None and x['priority'] == priority):
                event_stack.remove(x)
                break
        else:
            raise KeyError('Listener not found for "%s": %s'  % (event,
                           callback))

    def fire_event(self, event, *args, **kwargs):
        """ Execute the listeners for this event passing any arguments
        along. """
        remove = []
        event_stack = self.events[event]
        for x in event_stack:
            x['callback'](*args, **kwargs)
            if x['single']:
                remove.append(x)
        for x in remove:
            event_stack.remove(x)


class ECMService(Eventer, syndicate.Service):

    site = 'https://cradlepointecm.com'
    api_prefix = '/api/v1'
    session_file = os.path.expanduser('~/.ecmcli_session')

    def __init__(self):
        super().__init__(uri='nope', urn=self.api_prefix,
                         serializer='htmljson')
        self.add_events([
            'start_request',
            'finish_request',
            'reset_auth'
        ])

    def connect(self, site=None, username=None, password=None):
        if site:
            self.site = site
        self.account = None
        self.hard_username = username
        self.hard_password = password
        self.uri = self.site
        self.load_session(ECMLogin.gen_signature(username))
        if not self.session_id:
            self.reset_auth()
        else:
            self.ident = self.get('login')

    def reset_auth(self):
        self.fire_event('reset_auth')
        self.reset_session()
        auth = ECMLogin(url='%s%s/login/' % (self.site, self.api_prefix))
        auth.setup(self.hard_username, self.hard_password)
        self.auth_sig = auth.signature
        self.adapter.auth = auth
        self.ident = self.get('login')

    def load_session(self, signature_lock):
        session_id = auth_sig = None
        try:
            with open(self.session_file) as f:
                d = json.load(f)
                try:
                    session_id, auth_sig = d
                except ValueError:  # old style session
                    pass
                else:
                    if signature_lock and auth_sig != signature_lock:
                        session_id = auth_sig = None
        except FileNotFoundError:
            pass
        self.session_id = session_id
        self.auth_sig = auth_sig
        if self.session_id:
            self.adapter.session.cookies['sessionid'] = self.session_id

    def reset_session(self):
        """ Delete the session state file and return True if an action
        happened. """
        self.session_id = None
        self.auth_sig = None
        try:
            os.remove(self.session_file)
        except FileNotFoundError:
            pass

    def check_session(self):
        """ ECM sometimes updates the session token. We make sure we are in
        sync. """
        session_id = self.adapter.session.cookies.get_dict()['sessionid']
        if session_id != self.session_id:
            with open(self.session_file, 'w') as f:
                os.chmod(self.session_file, 0o600)
                json.dump([session_id, self.auth_sig], f)
            self.session_id = session_id

    def do(self, *args, **kwargs):
        """ Wrap some session and error handling around all API actions. """
        self.fire_event('start_request', args=args, kwargs=kwargs)
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
        self.fire_event('finish_request', result=result)
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
        if resp['message']:
            err += '\n%s' % resp['message'].strip()
        raise SystemExit("Error: %s" % err)

    def accept_tos(self):
        tos_parser = TOSParser()
        for tos in self.get_pager('system_message', type='tos'):
            tos_parser.feed(tos['message'])
            input("You must read and accept the terms of service to "
                  "continue: <press enter>")
            tos_parser.pager()
            print()
            accept = input('Type "accept" to comply with the TOS: ')
            if accept != 'accept':
                return False
            self.post('system_message_confirm', {
                "message": tos['resource_uri']
            })
            return True

    def get_by(self, selectors, resource, criteria, required=True, **options):
        for field in selectors:
            filters = options.copy()
            filters[field] = criteria
            try:
                return self.get(resource, **filters)[0]
            except IndexError:
                pass
        if required:
            raise SystemExit("%s not found: %s" % (resource[:-1].capitalize(),
                             criteria))

    def get_by_id_or_name(self, resource, id_or_name, **kwargs):
        selectors = ['name']
        if id_or_name.isnumeric():
            selectors.insert(0, 'id')
        return self.get_by(selectors, resource, id_or_name, **kwargs)
