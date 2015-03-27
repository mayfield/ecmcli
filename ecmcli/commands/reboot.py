"""
Flash LEDS of the router(s).
"""

import argparse

parser = argparse.ArgumentParser(add_help=False)


def command(api, args, routers=None):
    print("Rebooting:")
    rfilter = {
        "id__in": ','.join(routers),
        "timeout": 0
    }
    for rid, rinfo in routers.items():
        print("    %s (%s)" % (rinfo['name'], rid))
    api.put('remote/control/system/reboot', True, **rfilter)
