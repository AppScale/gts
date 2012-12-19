# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.


"""
Local Shared Object example.

@see: U{http://pyamf.org/wiki/LocalSharedObjectHowto}
"""


import os
import logging

from pyamf.remoting.gateway.wsgi import WSGIGateway

import service


# get platform specific shared object folder
path = service.default_folder()
filetype = "*.sol"

services = {
    'lso': service.SharedObjectService(path, filetype)
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s'
)

application = WSGIGateway(services, logger=logging)


if __name__ == '__main__':
    from optparse import OptionParser
    from wsgiref import simple_server

    
    parser = OptionParser()
    parser.add_option("-p", "--port", default=8000,
        dest="port", help="port number [default: %default]")
    parser.add_option("--host", default="localhost",
        dest="host", help="host address [default: %default]")
    (options, args) = parser.parse_args()

    port = int(options.port)

    httpd = simple_server.WSGIServer(
        (options.host, port),
        simple_server.WSGIRequestHandler,
    )
    
    
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

        return application(environ, start_response)

    httpd.set_app(app)

    print "Running AMF gateway on http://%s:%d" % (options.host, port)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass

