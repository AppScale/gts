# Copyright (c) The PyAMF Project.
# See LICENSE for details.

import sys, os

sys.path.append(os.getcwd())

from twisted.application import internet, service
from server import TimerFactory, SocketPolicyFactory
from server import appPort, policyPort


timer = TimerFactory()
policy = SocketPolicyFactory('socket-policy.xml')

# this is the important bit
application = service.Application('pyamf-socket-example')

timerService = internet.TCPServer(appPort, timer)
socketPolicyService = internet.TCPServer(policyPort, policy)

timerService.setServiceParent(application)
socketPolicyService.setServiceParent(application)