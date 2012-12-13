# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

import logging
from optparse import OptionParser

import guestbook
from server import port

from pyamf.remoting.client import RemotingService


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s'
)


parser = OptionParser()
parser.add_option("-p", "--port", default=port,
    dest="port", help="port number [default: %default]")
parser.add_option("--host", default="localhost",
    dest="host", help="host address [default: %default]")
(options, args) = parser.parse_args()


url = 'http://%s:%d/gateway' % (options.host, int(options.port))
client = RemotingService(url, logger=logging)

service = client.getService('guestbook')

# print service.addMessage('Nick', 'http://boxdesign.co.uk',
#                          'nick@pyamf.org', 'Hello World!')
print service.getMessages()
