# Copyright (c) The PyAMF Project.
# See LICENSE for details.

import sys
sys.path.append('/usr/src/pyamf/')
sys.path.append('/home/pyamf/examples/authentication/')

from pyamf.remoting.gateway.wsgi import WSGIGateway

class CalcService:
    def sum(self, a, b):
         return a + b

def auth(username, password):
    if username == 'jane' and password == 'doe':
        return True

    return False

application = WSGIGateway({'calc': CalcService}, authenticator=auth)
