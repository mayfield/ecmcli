"""
List ECM Routers.
"""

import argparse
import html

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('-v', '--verbose', action='store_true',
                    help="Verbose output.")


def command(api, args, routers):
    printfn = verbose_print if args.verbose else terse_print
    for rid, rinfo in routers.items():
        printfn(rid, rinfo)


def verbose_print(rid, rinfo):
    print('VERBOSE', rid, rinfo)


def terse_print(rid, rinfo):
    print('TERSE', rid, rinfo)
