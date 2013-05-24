# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
C{django.db.models.fields} adapter module.

@see: U{Django Project<http://www.djangoproject.com>}
@since: 0.4
"""

from django.db.models import fields

import pyamf


def convert_NOT_PROVIDED(x, encoder):
    """
    @rtype: L{Undefined<pyamf.Undefined>}
    """
    return pyamf.Undefined


pyamf.add_type(lambda x: x is fields.NOT_PROVIDED, convert_NOT_PROVIDED)
