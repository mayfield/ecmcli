"""
List ECM Groups.
"""

import argparse
import html

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('-v', '--verbose', action='store_true',
                    help="Verbose output.")



def command(api, args):
    printer = verbose_printer if args.verbose else terse_printer
    printer(api=api)


def verbose_printer(api=None):
    pass


def terse_printer(api=None):
    for x in api.get_pager('groups', expand='statistics'):
        x['name'] = html.unescape(x['name'])
        print('%(name)25s %(id)6s' % x, 'synced: %(synched_count)-5d online:' \
              ' %(online_count)-5d offline: %(offline_count)-5d' %
              x['statistics'])
