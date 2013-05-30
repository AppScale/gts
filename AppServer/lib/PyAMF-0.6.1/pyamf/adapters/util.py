# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Useful helpers for adapters.

@since: 0.4
"""

import __builtin__

if not hasattr(__builtin__, 'set'):
    from sets import Set as set


def to_list(obj, encoder):
    """
    Converts an arbitrary object C{obj} to a C{list}.
    """
    return list(obj)


def to_dict(obj, encoder):
    """
    Converts an arbitrary object C{obj} to a C{dict}.
    """
    return dict(obj)


def to_set(obj, encoder):
    """
    Converts an arbitrary object C{obj} to a C{set}.
    """
    return set(obj)


def to_tuple(x, encoder):
    """
    Converts an arbitrary object C{obj} to a C{tuple}.
    """
    return tuple(x)


def to_string(x, encoder):
    """
    Converts an arbitrary object C{obj} to a string.

    @since: 0.5
    """
    return str(x)
