import logging

from pyamf.remoting.gateway.wsgi import WSGIGateway
from pyamf.remoting.gateway import expose_request

from twisted.web import server
from twisted.web.wsgi import WSGIResource
from twisted.python.threadpool import ThreadPool
from twisted.internet import reactor
from twisted.application import service, strports

        
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s'
)


class example:
    """
    An example class that can be used as a PyAMF service.
    """
    def test1(self, n):
        return "Test 1 Success!"

    @expose_request
    def testn(self, request, n):
        """
        This function is decorated to expose the underlying HTTP request,
        which provides access to things such as the requesting client's IP.
        """
        ip = request['REMOTE_ADDR']

        return "%s said %s!" % (ip, n)


# A standalone function that can be bound to a service.
def add(a, b): 
    return a + b 


# Create a dictionary mapping the service namespaces to a function
# or class instance
services = { 
    'example': example(),
    'myadd': add 
}

# Create and start a thread pool,
wsgiThreadPool = ThreadPool()
wsgiThreadPool.start()

# ensuring that it will be stopped when the reactor shuts down
reactor.addSystemEventTrigger('after', 'shutdown', wsgiThreadPool.stop)

# PyAMF gateway
gateway = WSGIGateway(services, logger=logging, expose_request=False,
                      debug=True)

# Create the WSGI resource
wsgiAppAsResource = WSGIResource(reactor, wsgiThreadPool, gateway)
site = server.Site(wsgiAppAsResource)
server = strports.service('tcp:8080', site)

# Hooks for twistd
application = service.Application('PyAMF Sample Remoting Server')
server.setServiceParent(application)