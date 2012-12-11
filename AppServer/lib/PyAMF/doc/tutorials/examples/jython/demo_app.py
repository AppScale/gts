import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s'
)


def echo(data):
    return data


def handler(environ, start_response):
    from pyamf.remoting.gateway.wsgi import WSGIGateway

    services = {'my_service.echo': echo}
    gw = WSGIGateway(services, logger=logging, debug=True)

    return gw(environ, start_response)
