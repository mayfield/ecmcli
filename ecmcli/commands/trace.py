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
        if p.enabled:
            raise SystemExit("Tracer already enabled")
        else:
            p.enabled = True
        self.api.add_listener('start_request', p.on_request_start)
        self.api.add_listener('finish_request', p.on_request_finish)


class Disable(base.ECMCommand):
    """ Disable API Tracing. """

    name = 'disable'

    def run(self, *args):
        p = self.parent
        if not p.enabled:
            raise SystemExit("No tracer to disable")
        else:
            p.enabled = False
        self.api.remove_listener('finish_request', p.on_request_finish)
        self.api.remove_listener('start_request', p.on_request_start)


class Trace(base.ECMCommand):
    """ Trace API calls. """

    name = 'trace'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enabled = False
        self.tracking = {}
        self.add_subcommand(Enable, default=True)
        self.add_subcommand(Disable)

    def on_request_start(self, callid, args=None, kwargs=None):
        t = time.perf_counter()
        method, path = args
        query = kwargs.copy()
        urn = query.pop('urn', self.api.urn)
        filters = ["%s=%s" % x for x in query.items()]
        sig = '<b>%s</b> /%s/%s?<dim>%s</dim>' % (
              method.upper(), urn.strip('/'), '/'.join(path).strip('/'),
              '&'.join(filters))
        self.tracking[callid] = t, sig
        shellish.vtmlprint('<cyan>%.3f</cyan> - API TRACE: <blue>%s</blue>' %
                           (t, sig))

    def on_request_finish(self, callid, error=None, result=None):
        t = time.perf_counter()
        start, sig = self.tracking.pop(callid)
        ms = (t - start) * 1000
        if self.tracking:
            addendum = ' [<magenta>%d call(s) outstanding</magenta>]' % \
                       len(self.tracking)
        else:
            addendum = ''
        if error is not None:
            shellish.vtmlprint('<cyan>%.3f</cyan> - API TRACE (%dms): <red>%s '
                               '<b>ERROR (%s)</b></red>%s' % (t, ms, sig,
                               error, addendum))
        else:
            shellish.vtmlprint('<cyan>%.3f</cyan> - API TRACE (%dms): <green>'
                               '%s <b>OK</b> (len: %s)</green>%s' % (t, ms, sig,
                               len(result) if result is not None else 'empty',
                               addendum))

command_classes = [Trace]
