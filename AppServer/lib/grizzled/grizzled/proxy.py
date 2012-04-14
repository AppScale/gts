# NOTE: Documentation is intended to be processed by epydoc and contains
# epydoc markup.

"""
Overview
========

The ``grizzled.forwarder`` module contain classes that make building proxies
easier.
"""

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import logging
from types import MethodType

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = ['Forwarder']

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log = logging.getLogger('grizzled.proxy')

# ---------------------------------------------------------------------------
# Public classes
# ---------------------------------------------------------------------------

class Forwarder(object):
    """
    The ``grizzled.forwarder.Forwarder`` class is intended to be used as
    a mixin, to make it easier for classes to forward calls to another
    class. The mix ``Forwarder`` into a class, simply include it as
    one of the base classes.

    **WARNING**: ``Forwarder`` intercepts calls to ``__getattr__``, so
    don't mix it in if your class is already overriding ``__getattr__``.

    Examples
    --------

    Forward all unimplemented methods to a file:

    .. python::

        from grizzled.forwarder import Forwarder

        class MyFileWrapper(Forwarder):
            def __init__(self, file):
                Forwarder.__init__(self, file)

        w = MyFileWrapper(open('/tmp/foo'))
        for line in w.readlines():
            print line

    Forward all unimplemented calls, *except* ``name``, to the specified
    object. Calls to ``name`` will raise an ``AttributeError``:

        
    .. python::

        from grizzled.forwarder import Forwarder

        class MyFileWrapper(Forwarder):
            def __init__(self, file):
                Forwarder.__init__(self, file, 'name')
    """

    def __init__(self, wrapped, *exceptions):
        """
        Initialize a new ``Forwarder`` that will pass unimplemented calls
        (method calls, attribute accesses, etc.) to the specified object.

        :Parameters:
            wrapped : object
                the object to which to pass unknown attributes
            exceptions : str
                one or more names (as separate arguments) of methods
                that should not be intercepted (and will, therefore,
                result in ``AttributeError`` exceptions if invoked,
                absent any other intervention).
        """
        self._wrapped = wrapped
        self._exceptions = [e for e in exceptions[0]] # arg tuple to list

    def __getattr__(self, name):
        # Now that we've intercepted __getattr__, we can't access our own
        # attributes directly. Use __getattribute__ to access them.
        obj = self.__getattribute__('_wrapped')
        exceptions = self.__getattribute__('_exceptions')
        if (obj is None) or (name in exceptions):
            self.__getattribute__(name)

        else:
            try:
                attr = getattr(obj, name)
                if isinstance(obj, MethodType):
                    return new.instancemethod(attr.im_func, self, obj.__class__)
                else:
                    return attr
            except AttributeError:
                # Recast error message as being from this class.
                raise AttributeError("'%s' object has no attribute '%s'" %
                                     (self.__class__.__name__, name))
