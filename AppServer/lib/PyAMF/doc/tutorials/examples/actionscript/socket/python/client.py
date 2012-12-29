# Copyright (c) The PyAMF Project.
# See LICENSE for details.

"""
Python client for socket example.

@since: 0.5
"""


import socket
import pyamf

from server import appPort, host


class AmfSocketClient(object):
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def connect(self, host, port):
        print "Connecting to socket server on %s:%d" % (host, port)
        try:
            self.sock.connect((host, port))
            print "Connected to server.\n"
        except socket.error, e:
            raise Exception("Can't connect: %s" % e[1])

    def start(self):
        msg = ''

        # tell server we started listening
        print "send request: start"
        try:
            self.sock.send('start')
        except socket.error, e:
            raise Exception("Can't connect: %s" % e[1])

        while len(msg) < 1024:
            # read from server
            amf = self.sock.recv(1024)

            if amf == '':
                print "Connection closed."

            msg = msg + amf

            for obj in pyamf.decode(amf):
                print obj

        return msg

    def stop(self):
        print "send request: stop"
        self.sock.send('stop')


if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser()
    parser.add_option("-p", "--port", default=appPort,
        dest="port", help="port number [default: %default]")
    parser.add_option("--host", default=host,
        dest="host", help="host address [default: %default]")
    (options, args) = parser.parse_args()

    host = options.host
    port = int(options.port)

    client = AmfSocketClient()
    client.connect(host, port)

    try:
        client.start()
    except KeyboardInterrupt:
        client.stop()   
