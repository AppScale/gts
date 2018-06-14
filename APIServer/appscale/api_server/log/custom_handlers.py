""" Handles custom HTTP requests from the dispatcher. """

from tornado import web
from tornado.escape import json_decode

from appscale.api_server.log.messages import RequestLog
from appscale.common.constants import HTTPCodes


class StartRequestHandler(web.RequestHandler):
    """ Creates a log entry for a new request. """
    def initialize(self, log_service):
        """ Defines resources required to handle requests.

        Args:
            log_service: A LogService object.
        """
        self.log_service = log_service

    def post(self):
        """ Creates a log entry for a new request. """
        try:
            args = json_decode(self.request.body)
        except ValueError:
            raise web.HTTPError(HTTPCodes.BAD_REQUEST,
                                'Payload must be valid JSON')

        try:
            request_log = RequestLog(**args)
        except TypeError as error:
            raise web.HTTPError(HTTPCodes.BAD_REQUEST, str(error))

        self.log_service.start_request(request_log)


class EndRequestHandler(web.RequestHandler):
    """ Finalizes a request log and sends it to the log server. """
    def initialize(self, log_service):
        """ Defines resources required to handle requests.

        Args:
            log_service: A LogService object.
        """
        self.log_service = log_service

    def post(self):
        """ Finalizes a request log and sends it to the log server. """
        try:
            args = json_decode(self.request.body)
        except ValueError:
            raise web.HTTPError(HTTPCodes.BAD_REQUEST,
                                'Payload must be valid JSON')

        try:
            self.log_service.end_request(**args)
        except TypeError as error:
            raise web.HTTPError(HTTPCodes.BAD_REQUEST, str(error))
