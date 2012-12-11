#!/usr/bin/env python
#
# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.


"""
GeoIP example server.

@see: U{GeoipExample<http://pyamf.org/wiki/GeoipExample>} wiki page.

@since: 0.1
"""                                                             


try:
    import GeoIP
    
    gi = GeoIP.new(GeoIP.GEOIP_STANDARD)
except ImportError:
    raise ImportError('This example requires the Maxmind GeoIP Python API package')

import pyamf
from pyamf.remoting.gateway import expose_request


class GeoInfo(object):
    def __init__(self):
        self.country = {}
        self.ip = ''

    def __repr__(self):
        return '<%s country=%s ip=%s>' % (GeoInfo.__name__, self.country, self.ip)

pyamf.register_class(GeoInfo, 'org.pyamf.examples.geoip.GeoInfo')


class GeoService(object):
    def __init__(self, engine):
        self.engine = engine

    def getCountryName(self, by, target):
        if by == 'name':
            return self.engine.country_name_by_name(target)

        return self.engine.country_name_by_addr(target)

    def getCountryCode(self, by, target):
        if by == 'name':
            return self.engine.country_code_by_name(target)

        return self.engine.country_code_by_addr(target)

    def getOrganization(self, by, target):
        if by == 'name':
            return self.engine.org_by_name(target)

        return self.engine.org_by_addr(target)

    def getRegion(self, by, target):
        if by == 'name':
            return self.engine.region_by_name(target)

        return self.engine.region_by_addr(target)

    def getRecord(self, by, target):
        if by == 'name':
            return self.engine.record_by_name(target)

        return self.engine.record_by_addr(target)

    @expose_request
    def getGeoInfo(self, environ, target=None):
        if target is None:
            target = environ['REMOTE_ADDR']

        gi = GeoInfo()
        gi.country = {
            'name': self.getCountryName('addr', target),
            'code': self.getCountryCode('addr', target)
        }
        gi.ip = target

        return gi

   
services = {
    'geoip': GeoService(gi)
}


if __name__ == '__main__':
    from pyamf.remoting.gateway.wsgi import WSGIGateway
    from wsgiref import simple_server
    from optparse import OptionParser

    parser = OptionParser()
    parser.add_option("-p", "--port", default=8000,
        dest="port", help="port number [default: %default]")
    parser.add_option("--host", default="localhost",
        dest="host", help="host address [default: %default]")
    (options, args) = parser.parse_args()

    gw = WSGIGateway(services)

    httpd = simple_server.WSGIServer(
        (options.host, int(options.port)),
        simple_server.WSGIRequestHandler,
    )

    httpd.set_app(gw)

    print "Running GeoIP AMF gateway on http://%s:%d" % (options.host,
                                                         int(options.port))

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
