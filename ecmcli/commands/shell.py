"""
Pull data or interact with the shell of ECM clients.
"""

import argparse
import fcntl
import os
import select
import struct
import sys
import termios
import tty

poll_max_retry = 30  # Max secs for polling when no activity is detected.
key_idle_timeout = 0.200  # How long we wait for additional keystrokes after
                          # one or more keystrokes have been detected.

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


def buffered_read(idle_timeout=key_idle_timeout,
                  max_timeout=None):
    buf = []
    timeout = max_timeout
    while True:
        if select.select([raw_in.fileno()], [], [], timeout)[0]:
            buf.append(raw_in.read())
            timeout = key_idle_timeout
        else:
            break
    sbuf = b''.join(buf).decode()
    if '~~' in sbuf:
        raise SystemExit('Session Closed')
    return sbuf


def full_write(dstfile, srcdata):
    """ Write into dstfile until it's done, accounting for short write()
    calls. """
    srcview = memoryview(srcdata)
    size = len(srcview)
    written = 0
    while written < size:
        select.select([], [dstfile.fileno()], [])  # block until writable
        written += dstfile.write(srcview[written:])


def _interactive_session(api, router):
    print("Connecting to: Router %s" % router)
    print("Type ~~ rapidly to close session")
    w_save, h_save = None, None
    res = 'remote/control/csterm/ecmcli-%s/' % api.session_id
    in_data = '\n'
    poll_timeout = key_idle_timeout  # somewhat arbitrary
    while True:
        w, h = window_size()
        if (w, h) != (w_save, h_save):
            out = api.put(res, {
                "w": w,
                "h": h,
                "k": in_data
            }, id=router)[0]
            w_save, h_save = w, h
            data = out['data']['k'] if out['success'] else None
        else:
            out = api.put('%sk' % res, in_data, id=router)[0]
            data = out['data'] if out['success'] else None
        if out['success']:
            if data:
                full_write(raw_out, data.encode())
                poll_timeout = 0  # Quickly look for more data
            else:
                poll_timeout += 0.200
        else:
            raise Exception('%s (%s)' % (out['exception'], out['reason']))
        poll_timeout = min(poll_max_retry, poll_timeout)
        in_data = buffered_read(max_timeout=poll_timeout)


def bulk_session(api, args, routers):
    command = '%s\n' % ' '.join(args.command)
    for rinfo in routers:
        r = api.put('remote/control/csterm/ecmcli-%s/k' % api.session_id,
                    command, id=rinfo['id'])[0]
        print()
        print("%s (%s):" % (rinfo['name'], rinfo['id']))
        print("=" * 80)
        if r['success']:
            if r['data'] == command:
                print("Warning: unsupported firmware")
            else:
                print(r['data'])
        else:
            print("Error:", r['exception'])
            if 'reason' in r:
                print("\tReason:", r['reason'])
            if 'message' in r:
                print("\tMessage:", r['message'])
        print("-" * 80)
        print()
