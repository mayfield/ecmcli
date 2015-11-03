"""
Terms of service viewing and acceptance.
"""

import shellish
import shutil
import textwrap
from . import base


class Review(base.ECMCommand):
    """ Review the ECM Terms of Service (TOS). """

    name = 'review'

    def setup_args(self, parser):
        self.add_file_argument('--download', mode='w')

    def print_tos(self, tos):
        """ Groom the TOS to fit the screen. """
        width = shutil.get_terminal_size()[0]
        data = str(shellish.htmlrender(tos['message'])).splitlines()
        for section in data:
            lines = textwrap.wrap(section, width-4)
            if not lines:
                print()
            for x in lines:
                print(x)

    def get_tos(self):
        tos = self.api.get('system_message', type='tos')
        assert tos.meta['total_count'] == 1
        return tos[0]

    def run(self, args):
        tos = self.get_tos()
        if args.download:
            with args.download as f:
                f.write(tos['message'])
        else:
            self.print_tos(tos)


class Accept(Review):
    """ Confirm acceptance of ECM Terms of Service (TOS).
    After reviewing the terms you will be asked to confirm your acceptance
    thereby giving you an opportunity to accept or reject the legal
    requirements for ECM usage. """

    name = 'accept'
    use_pager = False

    def setup_args(self, parser):
        self.add_argument('--i-accept-the-ecm-terms-of-service',
                          action='store_true')

    def run(self, args):
        tos = self.get_tos()
        if args.i_accept_the_ecm_terms_of_service:
            self.print_tos(tos)
            print()
            shellish.vtmlprint('I, %s %s (%s), do hereby accept the ECM '
                               'terms of service: <u><b>   X   </b></u>' % (
                               self.api.ident['user']['first_name'],
                               self.api.ident['user']['last_name'],
                               self.api.ident['user']['username']))
        else:
            with shellish.pager_redirect(self.get_config('core')['pager']):
                self.print_tos(tos)
            print()
            accept = input('Type "accept" to comply with the TOS: ')
            if accept != 'accept':
                raise SystemExit("Aborted")
        self.api.post('system_message_confirm', {"message": tos['resource_uri']})


class TOS(base.ECMCommand):
    """ Review and accept ECM Terms of Service (TOS). """

    name = 'tos'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(Review, default=True)
        self.add_subcommand(Accept)

command_classes = [TOS]
