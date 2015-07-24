import cmd
import sys

class ECMShell(cmd.Cmd):

    intro = '\n'.join([
        'Welcome to the ECM shell.',
        'Type help or ? to list commands.'
    ])

    @property
    def prompt(self):
        info = {
            "user": self.api.ident['user']['username'],
            "site": self.api.site.split('//', 1)[1],
            "cwd": '/'.join(x['name'] for x in self.cwd)
        }
        return ': \033[7m%(user)s\033[0m@%(site)s /%(cwd)s ; \n:; ' % (info)

    def __init__(self, api, args, options):
        super().__init__()
        self.cwd = [api.ident['account']]
        self.api = api
        self.args = args
        self.options = options

    def do_ls(self, arg):
        if arg:
            parent = self.api.get_by_id_or_name('accounts', arg)
        else:
            parent = self.cwd[-1]
        for x in self.api.get_pager('accounts', account=parent['id']):
            print(x['name'] + '/')

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
