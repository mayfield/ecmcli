"""
Some API handling code.  Predominantly this is to centralize common
alterations we make to API calls, such as filtering by router ids.
"""

import getpass
import hashlib
import html
import json
import os
import syndicate
import syndicate.client
import syndicate.data
import sys
from syndicate.adapters.sync import LoginAuth

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


class ECMService(syndicate.Service):

    site = 'https://cradlepointecm.com'
    api_prefix = '/api/v1'
    session_file = os.path.expanduser('~/.ecmcli_session')

    def __init__(self, username=None, password=None):
        self.account = None
        self.load_session()
        # Eventually auth sig could be based on an api token too.
        auth_sig = username and hashlib.sha1(username.encode()).hexdigest()
        if not self.session_id or (auth_sig and self.auth_sig != auth_sig):
            self.reset_session(auth_sig)
            creds = {
                "username": username or input('ECM Username: '),
                "password": password or getpass.getpass()
            }
            auth = LoginAuth(url='%s%s/login/' % (self.site, self.api_prefix),
                             data=creds)
        else:
            auth = None
        super().__init__(uri=self.site, urn=self.api_prefix, auth=auth,
                         serializer='htmljson')

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
        self.check_session()
        return result

    def handle_error(self, error):
        """ Pretty print error messages and exit. """
        print('Response ERROR: ', file=sys.stderr)
        for key, val in sorted(error.response.items()):
            print("  %-20s: %s" % (key.capitalize(),
                  html.unescape(str(val))), file=sys.stderr)
        if error.response['exception'] == 'unauthorized':
            if self.reset_session():
                print('WARNING: Flushed session state', file=sys.stderr)
        exit(1)
