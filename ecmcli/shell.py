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

    def __init__(self, commands, api):
        self.api = api
        self.cwd = [api.ident['account']]
        self.command_methods = ['do_%s' % x for x in commands]
        for name, module in commands.items():
            setattr(self, 'do_%s' % name, self.wrap_module(name, module))
            setattr(self, 'help_%s' % name, module.parser.print_help)
            if hasattr(module, 'completer'):
                setattr(self, 'complete_%s' % name, module.completer)
        super().__init__()

    def wrap_module(self, name, module):
        def wrap(args):
            args = module.parser.parse_args(args.split())
            module.command(self.api, args)
        wrap.__doc__ = module.__doc__
        wrap.__name__ = 'do_%s' % name
        return wrap

    def get_names(self):
        return super().get_names() + self.command_methods

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
        for x in self.api.get_pager('users', **{"profile.account": parent['id']}):
            items.append('u:%s' % x['username'])
        self.columnize(items)

    def default(self, line):
        if line == 'EOF':
            print('^D')
            exit(0)
        else:
            return super().default(line)

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
