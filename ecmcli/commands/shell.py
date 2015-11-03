"""
Interact with the shell of ECM clients.
"""

import contextlib
import fcntl
import os
import select
import shutil
import sys
import termios
import time
import tty
from . import base


class Shell(base.ECMCommand):
    """ Emulate an interactive shell to a remote router. """

    name = 'shell'
    use_pager = False
    poll_max_retry = 300  # Max secs for polling when no activity is detected.
    # How long we wait for additional keystrokes after one or more keystrokes
    # have been detected.
    key_idle_timeout = 0.150
    raw_in = sys.stdin.buffer.raw
    raw_out = sys.stdout.buffer.raw

    def setup_args(self, parser):
        self.add_router_argument()
        self.add_argument('-n', '--new', action='store_true',
                          help='Start a new session')

    def run(self, args):
        router = self.api.get_by_id_or_name('routers', args.ident)
        print("Connecting to: %s (%s)" % (router['name'], router['id']))
        print("Type ~~ rapidly to close session")
        sessionid = int(time.time() * 10000) if args.new else \
                    self.api.session_id
        with self.setup_tty():
            self.rsh(router, sessionid)

    @contextlib.contextmanager
    def setup_tty(self):
        stdin = sys.stdin.fileno()
        ttysave = termios.tcgetattr(stdin)
        tty.setraw(stdin)
        attrs = termios.tcgetattr(stdin)
        attrs[tty.IFLAG] = (attrs[tty.IFLAG] | termios.ICRNL)
        attrs[tty.OFLAG] = (attrs[tty.OFLAG] | termios.ONLCR | termios.OPOST)
        attrs[tty.LFLAG] = (attrs[tty.LFLAG] | termios.IEXTEN)
        termios.tcsetattr(stdin, termios.TCSANOW, attrs)
        fl = fcntl.fcntl(stdin, fcntl.F_GETFL)
        fcntl.fcntl(stdin, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        try:
            yield
        finally:
            termios.tcsetattr(stdin, termios.TCSADRAIN, ttysave)
            fcntl.fcntl(stdin, fcntl.F_SETFL, fl)

    def buffered_read(self, idle_timeout=key_idle_timeout, max_timeout=None):
        buf = []
        timeout = max_timeout
        while True:
            if select.select([self.raw_in.fileno()], [], [], timeout)[0]:
                buf.append(self.raw_in.read())
                timeout = self.key_idle_timeout
            else:
                break
        sbuf = b''.join(buf).decode()
        if '~~' in sbuf:
            sys.exit('Session Closed')
        return sbuf

    def full_write(self, dstfile, srcdata):
        """ Write into dstfile until it's done, accounting for short write()
        calls. """
        srcview = memoryview(srcdata)
        size = len(srcview)
        written = 0
        while written < size:
            select.select([], [dstfile.fileno()], [])  # block until writable
            written += dstfile.write(srcview[written:])

    def rsh(self, router, sessionid):
        rid = router['id']
        w_save, h_save = None, None
        res = 'remote/control/csterm/ecmcli-%s/' % sessionid
        in_data = '\n'
        poll_timeout = self.key_idle_timeout  # somewhat arbitrary
        while True:
            w, h = shutil.get_terminal_size()
            if (w, h) != (w_save, h_save):
                out = self.api.put(res, {
                    "w": w,
                    "h": h,
                    "k": in_data
                }, id=rid)[0]
                w_save, h_save = w, h
                data = out['data']['k'] if out['success'] else None
            else:
                out = self.api.put('%sk' % res, in_data, id=rid)[0]
                data = out['data'] if out['success'] else None
            if out['success']:
                if data:
                    self.full_write(self.raw_out, data.encode())
                    poll_timeout = 0  # Quickly look for more data
                else:
                    poll_timeout += 0.050
            else:
                raise Exception('%s (%s)' % (out['exception'], out['reason']))
            poll_timeout = min(self.poll_max_retry, poll_timeout)
            in_data = self.buffered_read(max_timeout=poll_timeout)

command_classes = [Shell]
