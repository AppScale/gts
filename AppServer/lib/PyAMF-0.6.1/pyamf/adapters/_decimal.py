# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Adapter for the U{decimal<http://docs.python.org/library/decimal.html>} module.

@since: 0.4
"""

import decimal

import pyamf


def convert_Decimal(x, encoder):
    """
    Called when an instance of U{decimal.Decimal<http://
    docs.python.org/library/decimal.html#decimal-objects>} is about to be
    encoded to an AMF stream.

    @return: If the encoder is in 'strict' mode then C{x} will be converted to
        a float. Otherwise an L{pyamf.EncodeError} with a friendly message is
        raised.
    """
    if encoder.strict is False:
        return float(x)

    raise pyamf.EncodeError('Unable to encode decimal.Decimal instances as '
        'there is no way to guarantee exact conversion. Use strict=False to '
        'convert to a float.')


if hasattr(decimal, 'Decimal'):
    pyamf.add_type(decimal.Decimal, convert_Decimal)
