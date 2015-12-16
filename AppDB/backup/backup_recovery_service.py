""" Top level server for backup and recovery. """

import json
import logging

import tornado.httpserver
import tornado.httputil
import tornado.ioloop
import tornado.web

import backup_recovery_helper
from backup_recovery import BackupService
from backup_recovery_constants import BACKUP_DIR_LOCATION
from backup_recovery_constants import DEFAULT_PORT
from backup_recovery_constants import HTTP_OK

class MainHandler(tornado.web.RequestHandler):
  """ Main handler class. """
  
  def initialize(self, backup_recovery_service):
    """ Class for initializing backup/recovery web handler. """
    self.backup_recovery_service = backup_recovery_service

  def get(self):
    """ A GET handler for requests to this server. """
    self.write(json.dumps({'status': 'up'}))

  @tornado.web.asynchronous
  def post(self):
    """ A POST handler for request to this server. """
    request = self.request
    http_request_data = request.body
    response = self.backup_recovery_service.remote_request(http_request_data)

    request.connection.write_headers(
      tornado.httputil.ResponseStartLine('HTTP/1.1', HTTP_OK, 'OK'),
      tornado.httputil.HTTPHeaders({"Content-Length": str(len(response))}))
    request.connection.write(response)
    request.connection.finish()

def get_application():
  """ Retrieves the application to feed into tornado. """
  return tornado.web.Application([
    (r"/?", MainHandler, dict(backup_recovery_service=BackupService())),
    ], )

def main():
  """ Main. """

  logging.getLogger().setLevel(logging.INFO)
  logging.info("Starting server on port {0}".format(DEFAULT_PORT))

  # Create backups dir if it doesn't exist.
  if not backup_recovery_helper.mkdir(BACKUP_DIR_LOCATION):
    logging.warning("Dir '{0}' already exists. Skipping dir creation...".
      format(BACKUP_DIR_LOCATION))

  # Start Tornado.
  http_server = tornado.httpserver.HTTPServer(get_application())
  http_server.bind(DEFAULT_PORT)
  http_server.start(0)
  tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
  main()
