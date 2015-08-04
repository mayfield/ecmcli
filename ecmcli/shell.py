"""
Interactive shell for ECM.
"""

import cmd
import code
import os.path
import readline
import shlex
import shutil
import sys
from . import api


class ShellQuit(Exception):
    pass


class ECMShell(cmd.Cmd):

    history_file = os.path.expanduser('~/.ecmcli_history')
    intro = '\n'.join([
        'Welcome to the ECM shell.',
        'Type "help" or "?" to list commands and "exit" to quit.'
    ])

    @property
    def prompt(self):
        info = {
            "user": self.api.ident['user']['username'],
            "site": self.api.site.split('//', 1)[1],
            "cwd": '/'.join(x['name'] for x in self.cwd)
        }
        return ': \033[7m%(user)s\033[0m@%(site)s /%(cwd)s ; \n:; ' % (info)

    def __init__(self, root_command):
        self.api = root_command.api
        self.root_command = root_command
        self.cwd = [self.api.ident['account']]
        self.command_methods = ['do_%s' % x.name
                                for x in root_command.subcommands]
        try:
            readline.read_history_file(self.history_file)
        except FileNotFoundError:
            pass
        for x in root_command.subcommands:
            x.api = self.api
            setattr(self, 'do_%s' % x.name, self.wrap_command_invoke(x))
            setattr(self, 'help_%s' % x.name, x.argparser.print_help)
            setattr(self, 'complete_%s' % x.name, x.complete_wrap)
        super().__init__()

    def wrap_command_invoke(self, cmd):
        def wrap(arg):
            args = cmd.argparser.parse_args(shlex.split(arg))
            cmd.invoke(args)
        wrap.__doc__ = cmd.__doc__
        wrap.__name__ = 'do_%s' % cmd.name
        return wrap

    def get_names(self):
        return super().get_names() + self.command_methods

    def emptyline(self):
        """ Do not re-run the last command. """
        pass

    def columnize(self, items, displaywidth=None):
        if displaywidth is None:
            displaywidth, h = shutil.get_terminal_size()
        return super().columnize(items, displaywidth=displaywidth)

    def cmdloop(self):
        intro = ()
        while True:
            try:
                super().cmdloop(*intro)
            except ShellQuit:
                return
            except KeyboardInterrupt:
                print()
            except api.AuthFailure as e:
                raise e
            except SystemExit as e:
                if not str(e).isnumeric():
                    print(e, file=sys.stderr)
            finally:
                readline.write_history_file(self.history_file)
            if not intro:
                intro = ('',)

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

    def do_exit(self, arg):
        raise ShellQuit()

    def default(self, line):
        if line == 'EOF':
            print('^D')
            raise ShellQuit()
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
