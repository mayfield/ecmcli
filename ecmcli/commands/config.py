"""
Get and set configs for routers and groups.
"""

import argparse
import json

parser = argparse.ArgumentParser(add_help=False)

parser.add_argument('--group', metavar='ID_OR_NAME')
parser.add_argument('GET_OR_SET', nargs='*', help='key or key=value')


def command(api, args, routers):
    if not args.GET_OR_SET:
        return get_value(api, routers, None)
    get_andor_set = ' '.join(args.GET_OR_SET).split('=', 1)
    key = get_andor_set.pop(0)
    if get_andor_set:
        value = get_andor_set[0]
        return set_value(api, routers, key, value)
    else:
        return get_value(api, routers, key)


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


def set_value(api, routers, key, value):
    for x in routers:
        ok = api.put('remote', 'config', key.replace('.', '/'), json.loads(value),
                     id=x['id'])[0]
        print('%s:' % x['name'], 'okay' if ok['success'] else ok['exception'])


def get_value(api, routers, key):
    for x in routers:
        diff = api.get('routers', x['id'], 'configuration_manager',
                       'configuration')
        updates, removals = diff
        path = x['name']
        if key:
            path += '.%s' % key
        print(path, '=', json.dumps(walk_config(key, updates)))
