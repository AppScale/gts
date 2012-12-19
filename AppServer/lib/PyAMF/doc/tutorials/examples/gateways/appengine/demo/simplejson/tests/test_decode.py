import simplejson as S
import decimal
def test_decimal():
    rval = S.loads('1.1', parse_float=decimal.Decimal)
    assert isinstance(rval, decimal.Decimal)
    assert rval == decimal.Decimal('1.1')

def test_float():
    rval = S.loads('1', parse_int=float)
    assert isinstance(rval, float)
    assert rval == 1.0
