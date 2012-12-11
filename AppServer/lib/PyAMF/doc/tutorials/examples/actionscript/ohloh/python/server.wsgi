# Copyright (c) The PyAMF Project.
# See LICENSE for details.

import sys
sys.path.append('/usr/src/pyamf/')
sys.path.append('/home/pyamf/examples/ohloh/python/')

from pyamf.remoting.gateway.wsgi import WSGIGateway
import server

application = WSGIGateway(server.services)

