"""
User interface collection.
"""

import datetime
import dateutil
import humanize

localtz = dateutil.tz.tzlocal()


def time_since(dt):
    """ Return a human string indicating how much time as passed since this
    datetime. """
    if dt is None:
        return ''
    since = dt.now(tz=dt.tzinfo) - dt
    return humanize.naturaltime(since)[:-4]


def parse_ts(ts, **kwargs):
    dt = dateutil.parser.parse(ts)
    return localize_dt(dt, **kwargs)


def localize_dt(dt, tz=localtz):
    return dt.astimezone(tz)


def localnow(tz=localtz):
    return datetime.datetime.now(tz=tz)


def formatdate(dt, format='%b %d, %Y'):
    return dt.strftime(format)


def formattime(dt, format='%I:%M %p %Z'):
    return dt.strftime(format)


def formatdatetime(dt, timeformat=None, dateformat=None):
    d = formatdate(dt, format=dateformat) if dateformat else formatdate(dt)
    t = formattime(dt, format=timeformat) if timeformat else formattime(dt)
    return '%s, %s' % (d, t)


def naturaldelta(td):
    return humanize.naturaldelta(td)
