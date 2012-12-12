import logging

import cherrypy

from pyamf.remoting.gateway.wsgi import WSGIGateway

	
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s'
)


def echo(data):
   """
   This is a function that we will expose.
   """
   return data


class Root(object):
    """
    This is the root controller for the rest of the website.
    """
    def index(self):
        return "This is your main website"
    index.exposed = True


config = {
    '/crossdomain.xml': {
        'tools.staticfile.on': True,
        'tools.staticfile.filename': '/path/to/crossdomain.xml'
    }
}

services = {
   'myservice.echo': echo,
   # Add other exposed functions here
}

gateway = WSGIGateway(services, logger=logging, debug=True)

# This is where we hook in the WSGIGateway
cherrypy.tree.graft(gateway, "/gateway/")
cherrypy.quickstart(Root(), config=config)
