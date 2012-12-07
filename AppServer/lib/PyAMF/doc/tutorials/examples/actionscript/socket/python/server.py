# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Example socket server using Twisted.

@see: U{Documentation for this example<http://pyamf.org/tutorials/actionscript/socket.html>}

@since: 0.1
"""


try:
    import twisted
except ImportError:
    print "This examples requires the Twisted framework. Download it from http://twistedmatrix.com"
    raise SystemExit

from twisted.internet.protocol import Protocol, Factory
from twisted.internet import reactor

from datetime import datetime
import pyamf


class TimerProtocol(Protocol):
    interval = 1.0 # interval in seconds to send the time
    encoding = pyamf.AMF0
    timeout = 300 

    def __init__(self):
        self.started = False
        self.encoder = pyamf.get_encoder(self.encoding)
        self.stream = self.encoder.stream

    def connectionLost(self, reason):
        Protocol.connectionLost(self, reason)

        self.factory.number_of_connections -= 1

    def connectionMade(self):
        if self.factory.number_of_connections >= self.factory.max_connections:
            self.transport.write('Too many connections, try again later')
            self.transport.loseConnection()

            return

        self.factory.number_of_connections += 1
        self.timeout_deferred = reactor.callLater(TimerProtocol.timeout, self.transport.loseConnection)

    def dataReceived(self, data):
        data = data.strip()
        if data == 'start':
            # start sending a date object that contains the current time
            if not self.started:
                self.start()
        elif data == 'stop':
            self.stop()

        if self.timeout_deferred:
            self.timeout_deferred.cancel()
            self.timeout_deferred = reactor.callLater(TimerProtocol.timeout, self.transport.loseConnection)

    def start(self):
        self.started = True
        self.sendTime()

    def stop(self):
        self.started = False

    def sendTime(self):
        if self.started:
            self.encoder.writeElement(datetime.now())
            self.transport.write(self.stream.getvalue())
            self.stream.truncate()

            reactor.callLater(self.interval, self.sendTime)


class TimerFactory(Factory):
    protocol = TimerProtocol
    max_connections = 1000

    def __init__(self):
        self.number_of_connections = 0


class SocketPolicyProtocol(Protocol):
    """
    Serves strict policy file for Flash Player >= 9,0,124.
    
    @see: U{http://adobe.com/go/strict_policy_files}
    """
    def connectionMade(self):
        self.buffer = ''

    def dataReceived(self, data):
        self.buffer += data

        if self.buffer.startswith('<policy-file-request/>'):
            self.transport.write(self.factory.getPolicyFile(self))
            self.transport.loseConnection()


class SocketPolicyFactory(Factory):
    protocol = SocketPolicyProtocol

    def __init__(self, policy_file):
        """
        @param policy_file: Path to the policy file definition
        """
        self.policy_file = policy_file

    def getPolicyFile(self, protocol):
        return open(self.policy_file, 'rt').read()


host = 'localhost'
appPort = 8000
policyPort = 843
policyFile = 'socket-policy.xml'


if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser()
    parser.add_option("--host", default=host,
        dest="host", help="host address [default: %default]")
    parser.add_option("-a", "--app-port", default=appPort,
        dest="app_port", help="Application port number [default: %default]")
    parser.add_option("-p", "--policy-port", default=policyPort,
        dest="policy_port", help="Socket policy port number [default: %default]")
    parser.add_option("-f", "--policy-file", default=policyFile,
        dest="policy_file", help="Location of socket policy file [default: %default]")
    (opt, args) = parser.parse_args()

    print "Running Socket AMF gateway on %s:%s" % (opt.host, opt.app_port)
    print "Running Policy file server on %s:%s" % (opt.host, opt.policy_port)
    
    reactor.listenTCP(int(opt.app_port), TimerFactory(), interface=opt.host)
    reactor.listenTCP(int(opt.policy_port), SocketPolicyFactory(opt.policy_file),
                      interface=opt.host)
    reactor.run()
