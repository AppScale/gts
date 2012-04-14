
from contextlib import contextmanager

@contextmanager
def exception_expected(exception_class):
    got_it = False
    try:
        yield
    except exception_class:
        got_it = True
    finally:
        if not got_it:
            assert False, 'Expected, but did not get, %s' % exception_class
