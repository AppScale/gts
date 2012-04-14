#!/usr/bin/env python
# ---------------------------------------------------------------------------

"""
Provides a front-end to the Python standard ``optparse`` module. The
``CommandLineParser`` class makes two changes to the standard behavior.

  - The output for the '-h' option is slightly different.
  - A bad option causes the parser to generate the entire usage output,
    not just an error message.

It also provides a couple extra utility modules.
"""

__docformat__ = "restructuredtext en"

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

from optparse import OptionParser
import sys

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = ['CommandLineParser']

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class CommandLineParser(OptionParser):
    """Custom version of command line option parser."""

    def __init__(self, *args, **kw):
        """ Create a new instance. """

        OptionParser.__init__(self, *args, **kw)

        # I like my help option message better than the default...

        self.remove_option('-h')
        self.add_option('-h', '--help', action='help',
                        help='Show this message and exit.')
        
        self.epilogue = None

    def print_help(self, out=sys.stderr):
        """
        Print the help message, followed by the epilogue (if set), to the
        specified output file. You can define an epilogue by setting the
        ``epilogue`` field.
        
        :Parameters:
            out : file
                where to write the usage message
        """
        OptionParser.print_help(self, out)
        if self.epilogue:
            import textwrap
            print >> out, '\n%s' % textwrap.fill(self.epilogue, 80)
            out.flush()

    def die_with_usage(self, msg=None, exit_code=2):
        """
        Display a usage message and exit.

        :Parameters:
            msg : str
                If not set to ``None`` (the default), this message will be
                displayed before the usage message
                
            exit_code : int
                The process exit code. Defaults to 2.
        """
        if msg != None:
            print >> sys.stderr, msg
        self.print_help(sys.stderr)
        sys.exit(exit_code)

    def error(self, msg):
        """
        Overrides parent ``OptionParser`` class's ``error()`` method and
        forces the full usage message on error.
        """
        sys.stderr.write("%s: error: %s\n" % (self.get_prog_name(), msg))
        self.die_with_usage(msg)
