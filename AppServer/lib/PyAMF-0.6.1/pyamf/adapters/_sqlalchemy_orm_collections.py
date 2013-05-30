# Copyright (c) The PyAMF Project.
# See LICENSE for details.

"""
SQLAlchemy adapter module.

@see: U{SQLAlchemy homepage<http://www.sqlalchemy.org>}

@since: 0.4
"""

from sqlalchemy.orm import collections

import pyamf
from pyamf.adapters import util


pyamf.add_type(collections.InstrumentedList, util.to_list)
pyamf.add_type(collections.InstrumentedDict, util.to_dict)
pyamf.add_type(collections.InstrumentedSet, util.to_set)
