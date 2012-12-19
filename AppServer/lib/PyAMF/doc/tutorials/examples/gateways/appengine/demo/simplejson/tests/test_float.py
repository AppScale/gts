import simplejson
import math

def test_floats():
    for num in [1617161771.7650001, math.pi, math.pi**100, math.pi**-100]:
        assert float(simplejson.dumps(num)) == num
