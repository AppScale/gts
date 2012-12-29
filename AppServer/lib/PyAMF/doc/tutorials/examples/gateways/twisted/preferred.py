from twisted.web import resource, server
from twisted.application import service, strports

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
    def test1(self, n):
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

# Ideally, just the imports and the code below this comment would be
# in the .tac file; the AMF service would be defined in a module of
# your making

# Place the namespace mapping into a TwistedGateway
gateway = TwistedGateway(services, logger=logging, expose_request=False,
                         debug=True)

# A base root resource for the twisted.web server
root = resource.Resource()

# Publish the PyAMF gateway at the root URL
root.putChild('', gateway)

print 'Running AMF gateway on http://localhost:8080'

application = service.Application('PyAMF Sample Remoting Server')
server = strports.service('tcp:8080', server.Site(root))
server.setServiceParent(application)