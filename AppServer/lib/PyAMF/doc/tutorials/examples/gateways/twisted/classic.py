from twisted.internet import reactor, defer
from twisted.web import server, static, resource

from pyamf.remoting.gateway.twisted import TwistedGateway
from pyamf.remoting.gateway import expose_request

import logging
        
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s'
)

class example:
    """
    An example class that can be used as a PyAMF service.
    """
    def test1(self):
        return "Test 1 Success!"
    
    @expose_request
    def testn(self, request, n):
        """
        This function is decorated to expose the underlying HTTP request,
        which provides access to things such as the requesting client's IP.
        """
        ip = request.getClientIP()

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

# Place the namespace mapping into a TwistedGateway
gateway = TwistedGateway(services, logger=logging, expose_request=False,
                         debug=True)

# A base root resource for the twisted.web server
root = resource.Resource()

# Publish the PyAMF gateway at the root URL
root.putChild('', gateway)

# Start the twisted reactor and listen on HTTP port 8080
print 'Running AMF gateway on http://localhost:8080'

reactor.listenTCP(8080, server.Site(root))
reactor.run()