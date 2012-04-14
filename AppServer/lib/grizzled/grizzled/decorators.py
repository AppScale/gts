"""
This module contains various Python decorators.
"""

__docformat__ = "restructuredtext en"

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = ['deprecated', 'abstract']

# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def deprecated(since=None, message=None):
    """
    Decorator for marking a function deprecated. Generates a warning on
    standard output if the function is called.

    Usage:
    
    .. python::

        from grizzled.decorators import deprecated

        class MyClass(object):

            @deprecated()
            def oldMethod(self):
                pass

    Given the above declaration, the following code will cause a
    warning to be printed (though the method call will otherwise succeed):
    
    .. python::

        obj = MyClass()
        obj.oldMethod()

    You may also specify a ``since`` argument, used to display a deprecation
    message with a version stamp (e.g., 'deprecated since ...'):
    
    .. python::

        from grizzled.decorators import deprecated

        class MyClass(object):

            @deprecated(since='1.2')
            def oldMethod(self):
                pass

    :Parameters:
        since : str
            version stamp, or ``None`` for none
        message : str
            optional additional message to print
    """
    def decorator(func):
        if since is None:
            buf = 'Method %s is deprecated.' % func.__name__
        else:
            buf = 'Method %s has been deprecated since version %s.' %\
                  (func.__name__, since)

        if message:
            buf += ' ' + message

        def wrapper(*__args, **__kw):
            import warnings
            warnings.warn(buf, category=DeprecationWarning, stacklevel=2)
            return func(*__args,**__kw)

        wrapper.__name__ = func.__name__
        wrapper.__dict__ = func.__dict__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator

def abstract(func):
    """
    Decorator for marking a method abstract. Throws a ``NotImplementedError``
    if an abstract method is called.

    Usage:
    
    .. python::

        from grizzled.decorators import abstract

        class MyAbstractClass(object):

            @abstract
            def abstractMethod(self):
                pass

        class NotReallyConcrete(MyAbstractClass):
            # Class doesn't define abstractMethod().

    Given the above declaration, the following code will cause an
    ``NotImplementedError``:
    
    .. python::

        obj = NotReallyConcrete()
        obj.abstractMethod()
    """
    def wrapper(*__args, **__kw):
        raise NotImplementedError('Missing required %s() method' %\
                                  func.__name__)
    wrapper.__name__ = func.__name__
    wrapper.__dict__ = func.__dict__
    wrapper.__doc__ = func.__doc__
    return wrapper

def unimplemented(func):
    """
    Decorator for marking a function or method unimplemented. Throws a
    ``NotImplementedError`` if called. Note that this decorator is
    conceptually different from ``@abstract``. With ``@abstract``, the method
    is intended to be implemented by a subclass. With ``@unimplemented``, the
    method should never be implemented.

    Usage:
    
    .. python::

        from grizzled.decorators import unimplemented

        class ReadOnlyDict(dict):

            @unimplemented
            def __setitem__(self, key, value):
                pass
    """
    def wrapper(*__args, **__kw):
        raise NotImplementedError('Method or function "%s" is not implemented',
                                  func.__name__)
    wrapper.__name__ = func.__name__
    wrapper.__dict__ = func.__dict__
    wrapper.__doc__ = func.__doc__
    return wrapper


# ---------------------------------------------------------------------------
# Main program, for testing
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    @deprecated()
    def func1(a):
        pass

    @deprecated(since='1.2')
    def func2():
        pass

    func1(100)
    func2()

    class Foo(object):
        @abstract
        def foo(self):
            pass

    class Bar(Foo):
        pass

    b = Bar()
    try:
        b.foo()
        assert False
    except NotImplementedError, ex:
        print ex.message
