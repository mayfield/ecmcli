"""
Pull data or interact with the shell of ECM clients.
"""

import argparse
import fcntl
import html
import os
import select
import struct
import sys
import termios
import time
import tty

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('command', nargs="*", help='Command to execute')
parser.add_argument('--interact', '-i', metavar='ROUTER_ID',
                    help='Interact directly with a single device')

raw_in = sys.stdin.buffer.raw
raw_out = sys.stdout.buffer.raw


def command(api, args, routers=None):
    if args.interact:
        return interactive_session(api, args.interact)
    else:
        return bulk_session(api, args, routers)


def window_size():
    """ Returns width and height of window in characters. """
    winsz = fcntl.ioctl(raw_in.fileno(), termios.TIOCGWINSZ, '1234')
    return struct.unpack('hh', winsz)[::-1]


def interactive_session(api, router):
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
        _interactive_session(api, router)
    finally:
        termios.tcsetattr(stdin, termios.TCSADRAIN, ttysave)


def buffered_read(timeout=0.500):
    """ Read from stdin up to an anthropomorphic timeout. """
    buf = []
    ts = time.time()
    while True:
        to = timeout-(time.time()-ts)
        if select.select([raw_in.fileno()], [], [], to)[0]:
            buf.append(raw_in.read())
        else:
            return b''.join(buf)


def _interactive_session(api, router):
    print("Connecting to: Router %s" % router)
    print("Type ~~ rapidly to close session")
    (w_save, h_save) = (w, h) = window_size()
    api.put('remote/control/csterm/ecmcli-%s' % api.sessionid, {
        "w": w,
        "h": h
    }, id=router)
    while True:
        in_data = buffered_read()
        if b'~~' in in_data:
            raise SystemExit('Session Closed')
        while True:
            w, h = window_size()
            if (w, h) != (w_save, h_save):
                api.put('remote/control/csterm/ecmcli-%s/' % api.sessionid, {
                    "w": w,
                    "h": h,
                }, id=router)
                w_save, h_save = w, h
            out = api.put('remote/control/csterm/ecmcli-%s/k' % api.sessionid,
                          in_data.decode(), id=router)[0]
            if out['success']:
                if not out['data']:
                    break
                raw_out.write(html.unescape(out['data']).encode())
            else:
                raise Exception('%s (%s)' % (out['exception'], out['reason']))
            in_data = b""


def bulk_session(api, args, routers):
    rfilter = {
        "id__in": ','.join(routers)
    }
    command = '%s\n' % ' '.join(args.command)
    data = api.put('remote/control/csterm/ecmcli-%s/k' % api.sessionid,
                   command, **rfilter)
    for x in data:
        print()
        print("%s (%s):" % (routers[str(x['id'])]['name'], x['id']))
        print("=" * 80)
        if x['success']:
            if x['data'] == command:
                print("Warning: unsupported firmware")
            else:
                print(html.unescape(x['data']))
        else:
            print("Error: %s / %s" % (x['exception'], x['reason']))
        print("-" * 80)
        print()
