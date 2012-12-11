#!/usr/bin/python
#
# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
GeoIP example client.

@see: U{GeoipExample<http://pyamf.org/wiki/GeoipExample>} wiki page.
@since: 0.1
"""


import logging
from optparse import OptionParser

import server

from pyamf.remoting.client import RemotingService


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s'
)

parser = OptionParser()
parser.add_option("-p", "--port", default=8000,
    dest="port", help="port number [default: %default]")
parser.add_option("--host", default="localhost",
    dest="host", help="host address [default: %default]")
(options, args) = parser.parse_args()


url = 'http://%s:%d' % (options.host, int(options.port))
client = RemotingService(url, logger=logging)

service = client.getService('geoip')
print service.getGeoInfo()
