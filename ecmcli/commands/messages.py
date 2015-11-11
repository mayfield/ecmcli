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
        messages = list(self.api.get_pager('system_message',
                                           type__nexact='tos'))
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
    """ List messages. """

    name = 'ls'

    def setup_args(self, parser):
        self.inject_table_factory()
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
        with self.make_table(headers=[x[1] for x in self.fields],
                             accessors=[x[0] for x in self.fields]) as t:
            t.print(self.get_messages())


class Read(Common, base.ECMCommand):
    """ Read/Acknowledge a message. """

    name = 'read'

    def setup_args(self, parser):
        self.add_argument('ident', metavar='MESSAGE_ID',
                          complete=self.complete_id)
        super().setup_args(parser)

    def format_msg(self, msg):
        return shellish.htmlrender(msg)

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
        msg = self.api.get_by(['id'], res, ident[1])
        shellish.vtmlprint('<b>Created: %s</b>' % msg['created'])
        shellish.vtmlprint('<b>Subject: %s</b>' % msg['title'])
        if 'message' in msg:
            output = shellish.htmlrender(msg['message'])
            for x in str(output).split('\n'):
                print(textwrap.fill(x.strip(), break_long_words=False,
                                    replace_whitespace=False,
                                    break_on_hyphens=False))
        if ident[0] == 'usr':
            if not msg['is_read']:
                self.api.put(res, ident[1], {"is_read": True})
        elif not msg['confirmed']:
            self.api.post('system_message_confirm',
                          {"message": msg['resource_uri']})


class Messages(base.ECMCommand):
    """ Read/Acknowledge any messages from the system. """

    name = 'messages'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_subcommand(List, default=True)
        self.add_subcommand(Read)

command_classes = [Messages]
