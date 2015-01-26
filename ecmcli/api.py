"""
Some API handling code.  Predominantly this is to centralize common
alterations we make to API calls, such as filtering by router ids.
"""

import getpass
import html
import json
import os
import syndicate
import syndicate.client
import sys
from syndicate.adapters.sync import LoginAuth


class ECMService(syndicate.Service):

    site = 'https://cradlepointecm.com'
    api_prefix = '/api/v1'
    session_file = os.path.expanduser('~/.ecmcli_session')

    def __init__(self, username=None, password=None):
        self.load_session()
        if not self.sessionid:
            creds = {
                "username": username or input('ECM Username: '),
                "password": password or getpass.getpass()
            }
            auth = LoginAuth(url='%s%s/login/' % (self.site, self.api_prefix),
                             data=creds)
        else:
            auth = None
        super().__init__(uri=self.site, urn=self.api_prefix, auth=auth)

    def bind_adapter(self, adapter):
        super().bind_adapter(adapter)
        if self.sessionid:
            self.adapter.session.cookies['sessionid'] = self.sessionid

    def load_session(self):
        try:
            with open(self.session_file) as f:
                self.sessionid = json.load(f)
        except FileNotFoundError:
            self.sessionid = None

    def clear_session(self):
        """ Delete the session state file and return True if an action
        happened. """
        self.sessionid = None
        try:
            os.remove(self.session_file)
        except FileNotFoundError:
            return False
        else:
            return True

    def check_session(self):
        """ ECM sometimes updates the session token. We make sure we are in
        sync. """
        sessionid = self.adapter.session.cookies.get_dict()['sessionid']
        if sessionid != self.sessionid:
            with open(self.session_file, 'w') as f:
                os.chmod(self.session_file, 0o600)
                json.dump(sessionid, f)
            self.sessionid = sessionid

    def do(self, *args, **kwargs):
        """ Wrap some session and error handling around all API actions. """
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
            if self.clear_session():
                print('WARNING: Flushed session state', file=sys.stderr)
        exit(1)
