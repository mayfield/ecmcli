"""
Flash LEDS of the router(s).
"""

import argparse

parser = argparse.ArgumentParser(add_help=False)


def command(api, args, router_ids):
    print("Rebooting:")
    rfilter = {
        "id__in": ','.join(map(str, router_ids)),
        "timeout": 0
    }
    for rid, rinfo in router_ids.items():
        print("    %s (%s)" % (rinfo['name'], rid))
    api.put('remote/control/system/reboot', True, **rfilter)
