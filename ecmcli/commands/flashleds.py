"""
Flash LEDS of the router(s).
"""

import sys
import time
from . import base


class FlashLEDS(base.ECMCommand):
    """ Flash the LEDs of online routers. """

    name = 'flashleds'
    min_flash_delay = 0.200
    use_pager = False

    def run(self, args):
        routers = self.api.get_pager('routers')
        ids = []
        print("Flashing LEDS for:")
        for rinfo in routers:
            print("    %s (%s)" % (rinfo['name'], rinfo['id']))
            ids.append(rinfo['id'])
        rfilter = {
            "id__in": ','.join(ids)
        }
        leds = dict.fromkeys((
            "LED_ATTENTION",
            "LED_SS_1",
            "LED_SS_2",
            "LED_SS_3",
            "LED_SS_4"
        ), 0)
        print()
        while True:
            for k, v in leds.items():
                leds[k] = state = not v
            start = time.time()
            self.api.put('remote', '/control/gpio', leds, **rfilter)
            print("\rLEDS State: %s" % ('ON ' if state else 'OFF'), end='')
            sys.stdout.flush()
            time.sleep(max(0, self.min_flash_delay - (time.time() - start)))

command_classes = [FlashLEDS]
