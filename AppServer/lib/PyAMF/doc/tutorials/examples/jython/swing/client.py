#!/usr/bin/env jython
#
# Copyright (c) The PyAMF Project.
# See LICENSE for details.

"""
Jython AMF client example.

@since: 0.5
"""


import gui

from optparse import OptionParser

from pyamf.remoting.client import RemotingService


# parse commandline options
parser = OptionParser()
parser.add_option("-p", "--port", default=gui.port,
    dest="port", help="port number [default: %default]")
parser.add_option("--host", default=gui.host,
    dest="host", help="host address [default: %default]")
(options, args) = parser.parse_args()

# define gateway
url = 'http://%s:%d' % (options.host, int(options.port))
server = RemotingService(url)

# echo data
service = server.getService(gui.service_name)

print service('Hello World!')