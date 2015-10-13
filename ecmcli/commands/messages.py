"""
A mail command for user/system messages.
"""

import functools
import humanize
import shellish
import textwrap
from . import base


def ack_wrap(fn):
    """ Add emphasis to unread cells. """

    @functools.wraps(fn)
    def wrap(*args):
        res = fn(*args)
        row = args[-1]
        if not row.get('is_read') and not row.get('confirmed'):
            return '<b>%s</b>' % res
        else:
            return res
    return wrap


class Common(object):

    def get_messages(self):
        """ Combine system and user message streams. """
        messages = list(self.api.get_pager('system_message', type__nexact='tos'))
        messages.extend(self.api.get_pager('user_messages'))
        messages.sort(key=lambda x: x['created'], reverse=True)
        return messages

    @functools.lru_cache()
    def get_user(self, user_urn):
        return self.api.get(urn=user_urn)

    def humantime(self, dt):
        if dt is None:
            return ''
        since = dt.now(tz=dt.tzinfo) - dt
        return humanize.naturaltime(since)


class List(Common, base.ECMCommand):
    """ Show messages. """

    name = 'list'

    def setup_args(self, parser):
        self.add_table_group()
        self.fields = (
            (self.id_acc, 'ID'),
            (self.created_acc, 'Created'),
            (self.user_acc, 'From'),
            (self.title_acc, 'Title'),
            (self.expires_acc, 'Expires'),
        )
        super().setup_args(parser)

    @ack_wrap
    def id_acc(self, x):
        return '%s-%s' % (x['type'], x['id'])

    @ack_wrap
    def created_acc(self, x):
        return self.humantime(x['created'])

    @ack_wrap
    def user_acc(self, x):
        if x['type'] == 'sys':
            return '[ECM]'
        elif x['type'] == 'usr':
            return self.get_user(x['user'])['username']
        else:
            return '[UNSUPPORTED]'

    @ack_wrap
    def title_acc(self, x):
        return x['title']

    @ack_wrap
    def expires_acc(self, x):
        return self.humantime(x['expires'])

    def run(self, args):
        with shellish.Table(headers=[x[1] for x in self.fields],
                            accessors=[x[0] for x in self.fields],
                            renderer=args.table_format) as t:
            t.print(self.get_messages())


class Read(Common, base.ECMCommand):
    """ Read/Acknowledge a message. """

    name = 'read'

    def setup_args(self, parser):
        self.add_argument('ident', metavar='MESSAGE_ID',
                          complete=self.complete_id)
        super().setup_args(parser)

    def format_msg(self, msg):
        """ XXX: Obviously a dirty hack. """
        return textwrap.fill(msg, break_long_words=False)

    @shellish.ttl_cache(60)
    def cached_messages(self):
        return frozenset('%s-%s' % (x['type'], x['id'])
                         for x in self.get_messages())

    def complete_id(self, prefix, args):
        return set(x for x in self.cached_messages()
                   if x.startswith(prefix))

    def run(self, args):
        ident = args.ident.split('-')
        if len(ident) != 2:
            raise SystemExit("Invalid message identity: %s" % args.ident)
        res = {
            "sys": 'system_message',
            "usr": 'user_messages'
        }.get(ident[0])
        if res is None:
            raise SystemExit("Invalid message type: %s" % args.ident[0])
        # NOTE: system_message does not support detail get.
        msg = self.api.get(res, id=ident[1])[0]
        self.vtmlprint('<b>%s</b>' % msg['title'])
        if 'message' in msg:
            print()
            self.vtmlprint(self.format_msg(msg.get('message')))
        if ident[0] == 'usr':
            self.api.put(res, ident[1], {"is_read": True})
        else:
            self.vtmlprint("\n<red><b>WARNING:</b> Confirming system "
                           "messages not supported</red>")


class Messages(base.ECMCommand):
    """ Read/Acknowledge any messages from the system. """

    name = 'messages'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(List, default=True)
        self.add_subcommand(Read)

command_classes = [Messages]
