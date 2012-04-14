# $Id: 2f91144fd898abfc5994a3a7de580cde341c5c07 $

"""
Provides some base exception classes.
"""

__docformat__ = "restructuredtext en"

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = ['ExceptionWithMessage']

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class ExceptionWithMessage(Exception):
    """
    Useful base class for exceptions that have a single exception message
    argument. Among other things, this method provides a reasonable default
    ``__str__()`` method.

    Usage:
    
    .. python::

        from grizzled.exception import ExceptionWithMessage

        class MyException(ExceptionWithMessage):
            def __init__(self, msg):
                ExceptionWithMessage.__init__(self, msg)
    """
    def __init__(self, errorMessage):
        """
        Create a new exception.

        @type errorMessage:  string
        @param errorMessage: the error message
        """
        self.__message = errorMessage

    @property
    def message(self):
        """
        The message stored with this object.
        """
        return self.__message

    def __str__(self):
        return '%s: %s' % (self.__class__.__name__, self.__message)
