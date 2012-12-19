# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Jython example AMF server and client with Swing interface.

@see: U{Jython<http://pyamf.org/wiki/JythonExample>} wiki page.
@since: 0.5
"""


import logging

from wsgiref.simple_server import WSGIServer, WSGIRequestHandler
from pyamf.remoting.gateway.wsgi import WSGIGateway
from pyamf.remoting.client import RemotingService

import java.lang as lang
import javax.swing as swing
import java.awt as awt


class AppGUI(object):
    """
    Swing graphical user interface.
    """
    def __init__(self, title, host, port, service):
        # create window
        win = swing.JFrame(title, size=(800, 480))
        win.setDefaultCloseOperation(swing.JFrame.EXIT_ON_CLOSE)
        win.contentPane.layout = awt.BorderLayout(10, 10)

        # add scrollable textfield
        status = swing.JTextPane(preferredSize=(780, 400))
        status.setAutoscrolls(True)
        status.setEditable(False)
        status.setBorder(swing.BorderFactory.createEmptyBorder(20, 20, 20, 20))
        paneScrollPane = swing.JScrollPane(status)
        paneScrollPane.setVerticalScrollBarPolicy(
                        swing.JScrollPane.VERTICAL_SCROLLBAR_AS_NEEDED)
        win.contentPane.add(paneScrollPane, awt.BorderLayout.CENTER)

        # add server button
        self.started = "Start Server"
        self.stopped = "Stop Server"
        self.serverButton = swing.JButton(self.started, preferredSize=(150, 20),
                                          actionPerformed=self.controlServer)

        # add client button
        self.clientButton = swing.JButton("Invoke Method", preferredSize=(150, 20),
                                          actionPerformed=self.runClient)
        self.clientButton.enabled = False

        # position buttons
        buttonPane = swing.JPanel()
        buttonPane.setLayout(swing.BoxLayout(buttonPane, swing.BoxLayout.X_AXIS))
        buttonPane.setBorder(swing.BorderFactory.createEmptyBorder(0, 10, 10, 10))
        buttonPane.add(swing.Box.createHorizontalGlue())
        buttonPane.add(self.serverButton)
        buttonPane.add(swing.Box.createRigidArea(awt.Dimension(10, 0)))
        buttonPane.add(self.clientButton)
        win.contentPane.add(buttonPane, awt.BorderLayout.SOUTH)

        # add handler that writes log messages to the status textfield
        txtHandler = TextFieldLogger(status)
        logger = logging.getLogger("")
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(message)s')
        txtHandler.setFormatter(formatter)
        logger.addHandler(txtHandler)

        # setup server
        self.service_name = service
        self.url = "http://%s:%d" % (host, port)
        self.server = ThreadedAmfServer(host, port, self.service_name)

        # center and display window on the screen
        win.pack()
        us = win.getSize()
        them = awt.Toolkit.getDefaultToolkit().getScreenSize()
        newX = (them.width - us.width) / 2
        newY = (them.height - us.height) / 2
        win.setLocation(newX, newY)
        win.show()

    def controlServer(self, event):
        """
        Handler for server button clicks.
        """
        if event.source.text == self.started:
            logging.info("Created AMF gateway at %s" % self.url)
            event.source.text = self.stopped
            self.clientButton.enabled = True
            self.server.start()
        else:
            logging.info("Terminated AMF gateway at %s\n" % self.url)
            event.source.text = self.started
            self.clientButton.enabled = False
            self.server.stop()

    def runClient(self, event):
        """
        Invoke a method on the server using an AMF client.
        """
        self.client = ThreadedAmfClient(self.url, self.service_name)
        self.client.invokeMethod("Hello World!")


class ThreadedAmfClient(object):
    """
    Threaded AMF client that doesn't block the Swing GUI.
    """
    def __init__(self, url, serviceName):
        self.gateway = RemotingService(url, logger=logging)
        self.service = self.gateway.getService(serviceName)

    def invokeMethod(self, param):
        """
        Invoke a method on the AMF server.
        """
        class ClientThread(lang.Runnable):
            """
            Create a thread for the client.
            """
            def run(this):
                try:
                    self.service(param)
                except lang.InterruptedException:
                    return

        swing.SwingUtilities.invokeLater(ClientThread())


class ThreadedAmfServer(object):
    """
    Threaded WSGI server that doesn't block the Swing GUI.
    """
    def __init__(self, host, port, serviceName):      
        services = {serviceName: self.echo}
        gw = WSGIGateway(services, logger=logging)
        self.httpd = WSGIServer((host, port),
                     ServerRequestLogger)
        self.httpd.set_app(gw)

    def start(self):
        """
        Start the server.
        """
        class WSGIThread(lang.Runnable):
            """
            Create a thread for the server.
            """
            def run(this):
                try:
                    self.httpd.serve_forever()
                except lang.InterruptedException:
                    return

        self.thread = lang.Thread(WSGIThread())
        self.thread.start()

    def stop(self):
        """
        Stop the server.
        """
        self.thread = None

    def echo(self, data):
        """
        Just return data back to the client.
        """
        return data


class ServerRequestLogger(WSGIRequestHandler):
    """
    Request handler that logs WSGI server messages.
    """
    def log_message(self, format, *args):
        """
        Log message with debug level.
        """
        logging.debug("%s - %s" % (self.address_string(), format % args))


class TextFieldLogger(logging.Handler):
    """
    Logging handler that displays PyAMF log messages in the status text field.
    """
    def __init__(self, textfield, *args, **kwargs):
        self.status = textfield
        logging.Handler.__init__(self, *args, **kwargs)

    def emit(self, record):
        msg = '%s\n' % self.format(record)
        doc = self.status.getStyledDocument()
        doc.insertString(doc.getLength(), msg, doc.getStyle('regular'))
        self.status.setCaretPosition(self.status.getStyledDocument().getLength())


host = "localhost"
port = 8000
service_name = "echo"
title = "PyAMF server/client using Jython with Swing"


if __name__ == "__main__":
    from optparse import OptionParser

    parser = OptionParser()
    parser.add_option("-p", "--port", default=port,
        dest="port", help="port number [default: %default]")
    parser.add_option("--host", default=host,
        dest="host", help="host address [default: %default]")
    (opt, args) = parser.parse_args()

    app = AppGUI(title, opt.host, int(opt.port), service_name)
