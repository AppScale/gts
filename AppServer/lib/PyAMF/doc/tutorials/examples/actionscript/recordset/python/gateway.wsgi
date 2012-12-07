# Copyright (c) The PyAMF Project.
# See LICENSE for details.

"""
RecordSet test mod_wsgi example.

You can use this example with the swf client on the
U{EchoTest<http://pyamf.org/wiki/RecordSet>} wiki page.

@author: U{Thijs Triemstra<mailto:info@collab.nl>}
@since: 0.1.0
"""

import sys
sys.path.append('/usr/src/pyamf/')
sys.path.append('/home/pyamf-examples/recordset/python/')

import gateway, db
from gateway import SoftwareService

from pyamf.remoting.gateway.wsgi import WSGIGateway

services = {'service': SoftwareService(db.get_engine())}

application = WSGIGateway(services)
