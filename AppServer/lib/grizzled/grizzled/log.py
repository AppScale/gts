#!/usr/bin/env python
# ---------------------------------------------------------------------------

"""
Provides some classes and functions for use with the standard Python
``logging`` module.
"""

__docformat__ = "restructuredtext en"

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import logging
import sys
import textwrap

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = ['WrappingLogFormatter', 'init_simple_stream_logging']

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class WrappingLogFormatter(logging.Formatter):
    """
    A ``logging`` ``Formatter`` class that writes each message wrapped on line
    boundaries. Here's a typical usage scenario:
    
    .. python::
    
        import logging
        import sys
        from grizzled.log import WrappingLogFormatter

        stderr_handler = logging.StreamHandler(sys.stderr)
        formatter = WrappingLogFormatter(format='%(levelname)s %(message)s")
        stderr_handler.setLevel(logging.WARNING)
        stderr_handler.setFormatter(formatter)
        logging.getLogger('').handlers = [stderr_handler]
    """
    def __init__(self, format=None, date_format=None, max_width=79):
        """
        Initialize a new ``WrappingLogFormatter``.

        :Parameters:
            format : str
                The format to use, or ``None`` for the logging default

            date_format : str
                Date format, or ``None`` for the logging default

            max_width : int
                Maximum line width, or ``None`` to default to 79./
        """
        self.wrapper = textwrap.TextWrapper(width=max_width,
                                            subsequent_indent='    ')
        logging.Formatter.__init__(self, format, date_format)

    def format(self, record):
        s = logging.Formatter.format(self, record)
        result = []
        for line in s.split('\n'):
            result += [self.wrapper.fill(line)]

        return '\n'.join(result)

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def init_simple_stream_logging(level=logging.INFO,
                               streams=None,
                               format=None,
                               date_format=None):
    """
    Useful for simple command-line tools, this method configures the Python
    logging API to:
    
    - log to one or more open streams (defaulting to standard output) and
    - use a ``WrappingLogFormatter``

    :Parameters:
        level : int
            Desired log level

        streams : list
            List of files or file-like objects to which to log, or ``None``
            to log to standard output only
            
        format : str
            Log format to use, or ``None`` to use a reasonable default

        date_format : str
            Date format to use in logging, or ``None`` to use a reasonable
            default
    """
    if not streams:
        streams = [sys.stdout]

    if not format:
        format = '%(asctime)s %(message)s'

    if not date_format:
        date_format = '%H:%M:%S'

    logging.basicConfig(level=level)
    handlers = []

    formatter = WrappingLogFormatter(format=format, date_format=date_format)
    for stream in streams:
        log_handler = logging.StreamHandler(stream)
        log_handler.setLevel(level)
        log_handler.setFormatter(formatter)

        handlers += [log_handler]

    logging.getLogger('').handlers = handlers
