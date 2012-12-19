import simplejson as S

def test_encoding1():
    encoder = S.JSONEncoder(encoding='utf-8')
    u = u'\N{GREEK SMALL LETTER ALPHA}\N{GREEK CAPITAL LETTER OMEGA}'
    s = u.encode('utf-8')
    ju = encoder.encode(u)
    js = encoder.encode(s)
    assert ju == js
    
def test_encoding2():
    u = u'\N{GREEK SMALL LETTER ALPHA}\N{GREEK CAPITAL LETTER OMEGA}'
    s = u.encode('utf-8')
    ju = S.dumps(u, encoding='utf-8')
    js = S.dumps(s, encoding='utf-8')
    assert ju == js

def test_big_unicode_encode():
    u = u'\U0001d120'
    assert S.dumps(u) == '"\\ud834\\udd20"'
    assert S.dumps(u, ensure_ascii=False) == '"\\ud834\\udd20"'

def test_big_unicode_decode():
    u = u'z\U0001d120x'
    assert S.loads('"' + u + '"') == u
    assert S.loads('"z\\ud834\\udd20x"') == u

def test_unicode_decode():
    for i in range(0, 0xd7ff):
        u = unichr(i)
        json = '"\\u%04x"' % (i,)
        res = S.loads(json)
        assert res == u, 'S.loads(%r) != %r got %r' % (json, u, res)

if __name__ == '__main__':
    test_unicode_decode()
