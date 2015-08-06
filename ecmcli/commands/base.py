"""
Foundation components for commands.
"""

import argparse
import itertools
import shlex


def confirm(msg, exit=True):
    if input('%s (type "yes" to confirm)? ' % msg) != 'yes':
        if not exit:
            return False
        raise SystemExit('Aborted')
    return True


class Command(object):

    name = None

    def setup_args(self, parser):
        """ Subclasses should provide any setup for their parsers here. """
        pass

    def complete(self, text, state, begin, end):
        """ Tab completion function. """
        pass

    def prerun(self, args):
        """ Hook to do thing prior to any invocation. """
        pass

    def run(self, args):
        """ Primary entrypoint for command exec. """
        self.argparser.print_usage()
        raise SystemExit(1)

    def __init__(self, parent=None, **context):
        self.inject_context(parent, context)
        self.parent = parent
        self.depth = (parent.depth + 1) if parent else 0
        self.subcommands = []
        self.subparsers = None
        self.default_subcommand = None
        self.argparser = self.create_argparser()
        self.setup_args(self.argparser)

    def inject_context(self, parent, context):
        """ Map context attributes from the parent and from the context
        argument into this instance (as attributes). """
        self.context_keys = set(context.keys())
        for key, value in context.items():
            setattr(self, key, value)
        if parent:
            for key in parent.context_keys:
                setattr(self, key, getattr(parent, key))
            self.context_keys |= parent.context_keys

    def create_argparser(self):
        """ Factory for arg parser, can be replaced with any ArgParser compat
        instance. """
        Formatter = argparse.RawDescriptionHelpFormatter
        desc = self.clean_docstring()[1]
        parser = argparse.ArgumentParser(self.name, description=desc,
                                         formatter_class=Formatter)
        return parser

    def clean_docstring(self):
        """ Return sanitized docstring from this class.
        The first line of the docstring is the title, and remaining lines are
        the details, aka git style. """
        try:
            doc = [x.strip() for x in self.__doc__.splitlines()]
        except AttributeError:
            raise SyntaxError('Docstring missing for: %s' % self)
        if not doc[0]:
            doc.pop(0)  # Some people leave the first line blank.
        title = doc.pop(0)
        if doc:
            desc = '%s\n\n%s' % (title, '\n'.join(doc))
        else:
            desc = title
        return title, desc

    def complete_wrap(self, text, line, begin, end):
        """ Do naive argument parsing so the completer has better ability to
        understand expansion rules. """
        args = shlex.split(line)[1:]
        save = self.argparser.error
        self.argparser.error = lambda x: print('ERROR', x)
        try:
            parsed = self.argparser.parse_known_args(args)
        finally:
            self.argparser.error = save
        #print("TEXT:", text)
        #print("LINE:", line)
        #print("PARSED:", parsed)
        if not parsed and self.argparser:
            return [x for x in self.subparsers.choices if x.startswith(text)]
        return self.complete(text, args, begin, end)

    def invoke(self, args):
        """ If a subparser is present and configured  we forward invocation to
        the correct subcommand method. If all else fails we call run(). """
        commands = self.get_commands_from(args)
        if self.subparsers:
            try:
                command = commands[self.depth]
            except IndexError:
                if self.default_subcommand:
                    self.default_subcommand.argparser.parse_args([], namespace=args)
                    self.invoke(args)  # retry
                    return
            else:
                self.prerun(args)
                command.invoke(args)
                return
        self.prerun(args)
        self.run(args)

    def get_commands_from(self, args):
        """ We have to code the key names for each depth.  This method scans
        for each level and returns a list of the command arguments. """
        commands = []
        for i in itertools.count(0):
            try:
                commands.append(getattr(args, 'command%d' % i))
            except AttributeError:
                break
        return commands

    def add_subcommand(self, command_class, default=False):
        command = command_class(parent=self)
        if command.name is None:
            raise TypeError('Cannot add unnamed command: %s' % command)
        if not self.subparsers:
            desc = 'Provide a subcommand argument to perform an operation.'
            addsub = self.argparser.add_subparsers
            self.subparsers = addsub(title='subcommands', description=desc,
                                     metavar='COMMAND')
        if default:
            if self.default_subcommand:
                raise ValueError("Default subcommand already exists.")
            self.default_subcommand = command
        title, desc = command.clean_docstring()
        help_fmt = '%s (default)' if default else '%s'
        help = help_fmt % title
        prog = '%s %s' % (self.subparsers._prog_prefix, command.name)
        if command.subparsers:
            for x in command.subparsers.choices.values():
                x.prog = '%s %s' % (prog, x.prog.rsplit(' ', 1)[1])
        command.argparser.prog = prog
        action = self.subparsers._ChoicesPseudoAction(command.name, (), help)
        self.subparsers._choices_actions.append(action)
        self.subparsers._name_parser_map[command.name] = command.argparser
        command.argparser.set_defaults(**{'command%d' % self.depth: command})
        self.subcommands.append(command)
