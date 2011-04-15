import memcache
import time

class MemcacheMutex:
    def __init__(self, name, memcache):
        """ 
        MemcacheMutex provides a distributed mutex using memcache
        Parameters:
        name - The name of the mutex such that multiple mutexes can be created
        memcache - A connected memcache client
        """
        self.name = name
        # Keep track of if we have to lock to ensure
        # that if lock/unlock is called multiple times it doesn't break anything
        self.have_lock = False
        self.memcache = memcache

    def acquire(self):
        if self.have_lock:
            return True
        # Keep trying to add the key to memcache
        # Add returns false if the key is already in memcache
        # Add is our test-and-set operation
        while not self.memcache.add(self.key(), 1):
            # We didn't get the lock, keep trying till we do
            time.sleep(0.1)
        self.have_lock = True
        return True

    def release(self):
        if self.have_lock:
            self.memcache.delete(self.key())
            self.have_lock = False

    def key(self):
        return "LOCK-%s" % (self.name)

    def __del__(self):
        self.release()
