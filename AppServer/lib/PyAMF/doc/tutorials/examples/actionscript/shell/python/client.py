# Copyright (c) The PyAMF Project.
# See LICENSE for details.

"""
Client for shell example.

@since: 0.5
"""


import sys
from optparse import OptionParser

from pyamf.remoting.client import RemotingService


parser = OptionParser()
parser.add_option("-p", "--port", default=8000,
    dest="port", help="port number [default: %default]")
parser.add_option("--host", default="localhost",
    dest="host", help="host address [default: %default]")
(options, args) = parser.parse_args()


url = 'http://%s:%d/gateway/shell/' % (options.host, int(options.port))
server = RemotingService(url)
print 'Connecting to %s\n' % url
    
# call service to fetch intro text
intro = server.getService('shell.startup')
print intro()

# call service to evalute script and return result
evaluate = server.getService('shell.evalCode')

# start the shell
while 1:
    input = raw_input('>>> ')
    print evaluate(input)