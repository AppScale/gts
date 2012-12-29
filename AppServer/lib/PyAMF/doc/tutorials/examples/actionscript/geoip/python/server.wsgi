# Copyright (c) The PyAMF Project.
# See LICENSE for details.

"""
GeoIP example server for mod_wsgi.

@see: U{GeoipExample<http://pyamf.org/wiki/GeoipExample>} wiki page.
@author: U{Thijs Triemstra<mailto:info@collab.nl>}
@since: 0.1
"""

import sys
sys.path.append('/usr/src/pyamf/')
sys.path.append('/home/pyamf/examples/geoip/')

import server

from pyamf.remoting.gateway.wsgi import WSGIGateway

application = WSGIGateway(server.services)
