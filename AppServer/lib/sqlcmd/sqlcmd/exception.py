#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# $Id: 855bc891d87aa28cce823a56c76b6f9e89f23e6d $

"""
Exceptions used by *sqlcmd*.

COPYRIGHT AND LICENSE

Copyright © 2008 Brian M. Clapper

This is free software, released under the following BSD-like license:

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.

2. The end-user documentation included with the redistribution, if any,
   must include the following acknowlegement:

      This product includes software developed by Brian M. Clapper
      (bmc@clapper.org, http://www.clapper.org/bmc/). That software is
      copyright © 2008 Brian M. Clapper.

    Alternately, this acknowlegement may appear in the software itself, if
    and wherever such third-party acknowlegements normally appear.

THIS SOFTWARE IS PROVIDED ``AS IS'' AND ANY EXPRESSED OR IMPLIED
WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO
EVENT SHALL BRIAN M. CLAPPER BE LIABLE FOR ANY DIRECT, INDIRECT,
INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

$Id: 855bc891d87aa28cce823a56c76b6f9e89f23e6d $
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

class NonFatalError(Exception):
    """
    Exception indicating a non-fatal error. Intended to be a base class.
    Non-fatal errors are trapped and displayed as error messages within the
    command interpreter.
    """
    def __init__(self, value):
        self.message = value

    def __str__(self):
        return str(self.message)

class ConfigurationError(NonFatalError):
    """Thrown when bad configuration data is found."""
    def __init__(self, value):
        NonFatalError.__init__(self, value)

class NotConnectedError(NonFatalError):
    """
    Thrown to indicate that a SQL operation is attempted when there's no
    active connection to a database.
    """
    def __init__(self, value):
        NonFatalError.__init__(self, value)

class BadCommandError(NonFatalError):
    """Thrown to indicate bad input from the user."""
    def __init__(self, value):
        NonFatalError.__init__(self, value)
