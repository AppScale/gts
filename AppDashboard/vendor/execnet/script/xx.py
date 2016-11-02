import rlcompleter2

import register
import sys
rlcompleter2.setup()

try:
    hostport = sys.argv[1]
except:
    hostport = ':8888'
gw = register.ServerGateway(hostport)
