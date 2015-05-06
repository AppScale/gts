""" Web server/client that polls the AppScale Portal for new tasks and
initiates actions accordingly. """

import logging
import signal
import socket
import tornado.escape
import tornado.httpclient
import tornado.web

from tornado.ioloop import IOLoop
from tornado.options import define
from tornado.options import options
from tornado.options import parse_command_line

import hermes_constants
from handlers import MainHandler
from handlers import PollHandler
from handlers import TaskHandler
import helper

# Tornado web server options.
define("port", default=hermes_constants.HERMES_PORT, type=int)
define("debug", default=True, type=bool)

def poll():
  """ Callback function that polls for new tasks based on a schedule. """
  logging.info("Time to poll for a new task.")

  url = "{0}{1}".format(hermes_constants.HERMES_URL, PollHandler.PATH)
  helper.urlfetch_async(helper.create_request(url=url, method='GET'))

def signal_handler(signal, frame):
  """ Signal handler for graceful shutdown. """
  logging.warning("Caught signal: {0}".format(signal))
  IOLoop.instance().add_callback(shutdown)

def shutdown():
  """ Shuts down the server. """
  logging.info("Hermes shutting down.")
  IOLoop.instance().stop()

def main():
  """ Main. """
  logging.getLogger().setLevel(logging.DEBUG)

  signal.signal(signal.SIGTERM, signal_handler)
  signal.signal(signal.SIGINT, signal_handler)

  parse_command_line()

  app = tornado.web.Application([
    (MainHandler.PATH, MainHandler),
    (PollHandler.PATH, PollHandler),
    (TaskHandler.PATH, TaskHandler),
  ], debug=options.debug)

  try:
    app.listen(options.port)
  except socket.error:
    logging.error("ERROR on Hermes initialization: Port {0} already in use.".
      format(options.port))
    shutdown()
    return

  logging.info("Hermes is up and listening on port: {0}.".
    format(options.port))

  # Start polling loop.
  tornado.ioloop.PeriodicCallback(poll,
    hermes_constants.POLLING_INTERVAL).start()

  # Start loop for accepting http requests.
  IOLoop.instance().start()

if __name__ == "__main__":
  main()
