"""
Flash LEDS of the router(s).
"""

import argparse
import html
import time
from syndicate import data as syndata

MIN_FLASH_DELAY = 0.200

parser = argparse.ArgumentParser(add_help=False)


def command(api, args, router_ids):
    print("Flashing LEDS for:")
    rfilter = {
        "id__in": ','.join(map(str, router_ids)),
        "timeout": 0
    }
    for rid, rinfo in router_ids.items():
        print("    %s (%s)" % (rinfo['name'], rid))
    leds = dict.fromkeys((
        "LED_ATTENTION",
        "LED_SS_1",
        "LED_SS_2",
        "LED_SS_3",
        "LED_SS_4"
    ), 0)
    while True:
        for k, v in leds.items():
            leds[k] = not v
        start = time.time()
        api.put('remote/control/gpio', leds, **rfilter)
        time.sleep(max(0, MIN_FLASH_DELAY - (time.time() - start)))
