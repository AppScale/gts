
"""
``grizzled.collections.dict`` contains some useful dictionary classes
that extend the behavior of the built-in Python ``dict`` type.
"""
__docformat__ = "restructuredtext en"

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import sys

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = ['OrderedDict', 'LRUDict']

# ---------------------------------------------------------------------------
# Public Classes
# ---------------------------------------------------------------------------

                         ##############################                         
                         # OrderedDict implementation #                         
                         ##############################                         

class OrderedDict(dict):
    """
    ``OrderedDict`` is a simple ordered dictionary. The ``keys()``,
    ``items()``, ``__iter__()``, and other methods all return the keys in the
    order they were added to the dictionary. Note that re-adding a key (i.e.,
    replacing a key with a new value) does not change the original order.

    An ``OrderedDict`` object is instantiated with exactly the same parameters
    as a ``dict`` object. The methods it provides are identical to those in
    the ``dict`` type and are not documented here.
    """
    def __init__(self, *args, **kw):
        dict.__init__(self, *args, **kw)
        self.__orderedKeys = []
        self.__keyPositions = {}

    def __setitem__(self, key, value):
        try:
            index = self.__keyPositions[key]
        except KeyError:
            index = len(self.__orderedKeys)
            self.__orderedKeys += [key]
            self.__keyPositions[key] = index

        dict.__setitem__(self, key, value)

    def __delitem__(self, key):
        index = self.__keyPositions[key]
        del self.__orderedKeys[index]
        del self.__keyPositions[key]
        dict.__delitem__(self, key)

    def __iter__(self):
        for key in self.__orderedKeys:
            yield key

    def __str__(self):
        s = '{'
        sep = ''
        for k, v in self.iteritems():
            s += sep
            if type(k) == str:
                s += "'%s'" % k
            else:
                s += str(k)

            s += ': '
            if type(v) == str:
                s += "'%s'" % v
            else:
                s += str(v)
            sep = ', '
        s += '}'
        return s

    def keys(self):
        return self.__orderedKeys

    def items(self):
        return [(key, self[key]) for key in self.__orderedKeys]

    def values(self):
        return [self[key] for key in self.__orderedKeys]

    def iteritems(self):
        for key in self.__orderedKeys:
            yield (key, self[key])

    def iterkeys(self):
        for key in self.__orderedKeys:
            yield key

    def update(self, d):
        for key, value in d.iteritems():
            self[key] = value

    def pop(self, key, default=None):
        try:
            result = self[key]
            del self[key]

        except KeyError:
            if not default:
                raise

            result = default

        return result

    def popitem(self):
        key, value = dict.popitem(self)
        del self[key]
        return (key, value)

                           ##########################                           
                           # LRUDict Implementation #                           
                           ##########################                           

# Implementation note:
#
# Each entry in the LRUDict dictionary is an LRUListEntry. Basically,
# we maintain two structures:
#
# 1. A linked list of dictionary entries, in order of recency.
# 2. A dictionary of those linked list items.
#
# When accessing or updating an entry in the dictionary, the logic
# is more or less like the following "get" scenario:
#
# - Using the key, get the LRUListEntry from the dictionary.
# - Extract the value from the LRUListEntry, to return to the caller.
# - Move the LRUListEntry to the front of the recency queue.

class LRUListEntry(object):

    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.next = None
        self.prev = None

    def __hash__(self):
        return self.key.__hash__()
    
    def __str__(self):
        return '(%s, %s)' % (self.key, self.value)

    def __repr__(self):
        return str(self)

class LRUList(object):

    def __init__(self):
        self.head = self.tail = None
        self.size = 0

    def __del__(self):
        self.clear()

    def __str__(self):
        return '[' + ', '.join([str(tup) for tup in self.items()]) + ']'
    
    def __repr__(self):
        return self.__class__.__name__ + ':' + str(self)

    def __len__(self):
        return self.size

    def __iter__(self):
        entry = self.head
        while entry:
            yield entry.key
            entry = entry.next

    def keys(self):
        return [k for k in self]

    def items(self):
        result = []
        for key, value in self.iteritems():
            result.append((key, value))
        return result

    def values(self):
        result = []
        for key, value in self.iteritems():
            result.append(value)
        return result

    def iteritems(self):
        entry = self.head
        while entry:
            yield (entry.key, entry.value)
            entry = entry.next

    def iterkeys(self):
        self.__iter__()

    def itervalues(self):
        entry = self.head
        while entry:
            yield entry.value
            entry = entry.next

    def clear(self):
        while self.head:
            cur = self.head
            next = self.head.next
            cur.next = cur.previous = cur.key = cur.value = None
            self.head = next

        self.tail = None
        self.size = 0

    def remove(self, entry):
        if entry.next:
            entry.next.previous = entry.previous

        if entry.previous:
            entry.previous.next = entry.next

        if entry == self.head:
            self.head = entry.next

        if entry == self.tail:
            self.tail = entry.previous

        entry.next = entry.previous = None
        self.size -= 1
        assert self.size >= 0

    def remove_tail(self):
        result = self.tail

        if result:
            self.remove(result)

        return result

    def add_to_head(self, entry):
        if type(entry) == tuple:
            key, value = entry
            entry = LRUListEntry(key, value)
        else:
            entry.next = entry.previous = None

        if self.head:
            assert self.tail
            entry.next = self.head
            self.head.previous = entry
            self.head = entry

        else:
            assert not self.tail
            self.head = self.tail = entry

        self.size += 1

    def move_to_head(self, entry):
        self.remove(entry)
        self.add_to_head(entry)

class LRUDict(dict):
    """
    ``LRUDict`` is a dictionary of a fixed maximum size that enforces a least
    recently used discard policy. When the dictionary is full (i.e., contains
    the maximum number of entries), any attempt to insert a new entry causes
    one of the least recently used entries to be discarded.

    **Note**:

    - Setting or updating a key in the dictionary refreshes the corresponding
      value, making it "new" again, even if it replaces the existing value with
      itself.
    - Retrieving a value from the dictionary also refreshes the entry.
    - Iterating over the contents of the dictionary (via ``in`` or ``items()``
      or any other similar method) does *not* affect the recency of the
      dictionary's contents.
    - This implementation is *not* thread-safe.

    An ``LRUDict`` also supports the concept of *removal listeners*. Removal
    listeners are functions that are notified when objects are removed from
    the dictionary. Removal listeners can be:

    - *eject only* listeners, meaning they're only notified when objects are
      ejected from the cache to make room for new objects, or
    - *removal* listeners, meaning they're notified whenever an object is
      removed for *any* reason, including via ``del``.

    This implementation is based on a Java ``LRUMap`` class in the
    ``org.clapper.util`` library. See http://software.clapper.org/java/util/
    for details.
    """
    def __init__(self, *args, **kw):
        """
        Initialize an ``LRUDict`` that will hold, at most, ``max_capacity``
        items. Attempts to insert more than ``max_capacity`` items in the
        dictionary will cause the least-recently used entries to drop out of
        the dictionary.

        :Keywords:
            max_capacity : int
                The maximum size of the dictionary
        """
        if kw.has_key('max_capacity'):
            self.__max_capacity = kw['max_capacity']
            del kw['max_capacity']
        else:
            self.__max_capacity = sys.maxint
            
        dict.__init__(self)
        self.__removal_listeners = {}
        self.__lru_queue = LRUList()
        
    def __del__(self):
        self.clear()

    def get_max_capacity(self):
        """
        Get the maximum capacity of the dictionary.
        
        :rtype: int
        :return: the maximum capacity
        """
        return self.__max_capacity

    def set_max_capacity(self, new_capacity):
        """
        Set or change the maximum capacity of the dictionary. Reducing
        the size of a dictionary with items already in it might result
        in items being evicted.
        
        :Parameters:
            new_capacity : int
                the new maximum capacity
        """
        self.__max_capacity = new_capacity
        if len(self) > new_capacity:
            self.__clear_to(new_capacity)

    max_capacity = property(get_max_capacity, set_max_capacity,
                            doc='The maximum capacity. Can be reset at will.')

    def add_ejection_listener(self, listener, *args):
        """
        Add an ejection listener to the dictionary. The listener function
        should take at least two parameters: the key and value being removed.
        It can also take additional parameters, which are passed through
        unmodified.

        An ejection listener is only notified when objects are ejected from
        the cache to make room for new objects; more to the point, an ejection
        listener is never notified when an object is removed from the cache
        manually, via use of the ``del`` operator.

        :Parameters:
            listener : function
                Function to invoke

            args : iterable
                Any additional parameters to pass to the function
        """
        self.__removal_listeners[listener] = (True, args)

    def add_removal_listener(self, listener, *args):
        """
        Add a removal listener to the dictionary. The listener function should
        take at least two parameters: the key and value being removed. It can
        also take additional parameters, which are passed through unmodified.

        A removal listener is notified when objects are ejected from the cache
        to make room for new objects *and* when objects are manually deleted
        from the cache.

        :Parameters:
            listener : function
                Function to invoke

            args : iterable
                Any additional parameters to pass to the function
        """
        self.__removal_listeners[listener] = (False, args)

    def remove_listener(self, listener):
        """
        Remove the specified removal or ejection listener from the list of
        listeners.

        :Parameters:
            listener : function
                Function object to remove

        :rtype: bool
        :return: ``True`` if the listener was found and removed; ``False``
                 otherwise
        """
        try:
            del self.__removal_listeners[listener]
            return True
        except KeyError:
            return False
        
    def clear_listeners(self):
        """
        Clear all removal and ejection listeners from the list of listeners.
        """
        for key in self.__removal_listeners.keys():
            del self.__removal_listeners[key]

    def __setitem__(self, key, value):
        self.__put(key, value)
        
    def __getitem__(self, key):
        lru_entry = dict.__getitem__(self, key)
        self.__lru_queue.move_to_head(lru_entry)
        return lru_entry.value

    def __delitem__(self, key):
        lru_entry = dict.__getitem__(self, key)
        self.__lru_queue.remove(lru_entry)
        dict.__delitem__(self, key)
        self.__notify_listeners(False, [(lru_entry.key, lru_entry.value)])

    def __str__(self):
        s = '{'
        sep = ''
        for k, v in self.iteritems():
            s += sep
            if type(k) == str:
                s += "'%s'" % k
            else:
                s += str(k)

            s += ': '
            if type(v) == str:
                s += "'%s'" % v
            else:
                s += str(v)
            sep = ', '
        s += '}'
        return s

    def __iter__(self):
        return self.__lru_queue.__iter__()

    def clear(self):
        self.__clear_to(0)

    def get(self, key, default=None):
        try:
            lru_entry = self.__getitem__(key)
            value = lru_entry.value
        except KeyError:
            value = default
        return value

    def keys(self):
        return self.__lru_queue.keys()

    def items(self):
        return self.__lru_queue.items()

    def values(self):
        return self.__lru_queue.values()

    def iteritems(self):
        return self.__lru_queue.iteritems()

    def iterkeys(self):
        return self.__lru_queue.iterkeys()

    def itervalues(self):
        return self.__lru_queue.itervalues()

    def update(self, d):
        for key, value in d.iteritems():
            self[key] = value

    def pop(self, key, default=None):
        try:
            result = self[key]
            del self[key]

        except KeyError:
            if not default:
                raise

            result = default

        return result

    def popitem(self):
        """
        Pops the least recently used recent key/value pair from the
        dictionary.
        
        :rtype: tuple
        :return: the least recent key/value pair, as a tuple
        
        :raise KeyError: empty dictionary
        """
        if len(self) == 0:
            raise KeyError, 'Attempted popitem() on empty dictionary'

        lru_entry = self.__lru_queue.remove_tail()
        dict.__delitem__(self, lru_entry.key)
        return lru_entry.key, lru_entry.value

    def __put(self, key, value):
        try:
            lru_entry = dict.__getitem__(self, key)

            # Replacing an existing value with a new one. Move the entry
            # to the head of the list.

            lru_entry.value = value
            self.__lru_queue.move_to_head(lru_entry)

        except KeyError:
            # Not there. Have to add a new one. Clear out the cruft first.
            # Preserve one of the entries we're clearing, to avoid
            # reallocation.

            lru_entry = self.__clear_to(self.max_capacity - 1)
            if lru_entry:
                lru_entry.key, lru_entry.value = key, value
            else:
                lru_entry = LRUListEntry(key, value)
            self.__lru_queue.add_to_head(lru_entry)

        dict.__setitem__(self, key, lru_entry)

    def __clear_to(self, size):
        old_tail = None
        while len(self.__lru_queue) > size:
            old_tail = self.__lru_queue.remove_tail()
            assert old_tail
            key = old_tail.key
            value = dict.__delitem__(self, key)
            self.__notify_listeners(True, [(key, value)])

        assert len(self.__lru_queue) <= size
        assert len(self) == len(self.__lru_queue)
        return old_tail

    def __notify_listeners(self, ejecting, key_value_pairs):
        if self.__removal_listeners:
            for key, value in key_value_pairs:
                for func, func_data in self.__removal_listeners.items():
                    on_eject_only, args = func_data
                    if (not on_eject_only) or ejecting:
                        func(key, value, *args)
