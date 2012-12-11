# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Test Twisted server for Adobe AIR 2.0's UDP support.

Based on examples from http://twistedmatrix.com/documents/current/core/howto/udp.html
"""

from pyamf import register_class
from pyamf.amf3 import ByteArray

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor


class HelloWorld(object):

    def __repr__(self):
        return "<%s msg='%s' time=%s />" % (self.__class__.__name__, self.msg,
                                          self.time)


class EchoUDPServer(DatagramProtocol):

    def datagramReceived(self, data, (host, port)):
        ba = ByteArray(data)
        result = ba.readObject()
        print " received %s from %s:%d" % (result, host, port)

        self.transport.write(data, (host, port))


if __name__ == "__main__":
    alias = "org.pyamf.examples.air.udp.vo.HelloWorld"
    register_class(HelloWorld, alias)
    print "Registered alias '%s' for class '%s'" % (alias, HelloWorld.__name__)

    port = 55555
    print 'Server started listening on port', port

    server = EchoUDPServer()
    reactor.listenUDP(port, server)
    reactor.run()
