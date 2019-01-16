""" Top level server for the Search API. """
import logging

import argparse
from appscale.common.constants import LOG_FORMAT
import tornado.httpserver
import tornado.httputil
import tornado.ioloop
import tornado.web

from search_api import SearchService

# Default port for the search API web server.
DEFAULT_PORT = 53423

class MainHandler(tornado.web.RequestHandler):
  """ Main handler class. """

  def initialize(self, search_service):
    """ Class for initializing search service web handler. """
    self.search_service = search_service

  def post(self):
    """ A POST handler for request to this server. """
    request = self.request
    http_request_data = request.body
    pb_type = request.headers['protocolbuffertype']
    if pb_type == "Request":
      response = self.search_service.remote_request(http_request_data)
    else:
      response = self.search_service.unknown_request(pb_type)

    request.connection.write_headers(
      tornado.httputil.ResponseStartLine('HTTP/1.1', 200, 'OK'),
      tornado.httputil.HTTPHeaders({"Content-Length": str(len(response))}))
    request.connection.write(response)


if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument(
    '-v', '--verbose', action='store_true',
    help='Output debug-level logging')
  args = parser.parse_args()

  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
  if args.verbose:
    logging.getLogger().setLevel(logging.DEBUG)

  logging.info("Starting server on port {0}".format(DEFAULT_PORT))

  app = tornado.web.Application([
    (r"/?", MainHandler, dict(search_service=SearchService())),
  ])
  app.listen(DEFAULT_PORT)
  tornado.ioloop.IOLoop.current().start()
