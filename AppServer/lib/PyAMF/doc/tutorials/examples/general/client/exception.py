>>> from pyamf.remoting.client import RemotingService
>>> gateway = RemotingService('http://example.org/gw')
>>> service = gateway.getService('type_error')
>>> service()
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "/Users/nick/projects/pyamf/pyamf/remoting/client/__init__.py", line 121, in __call__
    return self._call(ServiceMethodProxy(self, None), *args)
  File "/Users/nick/projects/pyamf/pyamf/remoting/client/__init__.py", line 107, in _call
    response.body.raiseException()
  File "/Users/nick/projects/pyamf/pyamf/remoting/__init__.py", line 335, in raiseException
    raise get_exception_from_fault(self), self.description, None
TypeError: some useful message here
