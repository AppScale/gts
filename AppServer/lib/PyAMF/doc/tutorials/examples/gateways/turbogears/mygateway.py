import logging

from pyamf.remoting.gateway.wsgi import WSGIGateway


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s'
)


class Services(object):

    def echo(self, data):
        return "Turbogears gateway says:" + str(data)

    def sum(self, a, b):
        return a + b

    def scramble(self, text):
        from random import shuffle
        s = [x for x in text]
        shuffle(s)
        return ''.join(s)


# Expose our services
services = {"Services" : Services()}

GatewayController = WSGIGateway(services, logger=logging, debug=True)