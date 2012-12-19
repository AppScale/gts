import stackless

from   twisted.web import resource, http, server, error
from   twisted.internet import reactor
from   twisted.python import log

from   pyamf import remoting
from   pyamf.remoting.gateway.twisted import TwistedGateway
from   twisted.internet import defer
from   twisted.internet import task


class EchoServer(TwistedGateway):

   def __init__(self):
       super(EchoServer, self).__init__()
       self.request = None
       return

   def __echo__(self, request, deferred, y):
       deferred.callback(y)

   def echo(self, request, y):
       deferred = defer.Deferred()
       stackless.tasklet(self.__echo__)(request, deferred, y)

       return deferred


if __name__== "__main__":
   gw = EchoServer()
   gw.addService(gw.echo, "echo", "echo")

   root = resource.Resource()
   root.putChild('gwplayer', gw)
   reactor.listenTCP(8080, server.Site(root))
   print "server running on localhost:8080"

   task.LoopingCall(stackless.schedule).start(.01)
   stackless.tasklet(reactor.run)()
   stackless.run()