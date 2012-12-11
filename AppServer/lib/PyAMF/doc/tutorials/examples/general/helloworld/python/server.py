# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Hello world example server.

@see: U{HelloWorld<http://pyamf.org/tutorials/general/helloworld/index.html>} wiki page.

@since: 0.1.0
"""

def echo(data):
    """
    Just return data back to the client.
    """
    return data

services = {
    'echo': echo,
    'echo.echo': echo
}

if __name__ == '__main__':
    import os
    from pyamf.remoting.gateway.wsgi import WSGIGateway
    from wsgiref import simple_server

    gw = WSGIGateway(services)

    httpd = simple_server.WSGIServer(
        ('localhost', 8000),
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

        return gw(environ, start_response)

    httpd.set_app(app)

    print "Running Hello World AMF gateway on http://localhost:8000"

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass

