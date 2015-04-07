"""
Flash LEDS of the router(s).
"""

import argparse

parser = argparse.ArgumentParser(add_help=False)


def command(api, args, routers=None):
    print("Rebooting:")
    for rinfo in routers:
        print("    %s (%s)" % (rinfo['name'], rinfo['id']))
        api.put('remote/control/system/reboot', True, timeout=0,
                id=rinfo['id'])
