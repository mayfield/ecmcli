"""
Trace API activity.
"""

import shellish
import time
from . import base


class Enable(base.ECMCommand):
    """ Enable API Tracing. """

    name = 'enable'

    def run(self, *args):
        p = self.parent
        self.api.add_listener('start_request', p.on_request_start)
        self.api.add_listener('finish_request', p.on_request_finish)


class Disable(base.ECMCommand):
    """ Disable API Tracing. """

    name = 'disable'

    def run(self, *args):
        p = self.parent
        self.api.remove_listener('finish_request', p.on_request_finish)
        self.api.remove_listener('start_request', p.on_request_start)


class Trace(base.ECMCommand):
    """ Trace API calls. """

    name = 'trace'

    def on_request_start(self, args=None, kwargs=None):
        t = self.last_request_start = time.perf_counter()
        method, path = args
        query = kwargs.copy()
        urn = query.pop('urn', self.api.urn)
        filters = ["%s=%s" % x for x in query.items()]
        shellish.vtmlprint('<cyan>%.3f</cyan> - <blue>API DEBUG: %s /%s/%s?%s'
                           % (t, method.upper(), urn.strip('/'),
                           '/'.join(path).strip('/'), '&'.join(filters)))

    def on_request_finish(self, error=None, result=None):
        t = time.perf_counter()
        ms = (t - self.last_request_start) * 1000
        if error is not None:
            shellish.vtmlprint('<cyan>%.3f</cyan> - <red>API DEBUG (%dms): <b>'
                               'ERROR (%s)</b></red>' % (t, ms, error))
        else:
            shellish.vtmlprint('<cyan>%.3f</cyan> - <green>API DEBUG (%dms): '
                               '<b>OK (len: %d)</b></green>' % (t, ms,
                               len(result)))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(Enable, default=True)
        self.add_subcommand(Disable)

command_classes = [Trace]
