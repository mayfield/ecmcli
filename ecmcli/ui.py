"""
User interface collection.
"""

import humanize


def time_since(dt):
    """ Return a human string indicating how much time as passed since this
    datetime. """
    if dt is None:
        return ''
    since = dt.now(tz=dt.tzinfo) - dt
    return humanize.naturaltime(since)[:-4]
