#!/usr/bin/env python
#
# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.


"""
AMF client for Local Shared Object example.
"""


import logging
from optparse import OptionParser

from pyamf.remoting.client import RemotingService

from service import SharedObject


logging.basicConfig(
    level=logging.INFO,
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
service = client.getService('lso')

result = service.getApps()

path = result[0]
apps = result[1]

t = 0
for app in apps:
    t += 1
    print
    print '%d. %s - %s (%s files)' % (t, app.domain, app.name,
                                len(app.files))
    for sol in app.files:
        print ' - %s  (%s bytes) - $PATH%s' % (sol.filename, sol.size,
                                              sol.path[len(path):])
        
print
print 'Path:', path
print 'Total apps:', len(apps)
