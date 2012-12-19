#!/usr/bin/python
#
# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Client for the SQLAlchemy Addressbook example.

@see: U{AddressBookExample<http://pyamf.org/wiki/AddressBookExample>} wiki page.
@since: 0.5
"""


import logging
from optparse import OptionParser

from server import host, port, namespace

from pyamf.remoting.client import RemotingService


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s'
)

parser = OptionParser()
parser.add_option("-p", "--port", default=port,
    dest="port", help="port number [default: %default]")
parser.add_option("--host", default=host,
    dest="host", help="host address [default: %default]")
(options, args) = parser.parse_args()


url = 'http://%s:%d' % (options.host, int(options.port))
client = RemotingService(url, logger=logging)

service = client.getService('ExampleService')
ns = namespace + '.'

print service.insertDefaultData()

print 'Load users:'
for user in service.loadAll(ns + 'User'):
    print '\t%s. %s (%s)' % (user.id, user.first_name, user.created)

