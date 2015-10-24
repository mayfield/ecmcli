"""
Interactive shell for ECM.
"""

import shellish


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
        self.reset_cwd()

    def reset_cwd(self):
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
        shellish.columnize(items)

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
