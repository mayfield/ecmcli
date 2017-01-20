"""
Activity Log
"""

import collections
import shellish
from . import base
from .. import ui


actor_types = {
    1: 'system',
    2: 'user',
    3: 'api_key',
    4: 'router',
}


activity_types = {
    1: "created",
    2: "deleted",
    3: "updated",
    4: "requested",
    5: "reported",
    6: "logged in",
    7: "logged out",
    8: "registered",
    9: "unregistered",
    10: "activated",
}


object_types = {
    1: "account",
    2: "user",
    3: "group",
    4: "router",
    5: "schedule",
    # 6 deprecated
    7: "task",
    8: "api_key",
    9: "net_device",
    10: "notifier",
    11: "feature_binding",
    12: "authorization",
}


class ActivityLog(base.ECMCommand):
    """ Activity log commands. """

    name = 'activity-log'

    def setup_args(self, parser):
        self.add_subcommand(List, default=True)
        self.add_subcommand(Webhook)


class List(base.ECMCommand):
    """ Tabulate activity log. """

    name = 'ls'

    def setup_args(self, parser):
        self.inject_table_factory()
        super().setup_args(parser)

    @shellish.ttl_cache(300)
    def get_actor(self, itype, id):
        kind = actor_types[itype]
        if kind == 'user':
            user = self.api.get('users', str(id))
            return '<i>(user)</i> %s %s (%d)' % (user['first_name'],
                user['last_name'], id)
        elif kind == 'router':
            router = self.api.get('routers', str(id))
            return '<i>(router)</i> %s (%d)' % (router['name'], id)
        else:
            raise TypeError("unsupported actor: %s" % kind)

    @shellish.ttl_cache(300)
    def get_object(self, itype, id):
        kind = object_types[itype]
        if kind == 'user':
            user = self.api.get('users', str(id))
            return 'user: <cyan>%s %s</cyan> (%d)' % (user['first_name'],
                user['last_name'], id)
        elif kind == 'router':
            router = self.api.get('routers', str(id))
            return 'router: <blue>%s</blue> (%d)' % (router['name'], id)
        else:
            raise TypeError("unsupported actor: %s" % kind)

    def unhandled(self, kind):
        def fn(row):
            return 'Unsupported [%s]: %s' % (kind, row)
        return fn

    def handle_request(self, row):
        return '<b>{actor[username]} ({actor[id]})</b> {operation[name]} of ' \
            '<blue>{object[name]} ({object[id]})</blue>' \
            .format(**row['attributes'])

    def handle_update_details(self, row):
        attrs = row['attributes']
        if attrs['actor'] == attrs['object']:
            src = 'local-device'
        else:
            src = self.get_actor(row['actor_type'], row['actor_id'])
        dst = '%s (%s)' % (attrs['object']['name'], attrs['object']['id'])
        updates = list(base.totuples(attrs['diff']['target_config'][0]))
        updates.extend(('.'.join(map(str, x)), '<red><i>DELETED</i></red>')
                       for x in attrs['diff']['target_config'][1])
        pretty_updates = ', '.join('%s=<b><i>%s</i></b>' % x for x in updates)
        return 'Config changed by <b>%s</b> on <b>%s</b>: <blue>%s</blue>' % (
            src, dst, pretty_updates)

    def handle_update_diff(self, row):
        attrs = row['attributes']
        if attrs['actor'] == attrs['object']:
            src = 'local-device'
        else:
            src = self.get_actor(row['actor_type'], row['actor_id'])
        dst = '%s (%s)' % (attrs['object']['name'], attrs['object']['id'])
        updates = len(list(base.totuples(attrs['diff']['target_config'][0])))
        removals = len(attrs['diff']['target_config'][1])
        stat = []
        if updates:
            stat.append('<cyan>+%d</cyan>' % updates)
        if removals:
            stat.append('<magenta>-%d</magenta>' % removals)
        return 'Config changed by <b>%s</b> on <blue>%s</blue>: <b>%s</b> differences' % (
            src, dst, '/'.join(stat))

    def handle_login(self, row):
        return '<b>{actor[username]} ({actor[id]})</b> logged into ECM' \
            .format(**row['attributes'])

    def handle_logout(self, row):
        return '<b>{actor[username]} ({actor[id]})</b> logged out of ECM' \
            .format(**row['attributes'])

    def handle_fw_report(self, row):
        fw = row['attributes']['after']['actual_firmware']
        return '{actor[name]} ({actor[id]}) firmware upgraded to ' \
            '<blue><b>{fw[version]}</b></blue>' \
            .format(fw=fw, **row['attributes'])

    def handle_register(self, row):
        attrs = row['attributes']
        if attrs['actor'] == attrs['object']:
            src = 'local-device'
        else:
            # XXX Never seen before, but is probably some sort of insecure
            # activation thing and not a router or user.
            raise NotImplementedError(str(attrs['actor']))
        router = '%s (%s)' % (attrs['object']['name'], attrs['object']['id'])
        return 'Router registered by <b>%s</b>: <blue>%s</blue>' % (src,
            router)

    def parse_activity(self, row):
        handlers = {
            1: self.unhandled("create"),
            2: self.unhandled("delete"),
            3: self.handle_update_diff,
            4: self.handle_request,
            5: self.handle_fw_report,
            6: self.handle_login,
            7: self.handle_logout,
            8: self.handle_register,
            9: self.unhandled("unregister"),
            10: self.unhandled("activate"),
        }
        return handlers[row['activity_type']](row)

    def run(self, args):
        fields = collections.OrderedDict((
            ('Activity', self.parse_activity),
            ('Time', lambda x: ui.formatdatetime(ui.localize_dt(x['created_at'])))
        ))
        with self.make_table(headers=fields.keys(),
                             accessors=fields.values()) as t:
            t.print(self.api.get_pager('activity_logs',
                                       order_by='-created_at_timeuuid'))


class Webhook(base.ECMCommand):
    """ Monitor for new events and post them to a webhook. """

    name = 'webhook'

    def run(self, args):
        raise NotImplementedError("")


command_classes = [ActivityLog]
