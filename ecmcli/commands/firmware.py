"""
Commands for managing firmware versions of routers.
"""

from . import base


class Active(base.ECMCommand):
    """ Show the firmware versions being actively used. """

    name = 'active'

    def setup_args(self, parser):
        self.add_argument('--verbose', action="store_true")

    def run(self, args):
        self.tabulate(self.api.get_pager('firmwares'))


class Firmware(base.ECMCommand):
    """ Manage ECM Routers. """

    name = 'firmware'
    aliases = {
        'fw': 'firmware active'
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(Active, default=True)

command_classes = [Firmware]
