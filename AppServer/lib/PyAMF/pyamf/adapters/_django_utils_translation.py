# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
C{django.utils.translation} adapter module.

@see: U{Django Project<http://www.djangoproject.com>}
@since: 0.4.2
"""

from django.utils.translation import ugettext_lazy

import pyamf


def convert_lazy(l, encoder=None):
    if l.__class__._delegate_unicode:
        return unicode(l)

    if l.__class__._delegate_str:
        return str(l)

    raise ValueError('Don\'t know how to convert lazy value %s' % (repr(l),))


pyamf.add_type(type(ugettext_lazy('foo')), convert_lazy)
