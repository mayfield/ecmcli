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
import syndicate
import syndicate.client
import syndicate.data
import sys
import tempfile
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
        with tempfile.NamedTemporaryFile() as f:
            for x in self.buf:
                f.write(x.encode())
            os.system('less -r %s' % f.name)
        del self.buf[:]


syndicate.data.serializers['htmljson'] = syndicate.data.Serializer(
    'application/json',
    syndicate.data.serializers['json'].encode,
    HTMLJSONDecoder().decode
)


class ECMService(syndicate.Service):

    site = 'https://cradlepointecm.com'
    api_prefix = '/api/v1'
    session_file = os.path.expanduser('~/.ecmcli_session')

    def __init__(self, site, username=None, password=None):
        if site:
            self.site = site
        self.account = None
        self.load_session()
        # Eventually auth sig could be based on an api token too.
        auth_sig = username and hashlib.sha256(username.encode()).hexdigest()
        if not self.session_id or (auth_sig and self.auth_sig != auth_sig):
            self.reset_session(auth_sig)
            creds = {
                "username": username or input('Username: '),
                "password": password or getpass.getpass()
            }
            auth = LoginAuth(url='%s%s/login/' % (self.site, self.api_prefix),
                             data=creds)
        else:
            auth = None
        super().__init__(uri=self.site, urn=self.api_prefix, auth=auth,
                         serializer='htmljson')
        self.ident = self.get('login')

    def bind_adapter(self, adapter):
        super().bind_adapter(adapter)
        if self.session_id:
            self.adapter.session.cookies['sessionid'] = self.session_id

    def load_session(self):
        self.auth_sig = None
        try:
            with open(self.session_file) as f:
                d = json.load(f)
                try:
                    self.session_id, self.auth_sig = d
                except ValueError:
                    self.session_id = d
        except FileNotFoundError:
            self.session_id = None

    def reset_session(self, auth_sig=None):
        """ Delete the session state file and return True if an action
        happened. """
        self.session_id = None
        self.auth_sig = auth_sig
        try:
            os.remove(self.session_file)
        except FileNotFoundError:
            return False
        else:
            return True

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
        if self.account is not None:
            kwargs['account'] = self.account
        try:
            result = super().do(*args, **kwargs)
        except syndicate.client.ResponseError as e:
            self.handle_error(e)
            # Retry if handle_error did not exit.
            result = super().do(*args, **kwargs)
        self.check_session()
        return result

    def handle_error(self, error):
        """ Pretty print error messages and exit. """
        if error.response['exception'] == 'precondition_failed' and \
           error.response['message'] == 'must_accept_tos':
            if self.accept_tos():
                return
            print("\nWARNING: User did not accept terms.")
            exit(1)
        print('Response ERROR: ', file=sys.stderr)
        for key, val in sorted(error.response.items()):
            print("  %-20s: %s" % (key.capitalize(),
                  html.unescape(str(val))), file=sys.stderr)
        if error.response['exception'] == 'unauthorized':
            if self.reset_session():
                print('WARNING: Flushed session state', file=sys.stderr)
        exit(1)

    def accept_tos(self):
        tos_parser = TOSParser()
        for tos in self.get_pager('system_message', type='tos'):
            tos_parser.feed(tos['message'])
            input("You must read and accept the terms of service to " \
                  "continue: <press enter>")
            tos_parser.pager()
            print()
            accept = input('Type "accept" to comply with this TOS: ')
            if accept != 'accept':
                return False
            self.post('system_message_confirm', {
                "message": tos['resource_uri']
            })
            return True

    def search(self, resource, field_desc, criteria, match='icontains',
               **options):
        or_terms = []
        fields = {}
        for x in field_desc:
            if isinstance(x, tuple):
                fields[x[0]] = x[1]
            else:
                fields[x] = x
        for term in criteria:
            if ':' in term:
                field, value = term.split(':', 1)
                if field not in fields:
                    print("Invalid Search Field:", field)
                    print("Valid Specifiers:", ', '.join(fields))
                    exit(1)
                options['%s__%s' % (fields[field], match)] = value
                fields.pop(field)
            else:
                query = [('%s__%s' % (x, match), term)
                         for x in fields.values()]
                or_terms.extend('='.join(x) for x in query)
        if or_terms:
            options['_or'] = '|'.join(or_terms)
        return self.get_pager(resource, **options)

    def get_by(self, selectors, resource, criteria, required=True, **options):
        for field in selectors:
            filters = options.copy()
            filters[field] = criteria
            try:
                return self.get(resource, **filters)[0]
            except IndexError:
                pass
        if required:
            print("%s Not Found:" % resource[:-1].capitalize(), criteria)
            exit(1)

    def get_by_id_or_name(self, resource, id_or_name, **kwargs):
        selectors = ['name']
        if id_or_name.isnumeric():
            selectors.insert(0, 'id')
        return self.get_by(selectors, resource, id_or_name, **kwargs)
