
# NOTE: Documentation is intended to be processed by epydoc and contains
# epydoc markup.

"""
Overview
========

The ``grizzled.misc`` module contains miscellanous functions and classes that
don't seem to fit well in other modules.
"""

__docformat__ = "restructuredtext en"

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import logging

from grizzled.exception import ExceptionWithMessage

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = ['ReadOnly', 'ReadOnlyObjectError']

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log = logging.getLogger('grizzled.misc')

# ---------------------------------------------------------------------------
# Public classes
# ---------------------------------------------------------------------------

class ReadOnlyObjectError(ExceptionWithMessage):
    """
    Thrown by ``ReadOnly`` to indicate an attempt to set a field.

    :IVariables:
        field_name : str
            name of the read-only field that could not be set

        message : str
            message to associated with the exception
    """
    def __init__(self, field_name, message):
        ExceptionWithMessage.__init__(self, message)
        self.field_name = field_name

class ReadOnly(object):
    """
    A ``ReadOnly`` object wraps another object and prevents all the contained
    object's fields from being written. Example use:

    .. python::

        from grizzled.misc import ReadOnly
        from grizzled.config import Configuration

        config = Configuration()
        config.read('/path/to/some/file')
        roConfig = ReadOnly(config)

    Any attempt to set fields within ``roConfig`` will cause a
    ``ReadOnlyObjectError`` to be raised.

    The ``__class__`` member of the instantiate ``ReadOnly`` class will be the
    class of the contained object, rather than ``ReadOnly``
    (``Configuration`` in the example). Similarly, the ``isinstance()``
    built-in function will compare against the contained object's class.
    However, the ``type()`` built-in will return the ``ReadOnly`` class
    object.
    """
    def __init__(self, wrapped):
        """
        Create a new ``ReadOnly`` object that wraps the ``wrapped`` object
        and enforces read-only access to it.

        :Parameters:
            wrapped : object
                the object to wrap
        """
        self.wrapped = wrapped

    def __getattribute__(self, thing):
        wrapped = object.__getattribute__(self, 'wrapped')
        result = None
        if thing == 'wrapped':
            result = wrapped
        else:
            result = getattr(wrapped, thing)

        return result

    def __setattr__(self, thing, value):
        if thing == 'wrapped':
            object.__setattr__(self, thing, value)
        else:
            raise ReadOnlyObjectError(thing,
                                      'Attempt to access field "%s" of '
                                      'read-only %s object' %
                                      (thing, self.wrapped.__class__.__name__))

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

# backward compatibality
from grizzled.text import str2bool

def bitcount(num):
    """
    Count the number of bits in a numeric (integer or long) value. This
    method is adapted from the Hamming Weight algorithm, described (among
    other places) at http://en.wikipedia.org/wiki/Hamming_weight

    Works for up to 64 bits.

    :Parameters:
        num : int
            The numeric value

    :rtype: int
    :return: The number of 1 bits in the binary representation of ``num``
    """
    # Put count of each 2 bits into those 2 bits.
    num = num - ((num >> 1) & 0x5555555555555555)

    # Put count of each 4 bits into those 4 bits.
    num = (num & 0x3333333333333333) + ((num >> 2) & 0x3333333333333333)

    # Put count of each 8 bits into those 8 bits.
    num = (num + (num >> 4)) & 0x0f0f0f0f0f0f0f0f

    # Left-most bits.
    return int((num * 0x0101010101010101) >> 56)

    
