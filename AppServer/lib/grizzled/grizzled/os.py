#!/usr/bin/env python

# NOTE: Documentation is intended to be processed by epydoc and contains
# epydoc markup.

"""
Overview
========

The ``grizzled.os`` module contains some operating system-related functions and
classes. It is a conceptual extension of the standard Python ``os`` module.
"""

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import logging
import os as _os
import sys
import glob
from contextlib import contextmanager

from grizzled.decorators import deprecated

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = ['daemonize', 'DaemonError', 'working_directory',
           'file_separator', 'path_separator']

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default daemon parameters.
# File mode creation mask of the daemon.
UMASK = 0

# Default working directory for the daemon.
WORKDIR = "/"

# Default maximum for the number of available file descriptors.
MAXFD = 1024

# The standard I/O file descriptors are redirected to /dev/null by default.
if (hasattr(_os, "devnull")):
    NULL_DEVICE = _os.devnull
else:
    NULL_DEVICE = "/dev/null"

# The path separator for the operating system.

PATH_SEPARATOR = {'nt' : ';', 'posix' : ':'}
FILE_SEPARATOR = {'nt' : '\\', 'posix' : '/'}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log = logging.getLogger('grizzled.os')

# ---------------------------------------------------------------------------
# Public classes
# ---------------------------------------------------------------------------

class DaemonError(OSError):
    """
    Thrown by ``daemonize()`` when an error occurs while attempting to create
    a daemon.
    """
    pass

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def path_separator():
    """
    Get the path separator for the current operating system. The path
    separator is used to separate elements of a path string, such as
    "PATH" or "CLASSPATH". (It's a ":" on Unix-like systems and a ";"
    on Windows.)

    :rtype: str
    :return: the path separator
    """
    return PATH_SEPARATOR[_os.name]

@deprecated(since='0.7', message='Use os.path.sep, instead.')
def file_separator():
    """
    Get the file separator for the current operating system. The file
    separator is used to separate file elements in a pathname. (It's
    "/" on Unix-like systems and a "\\\\" on Windows.)
    
    **Deprecated**. Use the standard Python ``os.path.sep`` variable,
    instead.

    :rtype: str
    :return: the file separator
    """
    return FILE_SEPARATOR[_os.name]

def path_elements(path):
    """
    Given a path string value (e.g., the value of the environment variable
    ``PATH``), this generator function yields each item in the path.

    :Parameters:
        path
            the path to break up
    """
    for p in path.split(path_separator()):
        yield p

@contextmanager
def working_directory(directory):
    """
    This function is intended to be used as a ``with`` statement context
    manager. It allows you to replace code like this:

    .. python::

        original_directory = _os.getcwd()
        try:
            _os.chdir(some_dir)
            ... bunch of code ...
        finally:
            _os.chdir(original_directory)

    with something simpler:

    .. python ::

        from __future__ import with_statement
        from grizzled.os import working_directory

        with working_directory(some_dir):
            ... bunch of code ...

    :Parameters:
        directory : str
            directory in which to execute

    :return: yields the ``directory`` parameter
    """
    original_directory = _os.getcwd()
    try:
        _os.chdir(directory)
        yield directory

    finally:
        _os.chdir(original_directory)

def find_command(command_name, path=None):
    """
    Determine whether the specified system command exists in the specified
    path.

    :Parameters:
        command_name
            The (simple) filename of the command to find. May be a glob
            string.

        path
            The path to search, as a list or a string. If this parameter
            is a string, then it is split using the operating system-specific
            path separator. If this parameter is missing, then the ``PATH``
            environment variable is used

    :rtype: str
    :return: The path to the first command that matches ``command_name``, or 
             ``None`` if not found
    """
    if not path:
        path = _os.environ.get('PATH', '.')

    if type(path) == str:
        path = path.split(path_separator())
    elif type(path) == list:
        pass
    else:
        assert False, 'path parameter must be a list or a string'

    found = None
    for p in path:
        full_path = _os.path.join(p, command_name)
        for p2 in glob.glob(full_path):
            if _os.access(p2, _os.X_OK):
                found = p2
                break

        if found:
            break

    return found

def spawnd(path, args, pidfile=None):
    """
    Run a command as a daemon. This method is really just shorthand for the
    following code:
    
    .. python::
    
        daemonize(pidfile=pidfile)
        _os.execv(path, args)

    :Parameters:
        path : str
            Full path to program to run
            
        args : list
            List of command arguments. The first element in this list must
            be the command name (i.e., arg0).
            
        pidfile : str
            Path to file to which to write daemon's process ID. The string may
            contain a ``${pid}`` token, which is replaced with the process ID
            of the daemon. e.g.: ``/var/run/myserver-${pid}``
    """
    daemonize(no_close=True, pidfile=pidfile)
    _os.execv(path, args)

def daemonize(no_close=False, pidfile=None):
    """
    Convert the calling process into a daemon. To make the current Python
    process into a daemon process, you need two lines of code:

    .. python::

        from grizzled.os import daemonize
        daemonize.daemonize()

    If ``daemonize()`` fails for any reason, it throws a ``DaemonError``,
    which is a subclass of the standard ``OSError`` exception. also logs debug
    messages, using the standard Python ``logging`` package, to channel
    "grizzled.os.daemon".

    **Adapted from:** http://software.clapper.org/daemonize/

    **See Also:**

    - Stevens, W. Richard. *Unix Network Programming* (Addison-Wesley, 1990).

    :Parameters:
        no_close : bool
            If ``True``, don't close the file descriptors. Useful if the
            calling process has already redirected file descriptors to an
            output file. **Warning**: Only set this parameter to ``True`` if
            you're *sure* there are no open file descriptors to the calling
            terminal. Otherwise, you'll risk having the daemon re-acquire a
            control terminal, which can cause it to be killed if someone logs
            off that terminal.

        pidfile : str
            Path to file to which to write daemon's process ID. The string may
            contain a ``${pid}`` token, which is replaced with the process ID
            of the daemon. e.g.: ``/var/run/myserver-${pid}``

    :raise DaemonError: Error during daemonizing
    """
    log = logging.getLogger('grizzled.os.daemon')

    def __fork():
        try:
            return _os.fork()
        except OSError, e:
            raise DaemonError, ('Cannot fork', e.errno, e.strerror)

    def __redirect_file_descriptors():
        import resource  # POSIX resource information
        maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
        if maxfd == resource.RLIM_INFINITY:
            maxfd = MAXFD

        # Close all file descriptors.

        for fd in range(0, maxfd):
            # Only close TTYs.
            try:
                _os.ttyname(fd)
            except:
                continue

            try:
                _os.close(fd)
            except OSError:
                # File descriptor wasn't open. Ignore.
                pass

            # Redirect standard input, output and error to something safe.
            # os.open() is guaranteed to return the lowest available file
            # descriptor (0, or standard input). Then, we can dup that
            # descriptor for standard output and standard error.

            _os.open(NULL_DEVICE, _os.O_RDWR)
            _os.dup2(0, 1)
            _os.dup2(0, 2)


    if _os.name != 'posix':
        import errno
        raise DaemonError, \
              ('daemonize() is only supported on Posix-compliant systems.',
               errno.ENOSYS, _os.strerror(errno.ENOSYS))

    try:
        # Fork once to go into the background.

        log.debug('Forking first child.')
        pid = __fork()
        if pid != 0:
            # Parent. Exit using os._exit(), which doesn't fire any atexit
            # functions.
            _os._exit(0)

        # First child. Create a new session. os.setsid() creates the session
        # and makes this (child) process the process group leader. The process
        # is guaranteed not to have a control terminal.
        log.debug('Creating new session')
        _os.setsid()

        # Fork a second child to ensure that the daemon never reacquires
        # a control terminal.
        log.debug('Forking second child.')
        pid = __fork()
        if pid != 0:
            # Original child. Exit.
            _os._exit(0)

        # This is the second child. Set the umask.
        log.debug('Setting umask')
        _os.umask(UMASK)

        # Go to a neutral corner (i.e., the primary file system, so
        # the daemon doesn't prevent some other file system from being
        # unmounted).
        log.debug('Changing working directory to "%s"' % WORKDIR)
        _os.chdir(WORKDIR)

        # Unless no_close was specified, close all file descriptors.
        if not no_close:
            log.debug('Redirecting file descriptors')
            __redirect_file_descriptors()

        if pidfile:
            from string import Template
            t = Template(pidfile)
            pidfile = t.safe_substitute(pid=str(_os.getpid()))
            open(pidfile, 'w').write(str(_os.getpid()) + '\n')

    except DaemonError:
        raise

    except OSError, e:
        raise DaemonError, ('Unable to daemonize()', e.errno, e.strerror)

# ---------------------------------------------------------------------------
# Main program (for testing)
# ---------------------------------------------------------------------------

if __name__ == '__main__':

    log = logging.getLogger('grizzled.os')
    hdlr = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s', '%T')
    hdlr.setFormatter(formatter)
    log.addHandler(hdlr)
    log.setLevel(logging.DEBUG)

    log.debug('Before daemonizing, PID=%d' % _os.getpid())
    daemonize(no_close=True)
    log.debug('After daemonizing, PID=%d' % _os.getpid())
    log.debug('Daemon is sleeping for 10 seconds')

    import time
    time.sleep(10)

    log.debug('Daemon exiting')
    sys.exit(0)
