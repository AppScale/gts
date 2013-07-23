# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Adapter for the stdlib C{sets} module.

@since: 0.4
"""

import sets

import pyamf
from pyamf.adapters import util


if hasattr(sets, 'ImmutableSet'):
    pyamf.add_type(sets.ImmutableSet, util.to_tuple)

if hasattr(sets, 'Set'):
    pyamf.add_type(sets.Set, util.to_tuple)
