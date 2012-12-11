#!/usr/bin/env python
#
# Copyright (c) PyAMF Project.
# See LICENSE.txt for details.

"""
Simple WSGI server for SQLAlchemy Addressbook example.

@since: 0.4.1
"""


import pyamf
from pyamf import amf3

import persistent
import controller
import models

# Server defaults
port = 8000
host = 'localhost'

# Setup database
schema = persistent.Schema()
schema.createSchema()
schema.createMappers()

# Set this to True so that returned objects and arrays are bindable
amf3.use_proxies_default = True

# Map class aliases
# These same aliases must be registered in the Flash Player client
# with the registerClassAlias function.
namespace = 'org.pyamf.examples.addressbook.models'
pyamf.register_package(models, namespace)

# Map controller methods
sa_obj = controller.SAObject()
mapped_services = {
    'ExampleService': sa_obj
}


if __name__ == '__main__':
    import optparse
    import logging
    import os, sys

    from wsgiref import simple_server
    from pyamf.remoting.gateway.wsgi import WSGIGateway
	
    usage = """usage: %s [options]""" % os.path.basename(sys.argv[0])
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-p", "--port", default=port,
        dest="port", help="port number [default: %default]")
    parser.add_option("--host", default=host,
        dest="host", help="host address [default: %default]")
    (options, args) = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG,
           format='%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s')

    host = options.host
    port = int(options.port)

    # Start server
    print "Running SQLAlchemy AMF gateway on http://%s:%d" % (host, port)
    print "Press Ctrl-c to stop server."
	
    server = simple_server.WSGIServer((host, port),
                                simple_server.WSGIRequestHandler)
    gateway = WSGIGateway(mapped_services, logger=logging)
    
    def app(environ, start_response):
        if environ['PATH_INFO'] == '/crossdomain.xml':
            fn = os.path.join(os.getcwd(), os.path.dirname(__file__),
               'crossdomain.xml')

            fp = open(fn, 'rt')
            buffer = fp.readlines()
            fp.close()

            start_response('200 OK', [
                ('Content-Type', 'application/xml'),
                ('Content-Length', str(len(''.join(buffer))))
            ])

            return buffer

        return gateway(environ, start_response)
        
    server.set_app(app)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
