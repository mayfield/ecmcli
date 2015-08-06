"""
Get and set configs for routers and groups.
"""

import json
from . import base


def walk_config(key, config):
    if key is None:
        return config
    offt = config
    sentinel = object()
    for x in key.split('.'):
        offt = offt.get(x, sentinel)
        if offt is sentinel:
            return None
    return offt


class Config(base.Command):
    """ Get and set configs for routers and groups. """

    name = 'config'

    def setup_args(self, parser):
        parser.add_argument('--group', metavar='ID_OR_NAME')
        parser.add_argument('get_or_set', metavar='GET_OR_SET', nargs='?',
                            help='key or key=value')

    def run(self, args):
        routers = self.api.get_pager('routers')
        if not args.get_or_set:
            return self.get_value(routers, None)
        get_or_set = args.get_or_set.split('=', 1)
        key = get_or_set.pop(0)
        if get_or_set:
            value = get_or_set[0]
            return self.set_value(routers, key, value)
        else:
            return self.get_value(routers, key)

    def set_value(self, routers, key, value):
        for x in routers:
            ok = self.api.put('remote', 'config', key.replace('.', '/'),
                              json.loads(value), id=x['id'])[0]
            status = 'okay' if ok['success'] else ok['exception']
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
