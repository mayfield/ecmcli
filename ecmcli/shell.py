"""
Interactive shell for ECM.
"""

import code
import shellish
import time
from . import api


class ECMShell(shellish.Shell):

    default_prompt_format = r': \033[7m{user}\033[0m@{site} /{cwd} ; \n:;'
    intro = '\n'.join([
        'Welcome to the ECM shell.',
        'Type "help" or "?" to list commands and "exit" to quit.'
    ])

    def prompt_info(self):
        info = super().prompt_info()
        info.update({
            "user": self.api.ident['user']['username'],
            "site": self.api.site.split('//', 1)[1],
            "cwd": '/'.join(x['name'] for x in self.cwd)
        })
        return info

    def __init__(self, root_command):
        super().__init__(root_command)
        self.api = root_command.api
        self.cwd = [self.api.ident['account']]

    def do_ls(self, arg):
        if arg:
            parent = self.api.get_by_id_or_name('accounts', arg)
        else:
            parent = self.cwd[-1]
        items = []
        for x in self.api.get_pager('accounts', account=parent['id']):
            items.append('%s/' % x['name'])
        for x in self.api.get_pager('routers', account=parent['id']):
            items.append('r:%s' % x['name'])
        account_filter = {"profile.account": parent['id']}
        for x in self.api.get_pager('users', **account_filter):
            items.append('u:%s' % x['username'])
        self.columnize(items)

    def do_login(self, arg):
        try:
            self.api.reset_auth()
        except api.AuthFailure as e:
            print('Auth Error:', e)

    def do_debug(self, arg):
        """ Run an interactive python interpretor. """
        code.interact(None, None, self.__dict__)

    def do_debug_api(self, arg):
        """ Start logging api activity to the screen. """
        self.api.add_listener('start_request', self.on_request_start)
        self.api.add_listener('finish_request', self.on_request_finish)

    def on_request_start(self, args=None, kwargs=None):
        self.last_request_start = time.perf_counter()
        print('START REQUEST', args, kwargs)

    def on_request_finish(self, result=None):
        time_taken = time.perf_counter() - self.last_request_start
        print('FINISHED REQUEST (%g seconds):' % time_taken, result)

    def do_cd(self, arg):
        cwd = self.cwd[:]
        if arg.startswith('/'):
            del cwd[1:]
        for x in arg.split('/'):
            if not x or x == '.':
                continue
            if x == '..':
                cwd.pop()
            else:
                newdir = self.get_account(x, parent=cwd[-1])
                if not newdir:
                    print("Account not found:", x)
                    return
                cwd.append(newdir)
        self.cwd = cwd

    def get_account(self, id_or_name, parent=None):
        options = {}
        if parent is not None:
            options['account'] = parent['id']
        newdir = self.api.get_by_id_or_name('accounts', id_or_name,
                                            required=False, **options)
        return newdir
