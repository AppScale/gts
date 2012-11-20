import sys, time
from threading import Thread
from memcache_mutex import *

NUMBER_OF_THREADS=30
TIMES_TO_INCREMENT=5
COUNTER_KEY="counter"

# Should be set to the ip:port of the memcache server to use
MEMCACHE_LOCATION=None

class Incrementer(Thread):
    def __init__(self, id):
        self.id = id
        self.memcache = memcache.Client([MEMCACHE_LOCATION], debug=0)
        Thread.__init__(self)

    def run(self):
        """
        Increments a counter under lock to ensure that no updates are lost. I'm intentionally
        not using the incr method in order to increase the likleyhood that updates would be lost
        if the mutex didn't work correctly.
        """
        for i in range(TIMES_TO_INCREMENT):
            lock = MemcacheMutex("lock", self.memcache)
            lock.acquire()
            value = self.memcache.get(COUNTER_KEY) or 0
            value += 1
            self.memcache.set(COUNTER_KEY, value)
            lock.release()

def main(args):
    if MEMCACHE_LOCATION is None:
        print "MEMCACHE_LOCATION needs to be set in order for this test to work!"
        sys.exit(1)

    mc = memcache.Client([MEMCACHE_LOCATION], debug=0)
    # Flush any old data to ensure we are working with a clean slate
    mc.flush_all()

    threads = []
    for i in range(NUMBER_OF_THREADS):
        t = Incrementer(i)
        threads.append(t)

    for thread in threads:
        thread.start()


    for thread in threads:
        thread.join()

    final_value = mc.get(COUNTER_KEY)

    # If the mutex worked correctly then no updates should be trampled and
    # the final value should be the same as the number of increments that happened
    # times the number of threads
    assert final_value == (NUMBER_OF_THREADS*TIMES_TO_INCREMENT)

    print "MemcacheMutex worked correctly!"


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
