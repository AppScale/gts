# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Gateway for Google App Engine.

This gateway allows you to expose functions in Google App Engine web
applications to AMF clients and servers.

@see: U{Google App Engine homepage
    <http://code.google.com/appengine/docs/python/overview.html>}
@since: 0.3.1
"""

import sys
import os.path

try:
    sys.path.remove(os.path.dirname(os.path.abspath(__file__)))
except ValueError:
    pass

google = __import__('google.appengine.ext.webapp')
webapp = google.appengine.ext.webapp

from pyamf import remoting, DecodeError
from pyamf.remoting import gateway

__all__ = ['WebAppGateway']


class WebAppGateway(webapp.RequestHandler, gateway.BaseGateway):
    """
    Google App Engine Remoting Gateway.
    """

    __name__ = None

    def __init__(self, *args, **kwargs):
        gateway.BaseGateway.__init__(self, *args, **kwargs)

    def getResponse(self, request):
        """
        Processes the AMF request, returning an AMF response.

        :param request: The AMF Request.
        :type request: :class:`Envelope<pyamf.remoting.Envelope>`
        :rtype: :class:`Envelope<pyamf.remoting.Envelope>`
        :return: The AMF Response.
        """
        response = remoting.Envelope(request.amfVersion)

        for name, message in request:
            self.request.amf_request = message

            processor = self.getProcessor(message)
            response[name] = processor(message, http_request=self.request)

        return response

    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.headers['Server'] = gateway.SERVER_NAME
        self.error(405)
        self.response.out.write("405 Method Not Allowed\n\n"
            "To access this PyAMF gateway you must use POST requests "
            "(%s received)" % self.request.method)

    def post(self):
        body = self.request.body_file.read()
        stream = None
        timezone_offset = self._get_timezone_offset()

        # Decode the request
        try:
            request = remoting.decode(body, strict=self.strict,
                logger=self.logger, timezone_offset=timezone_offset)
        except (DecodeError, IOError):
            if self.logger:
                self.logger.exception('Error decoding AMF request')

            response = ("400 Bad Request\n\nThe request body was unable to "
                "be successfully decoded.")

            if self.debug:
                response += "\n\nTraceback:\n\n%s" % gateway.format_exception()

            self.error(400)
            self.response.headers['Content-Type'] = 'text/plain'
            self.response.headers['Server'] = gateway.SERVER_NAME
            self.response.out.write(response)

            return
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            if self.logger:
                self.logger.exception('Unexpected error decoding AMF request')

            response = ('500 Internal Server Error\n\n'
                'An unexpected error occurred.')

            if self.debug:
                response += "\n\nTraceback:\n\n%s" % gateway.format_exception()

            self.error(500)
            self.response.headers['Content-Type'] = 'text/plain'
            self.response.headers['Server'] = gateway.SERVER_NAME
            self.response.out.write(response)

            return

        if self.logger:
            self.logger.debug("AMF Request: %r" % request)

        # Process the request
        try:
            response = self.getResponse(request)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            if self.logger:
                self.logger.exception('Error processing AMF request')

            response = ("500 Internal Server Error\n\nThe request was " \
                "unable to be successfully processed.")

            if self.debug:
                response += "\n\nTraceback:\n\n%s" % gateway.format_exception()

            self.error(500)
            self.response.headers['Content-Type'] = 'text/plain'
            self.response.headers['Server'] = gateway.SERVER_NAME
            self.response.out.write(response)

            return

        if self.logger:
            self.logger.debug("AMF Response: %r" % response)

        # Encode the response
        try:
            stream = remoting.encode(response, strict=self.strict,
                logger=self.logger, timezone_offset=timezone_offset)
        except:
            if self.logger:
                self.logger.exception('Error encoding AMF request')

            response = ("500 Internal Server Error\n\nThe request was " \
                "unable to be encoded.")

            if self.debug:
                response += "\n\nTraceback:\n\n%s" % gateway.format_exception()

            self.error(500)
            self.response.headers['Content-Type'] = 'text/plain'
            self.response.headers['Server'] = gateway.SERVER_NAME
            self.response.out.write(response)

            return

        response = stream.getvalue()

        self.response.headers['Content-Type'] = remoting.CONTENT_TYPE
        self.response.headers['Content-Length'] = str(len(response))
        self.response.headers['Server'] = gateway.SERVER_NAME

        self.response.out.write(response)

    def __call__(self, *args, **kwargs):
        return self
