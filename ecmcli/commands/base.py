"""
Foundation components for commands.
"""

import argparse
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
        if not hasattr(args, 'api'):
            args.api = self.api

    def run(self, args):
        """ Primary entrypoint for command exec. """
        pass

    def __init__(self):
        self.api = None
        self.subcommands = []
        self.subparsers = None
        self.default_subcommand = None
        self.argparser = self.create_argparser()
        self.setup_args(self.argparser)

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
        self.argparser.error = lambda x: print(x)
        try:
            parsed = self.argparser.parse_known_args(args)
        finally:
            self.argparser.error = save
        print("TEXT:", text)
        print("LINE:", line)
        print("PARSED:", parsed)
        if not parsed and self.argparser:
            print
            return [x for x in self.subparsers.choices if x.startswith(text)]
        return self.complete(text, args, begin, end)

    def invoke(self, args):
        """ If a subparser is present and configured  we forward invocation to
        the correct subcommand method. If all else fails we call run(). """
        if self.subparsers:
            if not args.subcommand and self.default_subcommand:
                args.subcommand = self.default_subcommand.name
                defaults = self.default_subcommand.argparser.parse_args([])
                args.__dict__.update(defaults.__dict__)
            if args.subcommand:
                self.prerun(args)
                args.command.invoke(args)
                return
        self.prerun(args)
        self.run(args)

    def add_subcommand(self, command, default=False):
        if command.name is None:
            raise TypeError('Cannot add unnamed command: %s' % command)
        if not self.subparsers:
            desc = 'Provide a subcommand argument to perform an operation.'
            addsub = self.argparser.add_subparsers
            self.subparsers = addsub(title='subcommands', description=desc,
                                     dest='subcommand', metavar='COMMAND')
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
        command.argparser.set_defaults(command=command)
        self.subcommands.append(command)


class ArgParser(argparse.ArgumentParser):
    """ Add some standardized notions of subcommands to the argument parser.
    Using this class simply helps consistency for the bulk of commands that
    make use of subcommands. """

    def __init__(self, *args, **kwargs):
        Formatter = argparse.RawDescriptionHelpFormatter
        self.subcmd_parser = None
        super().__init__(*args, formatter_class=Formatter, **kwargs)

    def complete(self, last, fullline, begidx, endidx):
        """ Attempt to autocomplete the current input buffer based on our
        arugment parsing configuration.  Any arguments that represent an
        incomplete key/value combo where the key is complete will defer to
        a completer function on the argument itself.  This allows type
        specific completion when the user wants to see the available options
        for a given argument. """
        args = shlex.split(fullline)[1:]
        save = self.argparser.error
        self.argparser.error = lambda x: print(x)
        try:
            parsed = self.argparser.parse_known_args(args)
        finally:
            self.argparser.error = save
        print("LAST:", last)
        print("FULLLINE:", fullline)
        print("PARSED:", parsed)
        if not parsed and self.subcmd_parser:
            return [x for x in self.subcmd_parser.choices if x.startswith(last)]
