import simplejson
def test_default():
    assert simplejson.dumps(type, default=repr) == simplejson.dumps(repr(type))
