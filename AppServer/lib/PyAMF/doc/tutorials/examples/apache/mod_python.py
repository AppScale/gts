from pyamf.remoting.gateway.wsgi import WSGIGateway

import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s'
)


def echo(data):
   return data

services = {
   'echo': echo,
   # Add other exposed functions here
}

application = WSGIGateway(services, logger=logging, debug=True)
