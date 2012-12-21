# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Gateway for RecordSet remoting service.

@since: 0.1.0
"""

from sqlalchemy.sql import select

from pyamf import register_class, amf0

import db

def as_recordset(result):
    keys = None

    if hasattr(result, 'keys'):
        keys = result.keys
    elif hasattr(result, '_ResultProxy__keys'):
        keys = result._ResultProxy__keys

    if keys is None:
        raise AttributeError('Unknown keys for result')

    return amf0.RecordSet(keys, [list(x) for x in result])

class SoftwareService(object):
    def __init__(self, engine):
        self.engine = engine

    def getLanguages(self):
        """
        Returns all the languages.
        """
        return as_recordset(self.engine.execute(
            select([db.language]).order_by(db.language.c.Name.desc())
        ))

    def getSoftware(self, lang):
        """
        Returns all the software projects for the selected language.
        """
        return as_recordset(self.engine.execute(
            select([db.software], db.software.c.CategoryID == lang)
        ))

def parse_args(args):
    """
    Parse commandline options.
    """
    from optparse import OptionParser

    parser = OptionParser()
    parser.add_option('--host', dest='host', default='localhost',
                      help='The host address for the AMF gateway')
    parser.add_option('-p', '--port', dest='port', default=8000,
                      help='The port number the server uses')

    return parser.parse_args(args)

if __name__ == '__main__':
    import sys
    from pyamf.remoting.gateway.wsgi import WSGIGateway
    from wsgiref import simple_server

    options = parse_args(sys.argv[1:])[0]
    service = {'service': SoftwareService(db.get_engine())}

    host = options.host
    port = int(options.port)

    gw = WSGIGateway(service)

    httpd = simple_server.WSGIServer(
        (host, port),
        simple_server.WSGIRequestHandler,
    )

    httpd.set_app(gw)

    print 'Started RecordSet example server on http://%s:%s' % (host, str(port) )

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
