"""
``grizzled.history`` provides a command line history capability that
provides the same interface across different history implementations.
Currently, it supports three history implementations:

- `GNU Readline`_, which is built into versions of Python on the Mac
  and Unix systems
- `pyreadline`_, which many people use on Windows systems
- A dummy fallback history implementation that does nothing, for when readline
  isn't available.
  
The `History` class provides the interface and some common methods for
all history operations.

.. _pyreadline: http://ipython.scipy.org/dist/
.. _GNU Readline: http://cnswww.cns.cwru.edu/php/chet/readline/rluserman.html

To get the appropriate History implementation for the current platform,
simply call the ``get_history()`` factory method.
"""

from __future__ import with_statement

__docformat__ = "restructuredtext en"

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import re
import sys
import logging
import copy

from grizzled.decorators import abstract
from grizzled.exception import ExceptionWithMessage

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = ['get_history', 'History', 'DEFAULT_MAXLENGTH', 'HistoryError']
__docformat__ = 'restructuredtext'

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MAXLENGTH = 512

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

log = logging.getLogger('history')
_have_readline = False
_have_pyreadline = False

try:
    import readline
    _have_readline = True

    # Is it pyreadline? If so, it's not quite the same.

    try:
        _have_pyreadline = readline.rl.__module__.startswith('pyreadline.')
    except AttributeError:
        pass
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def get_history(verbose=True):
    """
    Factory method to create an appropriate History object.

    :Parameters:
        verbose : bool
            ``True`` to display a message on standard output about what
            history management mechanism is being used.

    :rtype: ``History``
    :return: the ``History`` object
    """
    global _have_readline
    global _have_pyreadline
    result = None
    if _have_pyreadline:
        if verbose:
            print 'Using pyreadline for history management.'
        result = PyReadlineHistory()

    elif _have_readline:
        if verbose:
            print 'Using readline for history management.'
        result = ReadlineHistory()

    else:
        print 'WARNING: Readline unavailable. There will be no history.'
        result = DummyHistory()

    result.max_length = DEFAULT_MAXLENGTH
    return result

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class HistoryError(ExceptionWithMessage):
    """
    Thrown to indicate history errors, when another exception won't do.
    """
    pass

class History(object):
    """
    Base class for history implementations.  All concrete history
    implementations must extend this class.
    """
    def __init__(self):
        self.set_max_length(DEFAULT_MAXLENGTH)

    def show(self, out=sys.stdout):
        """
        Dump the history to a file-like object (defaulting to standard output).

        :Parameters:
            out : file
                Where to dump the history.
        """
        for i in range(1, self.total + 1):
            print >> out, '%4d: %s' % (i, self.get_item(i))

    def get_last_matching_item(self, command_name):
        """
        Get the most recently entered item that matches ``command_name``
        at the beginning.

        :Parameters:
            command_name : str
                The string to match against the commands in the history

        :rtype: str
        :return: the matching string, or ``None``
        """
        result = None
        for i in range(self.get_total(), 0, -1):
            s = self.get_item(i)
            tokens = s.split(None, 1)
            if len(command_name) <= len(s):
                if s[0:len(command_name)] == command_name:
                    result = s
                    break
        return result

    def get_last_item(self):
        """
        Get the most recent item in the history.

        :rtype: str
        :return: The most recent command, or ``None``
        """
        return self.get_item(self.get_total() - 1)

    def get_item(self, index):
        """
        Get an item from the history.

        :Parameters:
            index : int
                0-based index of the item to get. The larger the index
                value, the more recent the entry

        :rtype: str
        :return: the item at that index

        :raise IndexError: Index out of range
        """
        return None

    def set_completer_delims(self, s):
        """
        Set the completer delimiters--the characters that delimit tokens
        that are eligible for completion.

        :Parameters:
            s : str
                The delimiters
        """
        pass

    def get_completer_delims(self):
        """
        Get the completer delimiters--the characters that delimit tokens
        that are eligible for completion.

        :rtype: str
        :return: the delimiters
        """
        return ''

    @property
    def total(self):
        """
        The total number number of commands in the history. Identical to
        calling ``get_total()``.
        """
        return self.get_total()

    def get_total(self):
        """
        Get the total number number of commands in the history. Identical to
        the ``total`` property.

        :rtype: int
        :return: the number of commands in the history
        """
        return 0

    def __set_max_length(self, n):
        return self.set_max_length(n)

    def __get_max_length(self):
        return self.get_max_length()

    maxLength = property(__get_max_length, __set_max_length,
                         doc="The maximum length of the history")

    @abstract
    def get_max_length(self):
        """
        Get the maximum length of the history. This isn't the maximum number
        of entries in the in-memory history buffer; instead, it's the maximum
        number of entries that will be saved to the history file. Subclasses
        *must* provide an implementation of this method.

        :rtype: int
        :return: the maximum saved size of the history
        """
        pass

    @abstract
    def set_max_length(self, n):
        """
        Set the maximum length of the history. This isn't the maximum number
        of entries in the in-memory history buffer; instead, it's the maximum
        number of entries that will be saved to the history file.  Subclasses
        *must* provide an implementation of this method.

        :Parameters:
            n : int
                the maximum saved size of the history
        """
        pass

    @abstract
    def add_item(self, line):
        """
        Add (append) a line to the history buffer. Subclasses *must* provide
        an implementation of this method.

        :Parameters:
            line : str
                the command to append to the history
        """
        pass

    @abstract
    def remove_item(self, i):
        """
        Remove a line from the history buffer. Subclasses *must* provide an
        implementation of this method.

        :Parameters:
            i : int
                the 0-based index of the item to be removed
        """
        pass

    @abstract
    def clear_history(self):
        """
        Clear the history buffer. Subclasses *must* provide an
        implementation of this method.
        """
        pass

    def get_history_list(self):
        """
        Get a copy of the history buffer.

        :rtype: list
        :return: a list of commands from the history
        """
        result = []
        for i in range(1, self.total + 1):
            result += [self.get_item(i)]

        return result

    def remove_matches(self, regexp_string):
        """
        Remove all history items that match a regular expression.

        :Parameters:
            regexp_string : str
                the uncompiled regular expression to match

        :raise HistoryError: bad regular expression
        """
        try:
            pat = re.compile(regexp_string)
        except:
            raise HistoryError(str(sys.exc_info[1]))

        buf = []

        for i in range(1, self.total + 1):
            s = self.get_item(i)
            if not pat.match(s):
                buf += [s]

        self.replace_history(buf)

    def cut_back_to(self, index):
        """
        Cut the history back to the specified index, removing all entries
        more recent than that index.

        :Parameters:
            index : int
                the index of the command that should become the last command
                in the history

        :raise IndexError: index out of range
        """
        if (index > 0) and (index <= self.total):
            buf = []
            for i in range(1, index):
                buf += [self.get_item(i)]

            self.replace_history(buf)

    def replace_history(self, commands):
        """
        Replace the entire contents of the history with another set of values

        :Parameters:
            commands : list
                List of strings to put in the history after clearing it of any
                existing entries
        """
        self.clear_history()
        for command in commands:
            self.add_item(command, force=True)

    def save_history_file(self, path):
        """
        Save the history to a file. The file is overwritten with the contents
        of the history buffer.

        :Parameters:
            path : str
                Path to the history file to receive the output.

        :raise IOError: Unable to open file
        """
        log.debug('Writing history file "%s"' % path)
        with open(path, 'w') as f:
            for i in range(1, self.total + 1):
                f.write(self.get_item(i) + '\n')

    def load_history_file(self, path):
        """
        Load the history buffer with the contents of a file, completely
        replacing the in-memory history with the file's contents.

        :Parameters:
            path : str
                Path to the history file to read

        :raise IOError: Unable to open file
        """
        log.debug('Loading history file "%s"' % path)
        with open(path, 'r') as f:
            buf = []
            for line in f:
                buf += [line.strip()]

        max = self.get_max_length()
        if len(buf) > max:
            buf = buf[max]
        self.replace_history(buf)

class ReadlineHistory(History):

    def __init__(self):
        global _have_readline
        assert(_have_readline)
        History.__init__(self)

    def get_item(self, index):
        return readline.get_history_item(index)

    def get_total(self):
        return readline.get_current_history_length()

    def set_completer_delims(self, s):
        readline.set_completer_delims(s)

    def get_completer_delims(self,):
        return readline.get_completer_delims()

    def remove_item(self, index):
        # readline.remove_history_item() doesn't seem to work. Do it the
        # hard way.

        #try:
        #    readline.remove_history_item(i)
        #except ValueError:
        #    pass

        buf = []
        for i in range(1, self.total + 1):
            if i != index:
                buf += self.get_item(i)

        self.clear_history()
        for s in buf:
            readline.add_history(s)

    def clear_history(self):
        try:
            readline.clear_history()
        except AttributeError:
            len = self.get_max_length()
            readline.set_history_length(0)
            readline.set_history_length(len)

    def get_max_length(self):
        return readline.get_history_length()

    def set_max_length(self, n):
        readline.set_history_length(n)

    def add_item(self, line, force=False):
        readline.add_history(line)

class PyReadlineHistory(ReadlineHistory):
    def __init__(self):
        global _have_pyreadline
        assert(_have_pyreadline)
        ReadlineHistory.__init__(self)

    def get_item(self, index):
        return self.__get_buf()[index - 1].get_line_text()

    def get_total(self):
        return len(self.__get_buf())

    def set_completer_delims(self, s):
        readline.set_completer_delims(s)

    def get_completer_delims(self):
        return readline.get_completer_delims()

    def remove_item(self, index):
        buf = copy.deepcopy(self.__get_buf())
        self.clear_history()
        for s in buf:
            readline.add_history(s)

    def clear_history(self):
        readline.clear_history()

    def get_max_length(self):
        return readline.get_history_length()

    def set_max_length(self, n):
        readline.set_history_length(n)

    def add_item(self, line, force=False):
        # Kludge. pyreadline is a pain in the ass.
        from pyreadline import lineobj
        from pyreadline.unicode_helper import ensure_unicode

        line = ensure_unicode(line.rstrip())
        readline.add_history(lineobj.ReadLineTextBuffer(line))

    def __get_buf(self):
        return readline.rl._history.history

class DummyHistory(History):

    def __init__(self):
        History.__init__(self)

    def remove_item(self, i):
        pass

    def get_item(self, index):
        return None

    def get_history_list(self):
        return []

    def get_total(self):
        return 0

    def get_max_length(self):
        return 0

    def set_max_length(self, n):
        pass

    def clear_history(self):
        pass

    def add_item(self, line, force=False):
        pass

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    h = getHistory()
