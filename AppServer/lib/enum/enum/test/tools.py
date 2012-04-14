# -*- coding: utf-8 -*-

# test/tools.py
# Part of enum, a package providing enumerated types for Python.
#
# Copyright © 2007–2009 Ben Finney <ben+python@benfinney.id.au>
# This is free software; you may copy, modify and/or distribute this work
# under the terms of the GNU General Public License, version 2 or later
# or, at your option, the terms of the Python license.

""" Helper tools for unit tests.
    """

import os.path
import sys

test_dir = os.path.dirname(os.path.abspath(__file__))
code_dir = os.path.dirname(test_dir)
if not test_dir in sys.path:
    sys.path.insert(1, test_dir)
if not code_dir in sys.path:
    sys.path.insert(1, code_dir)


# Local variables:
# mode: python
# End:
# vim: filetype=python fileencoding=utf-8 :
