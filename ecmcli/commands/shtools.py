"""
Tools for the interactive shell.
"""

import code
from . import base


class Debug(base.ECMCommand):
    """ Run an interactive python interpretor. """

    name = 'debug'
    use_pager = False

    def run(self, args):
        code.interact(None, None, self.__dict__)

command_classes = [Debug]
