# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Django query adapter module.

Sets up basic type mapping and class mappings for a
Django models.

@see: U{Django Project<http://www.djangoproject.com>}
@since: 0.1b
"""

from django.db.models import query

import pyamf
from pyamf.adapters import util


pyamf.add_type(query.QuerySet, util.to_list)
