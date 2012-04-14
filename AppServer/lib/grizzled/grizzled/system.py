# NOTE: Documentation is intended to be processed by epydoc and contains
# epydoc markup.

"""
Overview
========

The ``grizzled.system`` module contains some functions and classes that
provide information about the Python system (the Python runtime, the language,
etc.). It is a conceptual extension of the standard Python ``sys`` module.
"""

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import sys as _sys
import logging
import re

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = ['python_version', 'python_version_string', 'ensure_version',
           'split_python_version', 'class_for_name']

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RELEASE_LEVEL_RE = re.compile(r'([0-9]+)(.[0-9]+)?')
RELEASE_LEVELS = {'a' : 0xa, 'b' : 0xb, 'c' : 0xc, 'f' : 0xf}
RELEASE_LEVEL_NAMES = {0xa : 'alpha',
                       0xb : 'beta',
                       0xc : 'candidate',
                       0xf : 'final'}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log = logging.getLogger('grizzled.system')

# ---------------------------------------------------------------------------
# Public classes
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def python_version(version):
    """
    Convert a Python string version (e.g., "2.5.1", "1.3", "2.6a3") to a
    numeric version that can meaningfully be compared with the standard
    ``sys`` module's ``sys.hexversion`` value.

    For example, here's the usual way to ensure that your program is running
    under Python 2.5.1 or better:
    
    .. python::

        import sys

        if sys.hexversion < 0x020501f0:
            raise RuntimeError, 'This program requires Python 2.5.1 or better'

    Here's how you'd use ``python_version()`` to do the same thing (in an
    arguably more readable way):

    .. python::

        import sys
        from grizzled.sys import python_version

        if sys.hexversion < python_version("2.5.1"):
            raise RuntimeError, 'This program requires Python 2.5.1 or better'

    :Parameters:
        version : str
            string Python version to convert to binary

    :rtype:  int
    :return: corresponding integer Python version

    :raise ValueError: ``version`` isn't of the form "x", or "x.y" or
                       "x.y.z"
    """
    err = 'Malformed Python version "%s"' % version

    tokens = version.split('.')
    if len(tokens) > 3:
        raise ValueError, err

    major = int(tokens[0])
    minor = micro = serial = 0
    release_level = 'f'

    if len(tokens) > 1:
        match = RELEASE_LEVEL_RE.match(tokens[1])
        if not match:
            raise ValueError, err

        minor = int(match.group(1))
        rl = match.group(2)
        if rl:
            release_level = rl[0]
            serial = int(rl[1:])

        if len(tokens) > 2:
            match = RELEASE_LEVEL_RE.match(tokens[2])
            if not match:
                raise ValueError, err

            micro = int(match.group(1))
            rl2 = match.group(2)
            if rl and rl2:
                raise ValueError, err
            if rl2:
                release_level = rl2[0]
                serial = int(rl2[1:])

    try:
        release_level = RELEASE_LEVELS[release_level]
    except KeyError:
        raise ValueError, err

    return (major << 24) |\
           (minor << 16) |\
           (micro << 8) |\
           (release_level << 4) |\
           serial

def split_python_version(version=None):
    """
    Convert a binary Python version string (e.g., ``0x020501f0``) into the
    same (*major*, *minor*, *micro*, *releaselevel*, *serial*) tuple that is
    found in ``sys.version_info``. Thus, for an input value of ``0x020501f0``,
    this function returns the tuple ``(2, 5, 1, 'final', 0)``.

    :Parameters:
        version : int
            Python integer version

    :rtype:  tuple
    :return: The (*major*, *minor*, *micro*, *releaselevel*, *serial*) tuple

    :raise ValueError: Bad version number
    """
    major = (version >> 24) & 0x000000ff
    minor = (version >> 16) & 0x000000ff
    micro = (version >> 8) & 0x000000ff
    release_level = (version >> 4) & 0x0000000f
    serial = version & 0x0000000f

    release_level_string = RELEASE_LEVEL_NAMES.get(release_level, None)
    if not release_level_string:
        raise ValueError, \
              'Bad release level 0x%x in version 0x%08x' %\
              (release_level, version)

    return (major, minor, micro, release_level_string, serial)

def python_version_string(version=None):
    """
    Convert a numeric Python version (such as ``sys.hexversion``) to a
    printable string.

    :Parameters:
        version : int
            Python integer version

    :rtype:  str
    :return: The stringified version
    """
    major, minor, micro, release_level, serial = split_python_version(version)
    s = '%d.%d' % (major, minor)
    if micro > 0:
        s += '.%d' % micro

    if release_level != 'final':
        s += release_level[0]
        s += '%s' % serial

    return s

def ensure_version(min_version):
    """
    Raise a ``RuntimeError`` if the current Python version isn't at least
    ``min_version``. ``min_version`` may be an ``int`` (e.g., ``0x020500f0``)
    or a string (e.g., "2.5.0").

    :Parameters:
        min_version : str or int
            minimum version, as a number or string

    :raise TypeError:    ``min_version`` isn't a string or an integer
    :raise ValueError:   ``min_version`` is a bad Python string version
    :raise RuntimeError: Python version is too old
    """
    if type(min_version) == str:
        min_version = python_version(min_version)
    elif type(min_version) == int:
        pass
    else:
        raise TypeError, \
              'version %s is not a string or an integer' % min_version

    if _sys.hexversion < min_version:
        raise RuntimeError, \
              'This program requires Python version "%s" or better, but ' \
              'the current Python version is "%s".' %\
              (python_version_string(min_version),
               python_version_string(sys.hexversion))


def class_for_name(class_name):
    """
    Given fully-qualified class name, load and return the class object. A
    fully-qualified class name contains the module and package, in addition to
    the simple class name (e.g., ``grizzled.config.Configuration``).

    :Parameters:
        class_name : str
            fully-qualified class name

    :rtype:  class
    :return: the class object

    :raise NameError: Class not found
    """
    tokens = class_name.split('.')
    if len(tokens) > 1:
        package = '.'.join(tokens[:-1])
        class_name = tokens[-1]
        exec 'from %s import %s' % (package, class_name)

    return eval(class_name)
    
