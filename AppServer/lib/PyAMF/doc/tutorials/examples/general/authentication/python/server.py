# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Authentication example server.

@since: 0.1
"""


from pyamf.remoting.gateway.wsgi import WSGIGateway


class CalcService:
    def sum(self, a, b):
         return a + b


def auth(username, password):
    if username == 'jane' and password == 'doe':
        return True

    return False


gateway = WSGIGateway({'calc': CalcService}, authenticator=auth)


if __name__ == '__main__':
    from optparse import OptionParser
    from wsgiref import simple_server

    parser = OptionParser()
    parser.add_option("-p", "--port", default=8000,
        dest="port", help="port number [default: %default]")
    parser.add_option("--host", default="localhost",
        dest="host", help="host address [default: %default]")
    (options, args) = parser.parse_args()

    host = options.host
    port = int(options.port)

    httpd = simple_server.WSGIServer((host, port), simple_server.WSGIRequestHandler)
    httpd.set_app(gateway)

    print "Running Authentication AMF gateway on http://%s:%d" % (host, port)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
