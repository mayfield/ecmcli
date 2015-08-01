"""
Foundation components for commands.
"""

import argparse


def confirm(msg, exit=True):
    if input('%s (type "yes" to confirm)? ' % msg) != 'yes':
        if not exit:
            return False
        raise SystemExit('Aborted')
    return True


class Command(object):

    name = None

    def init_argparser(self):
        """ Subclasses should provide any setup for their parsers here.
        The return value should be the argument parser instance for this
        command. """
        pass

    def run(self):
        """ Primary entrypoint for Subclasses command exec. """
        pass

    def complete(self, text, state, begin, end):
        """ Tab completion function. """
        pass

    def prerun(self, args):
        pass

    def __init__(self):
        self.api = None
        self.argparser = self.init_argparser()

    def invoke(self, api, args):
        """ If a subparser is present and configured  we forward invocation to
        the correct subcommand method. If all else fails we call run(). """
        self.api = api
        if self.argparser.subparser:
            if not args.subcommand and self.argparser.default_subparser:
                args = self.argparser.default_subparser.parse_args([])
            self.prerun(args)
            return args.subcommand_invoke(args)
        else:
            self.prerun(args)
            return self.run(args)


class ArgParser(argparse.ArgumentParser):
    """ Add some standardized notions of subcommands to the argument parser.
    Using this class simply helps consistency for the bulk of commands that
    make use of subcommands. """

    def __init__(self, *args, subcommands=False, **kwargs):
        Formatter = argparse.RawDescriptionHelpFormatter
        super().__init__(*args, formatter_class=Formatter, **kwargs)
        if subcommands:
            desc = 'Provide a subcommand argument to perform an operation.'
            self.subparser = self.add_subparsers(title='subcommands',
                                                 description=desc,
                                                 dest='subcommand')
            self.default_subparser = None
        else:
            self.subparser = None

    def add_subcommand(self, cmd, invoke_callback, default=False):
        help_fmt = '%s (default)' if default else '%s'
        try:
            doc = [x.strip() for x in invoke_callback.__doc__.splitlines()]
        except AttributeError:
            raise SyntaxError('Docstring required for subcommand method')
        if not doc[0]:
            doc.pop(0)  # Some people leave the first line blank.
        short_help = doc.pop(0)
        if doc:
            desc = '%s:\n\n  %s' % (short_help, '\n  '.join(doc))
        else:
            desc = short_help
        p = self.subparser.add_parser(cmd, help=help_fmt % short_help,
                                      description=desc)
        p.set_defaults(subcommand_invoke=invoke_callback)
        if default:
            if self.default_subparser:
                raise ValueError("Default subcommand already exists.")
            else:
                self.default_subparser = p
        return p
