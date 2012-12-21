import logging

from testproject.lib import helpers as h

log = logging.getLogger(__name__)

def echo(data):
    """
    This is a function that we will expose.
    """
    # print data to the console
    log.debug('Echo: %s', data)
    # echo data back to the client
    return data

services = {
    'myservice.echo': echo,
    # Add other exposed functions and classes here
}

GatewayController = h.WSGIGateway(services, logger=log, debug=True)