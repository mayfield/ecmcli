"""
Get and set configs for routers and groups.
"""

import argparse
import json
from . import base


def walk_config(key, config):
    if key is None:
        return config
    offt = config
    for x in key.split('.'):
        try:
            offt = offt[x]
        except KeyError:
            return None
        except TypeError:
            if x.isnumeric():
                try:
                    offt = offt[int(x)]
                except IndexError:
                    return None
            else:
                return None
    return offt


class Config(base.ECMCommand):
    """ [EXPEREMENTAL] Get and set configs for routers and groups. """

    name = 'config'

    def setup_args(self, parser):
        self.add_argument('--group', metavar='ID_OR_NAME',
                          complete=self.make_completer('groups', 'name'))
        self.add_argument('get_or_set', metavar='GET_OR_SET',
                          nargs=argparse.REMAINDER,
                          help='key || key=json_value')

    def run(self, args):
        routers = self.api.get_pager('routers')
        if not args.get_or_set:
            return self.get_value(routers, None)
        get_or_set = ' '.join(args.get_or_set).split('=', 1)
        key = get_or_set.pop(0)
        if get_or_set:
            value = get_or_set[0]
            return self.set_value(routers, key, value)
        else:
            return self.get_value(routers, key)

    def set_value(self, routers, key, value):
        try:
            value = json.loads(value)
        except ValueError as e:
            raise SystemExit('Invalid JSON Value: %s' % e)
        for x in routers:
            ok = self.api.put('remote', 'config', key.replace('.', '/'),
                              value, id=x['id'])[0]
            status = 'okay' if ok['success'] else \
                     '%s %s' % (ok['exception'], ok.get('message', ''))
            print('%s:' % x['name'], status)

    def get_value(self, routers, key):
        for x in routers:
            diff = self.api.get('routers', x['id'], 'configuration_manager',
                                'configuration')
            updates, removals = diff
            path = x['name']
            if key:
                path += '.%s' % key
            print(path, '=', json.dumps(walk_config(key, updates), indent=4))

command_classes = [Config]
