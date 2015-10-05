"""
Set and get GPIO pins.
"""

from . import base


class GPIOResponse(object):
    """ Wrap the various types of responses the GPIO remote API might
        provide. """

    def __init__(self, api_response):
        self.success = False
        self.status = None

        if not api_response:
            self.message = "Empty API response"
        elif not isinstance(api_response, list) or len(api_response) != 1 or \
                'success' not in api_response[0]:
            self.message = "Unexpected API response: %s" % api_response
        elif not api_response[0]['success']:
            self.message = "API call failed: %s" % api_response
        else:
            self.success = True
            self.status = api_response[0]['data']
            self.message = "success"


class GPIO(base.ECMCommand):
    """ Set or get the output GPIO. """

    name = 'gpio'

    def setup_args(self, parser):
        self.add_argument('ident', metavar='ROUTER_ID_OR_NAME',
                          complete=self.make_completer('routers', 'name'))
        self.add_argument('-v', '--value', type=int, metavar="GPIO_VALUE",
                          default=None)

    def human_status(self, status):
        return 'OFF (0)' if status == 0 else 'ON (1)'

    def run(self, args):
        gpio_path = 'config/system/connector_gpio/output'
        r = self.api.get_by_id_or_name('routers', args.ident)

        if args.value:
            val = args.value
            print('Setting GPIO on %s (%s) to: %s' % (r['name'], r['id'],
                  self.human_status(val)))
            g = GPIOResponse(self.api.put('remote', gpio_path, val,
                             id=r['id']))

            if not g.success:
                print(g.message)
                return

        g = GPIOResponse(self.api.get('remote', gpio_path, id=r['id']))
        if g.success:
            print('GPIO on %s (%s) now has value: %s' % (r['name'], r['id'],
                  self.human_status(g.status)))
        else:
            print(g.message)

command_classes = [GPIO]
