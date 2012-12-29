# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.


import logging
from optparse import OptionParser

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
client.setCredentials('jane', 'doe')

calc_service = client.getService('calc')
print calc_service.sum(85, 115) # should print 200.0

client.setCredentials('abc', 'def')
print calc_service.sum(85, 115).description # should print Authentication Failed
