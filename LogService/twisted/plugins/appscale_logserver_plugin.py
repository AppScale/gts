import os
import sys

from logserver import LogServerFactory
from twisted.application import internet, service
from twisted.application.service import IServiceMaker
from twisted.plugin import IPlugin
from twisted.python import log
from twisted.python import usage
from zope.interface import implementer

class Options(usage.Options):
  optParameters = [["port", "p", 7422, "The port number to listen on."],
                   ["path", "a", "/opt/appscale/logserver", "Path where logs are stored."],
                   ["size", "s", 2, "Size in GiB of retention of logs."],
                   ["unix_socket", "u", "/run/appscale/logserver.sock", "Path for unix socket to logserver."]]


@implementer(IServiceMaker, IPlugin)
class MyServiceMaker(object):
  tapname = "appscale-logserver"
  description = "Holds track of appserver logs."

  options = Options

  def makeService(self, options):
    application = service.MultiService()

    logserver_factory = LogServerFactory(options["path"], int(options["size"]))

    tcp_news_server = internet.TCPServer(int(options["port"]), logserver_factory)
    tcp_news_server.setServiceParent(application)

    if os.path.exists(options["unix_socket"]):
      os.remove(options["unix_socket"])
    unix_news_server = internet.UNIXServer(options["unix_socket"], logserver_factory)
    unix_news_server.setServiceParent(application)
    log.startLogging(sys.stdout)
    log.msg("Log Service started with parameters: port:{} path:{} "
            "size:{} unix_socket:{}".format(options.get("port"),
                                            options.get("path"),
                                            options.get("size"),
                                            options.get("unix_socket")))
    return application


# Now construct an object which *provides* the relevant interfaces
# The name of this variable is irrelevant, as long as there is *some*
# name bound to a provider of IPlugin and IServiceMaker.

serviceMaker = MyServiceMaker()
