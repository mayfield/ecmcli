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

stdin = sys.stdin.fileno()


def command(api, args, routers):
    if args.interact:
        return interactive_session(api, args.interact)
    else:
        return bulk_session(api, args, routers)


def interactive_session(api, router):
    h, w = struct.unpack('hh', fcntl.ioctl(stdin, termios.TIOCGWINSZ, '1234'))
    print("Connecting to: Router %s" % router)
    out = api.put('remote/control/csterm/ecmcli-%s' % api.sessionid, {
        "w": w,
        "h": h
    }, id=router)[0]
    ttysave = termios.tcgetattr(stdin)
    tty.setraw(stdin)
    fl = fcntl.fcntl(stdin, fcntl.F_GETFL)
    fcntl.fcntl(stdin, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    try:
        _interactive_session(api, router)
    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, ttysave)


def buffered_read(timeout=0.200):
    """ Read from stdin up to an anthrophmoric timeout. """
    buf = []
    while True:
        ts = time.time()
        if select.select([stdin], [], [], timeout-(time.time()-ts))[0]:
            buf.append(sys.stdin.read())
        else:
            print("RETURN", buf)
            return ''.join(buf)


def _interactive_session(api, router):
    while True:
        in_data = buffered_read()
        while True:
            out = api.put('remote/control/csterm/ecmcli-%s/k' % api.sessionid,
                          in_data, id=router)[0]
            in_data = ""
            if out['success']:
                os.write(sys.stdout.fileno(), html.unescape(out['data']).encode())
            else:
                raise Exception('%s (%s)' % (out['exception'], out['reason']))


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
