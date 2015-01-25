"""
Display and edit account and/or group settings.
"""

import argparse

parser = argparse.ArgumentParser(add_help=False)


def command(api, args, router_ids):
    print("SETTINGS")
