"""
Trace API activity.
"""

import cellulario
import functools
import itertools
import shellish
import sys
import time
from . import base

vprint = functools.partial(shellish.vtmlprint, file=sys.stderr)


class Enable(base.ECMCommand):
    """ Enable API Tracing. """

    name = 'enable'
    use_pager = False

    def run(self, *args):
        p = self.parent
        if p.enabled:
            raise SystemExit("Tracer already enabled")
        else:
            p.enabled = True
        cellulario.iocell.DEBUG = True
        p.session_verbosity_save = self.session.command_error_verbosity
        self.session.command_error_verbosity = 'traceback'
        self.api.add_listener('start_request', p.on_request_start)
        self.api.add_listener('finish_request', p.on_request_finish)
        self.session.add_listener('precmd', p.on_command_start)
        self.session.add_listener('postcmd', p.on_command_finish)


class Disable(base.ECMCommand):
    """ Disable API Tracing. """

    name = 'disable'
    use_pager = False

    def run(self, *args):
        p = self.parent
        if not p.enabled:
            raise SystemExit("No tracer to disable")
        else:
            p.enabled = False
        self.session.remove_listener('postcmd', p.on_command_finish)
        self.session.remove_listener('precmd', p.on_command_start)
        self.api.remove_listener('finish_request', p.on_request_finish)
        self.api.remove_listener('start_request', p.on_request_start)
        self.session.command_error_verbosity = p.session_verbosity_save
        cellulario.iocell.DEBUG = True


class Trace(base.ECMCommand):
    """ Trace API calls. """

    name = 'trace'
    use_pager = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enabled = False
        self.tracking = {}
        self.add_subcommand(Enable)
        self.add_subcommand(Disable)

    def run(self, args):
        if self.enabled:
            self['disable'](argv='')
            print("Trace Disabled")
        else:
            self['enable'](argv='')
            print("Trace Enabled")

    def tprint(self, ident, category, message, code='blue'):
        t = time.perf_counter()
        vprint('<cyan>%.3f[%s]</cyan> - %s: <%s>%s</%s>' % (t, ident,
               category, code, message, code))

    def on_request_start(self, callid, args=None, kwargs=None):
        t = time.perf_counter()
        method, path = args
        query = kwargs.copy()
        urn = query.pop('urn', self.api.urn)
        filters = ["%s=%s" % x for x in query.items()]
        sig = '<b>%s</b> /%s' % (method.upper(), urn.strip('/'))
        if path:
            sig += '/%s' % '/'.join(path).strip('/')
        if filters:
            sep = '&' if '?' in sig else '?'
            sig += '%s%s' % (sep, '&'.join(filters))
        self.tracking[callid] = t, sig
        self.tprint(callid, 'API START', sig)

    def on_request_finish(self, callid, result=None, exc=None):
        t = time.perf_counter()
        start, sig = self.tracking.pop(callid)
        ms = round((t - start) * 1000)
        if self.tracking:
            addendum = ' [<magenta>%d call(s) outstanding</magenta>]' % \
                       len(self.tracking)
        else:
            addendum = ''
        if exc is not None:
            self.tprint(callid, 'API FINISH (%dms)' % ms, '%s <b>ERROR (%s)'
                        '</b>%s' % (sig, exc, addendum), code='red')
        else:
            rlen = len(result) if result is not None else 'empty'
            self.tprint(callid, 'API FINISH (%dms)' % ms, '%s <b>OK</b> '
                        '(len: %s)%s' % (sig, rlen, addendum), code='green')

    def on_command_start(self, command, args):
        command.__trace_ts = time.perf_counter()
        args = vars(args).copy()
        for i in itertools.count(0):
            if self.arg_label_fmt % i in args:
                del args[self.arg_label_fmt % i]
            else:
                break
        simple = ', '.join('%s<red>=</red><cyan>%s</cyan>' % x
                           for x in args.items())
        self.tprint(command.prog, 'COMMAND RUN', simple)

    def on_command_finish(self, command, args, result=None, exc=None):
        try:
            ms = round((time.perf_counter() - command.__trace_ts) * 1000)
        except AttributeError:
            ms = 0
        if exc:
            self.tprint(command.prog, 'COMMAND FINISH (%dms)' % ms, exc,
                        code='red')
        else:
            self.tprint(command.prog, 'COMMAND FINISH (%dms)' % ms, result,
                        code='green')

command_classes = [Trace]
