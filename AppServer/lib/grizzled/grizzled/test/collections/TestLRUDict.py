#!/usr/bin/python2.4
# $Id: d013d05ce2f81cd44ec98b5568c26fef11333e0e $

"""
Tester.
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

from timeit import Timer

import google3
from grizzled.collections import LRUDict

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class TestLRUDict(object):

    def test1(self):
        lru = LRUDict(max_capacity=5)

        print "Adding 'a' and 'b'"
        lru['a'] = 'A'
        lru['b'] = 'b'
        print lru
        print lru.keys()
        assert lru.keys() == ['b', 'a']
        assert lru.values() == ['b', 'A']

        print "Adding 'c'"
        lru['c'] = 'c'
        print lru
        print lru.keys()
        assert lru.keys() == ['c', 'b', 'a']

        print "Updating 'a'"
        lru['a'] = 'a'
        print lru
        print lru.keys()
        assert lru.keys() == ['a', 'c', 'b']

        print "Adding 'd' and 'e'"
        lru['d'] = 'd'
        lru['e'] = 'e'
        print lru
        print lru.keys()
        assert lru.keys() == ['e', 'd', 'a', 'c', 'b']

        print "Accessing 'b'"
        assert lru['b'] == 'b'
        print lru
        print lru.keys()
        assert lru.keys() == ['b', 'e', 'd', 'a', 'c']

        print "Adding 'f'"
        lru['f'] = 'f'
        # Should knock 'c' out of the list
        print lru
        print lru.keys()
        assert lru.keys() == ['f', 'b', 'e', 'd', 'a']

        def on_remove(key, value, the_list):
            print 'on_remove("%s")' % key
            the_list.append(key)

        print 'Reducing capacity. Should result in eviction.'
        ejected = []
        lru.add_ejection_listener(on_remove, ejected)
        lru.max_capacity = 3
        ejected.sort()
        print 'ejected=%s' % ejected
        assert ejected == ['a', 'd']
        print lru.keys()
        assert lru.keys() == ['f', 'b', 'e']

        print 'Testing popitem()'
        key, value = lru.popitem()
        print lru
        print lru.keys()
        assert key == 'e'
        assert lru.keys() == ['f', 'b']

        print 'Clearing dictionary'
        lru.clear_listeners()
        lru.clear()
        del lru

    def add_one(self, lru, key):
        lru[key] = key

    def testBig(self):
        print 'Putting 10000 entries in a new LRU cache'
        lru = LRUDict(max_capacity=10000)
        for i in range(0, lru.max_capacity):
            lru[i] = i

        assert len(lru) == lru.max_capacity
        print 'Adding one more'
        assert len(lru) == lru.max_capacity
        print iter(lru).next()
