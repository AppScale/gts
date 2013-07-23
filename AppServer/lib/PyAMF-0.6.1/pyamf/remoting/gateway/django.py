# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Gateway for the Django framework.

This gateway allows you to expose functions in Django to AMF clients and
servers.

@see: U{Django homepage<http://djangoproject.com>}
@since: 0.1.0
"""

django = __import__('django.http')
http = django.http
conf = __import__('django.conf')
conf = conf.conf

import pyamf
from pyamf import remoting
from pyamf.remoting import gateway

__all__ = ['DjangoGateway']


class DjangoGateway(gateway.BaseGateway):
    """
    An instance of this class is suitable as a Django view.

    An example usage would be through C{urlconf}::

        from django.conf.urls.defaults import *

        urlpatterns = patterns('',
            (r'^gateway/', 'yourproject.yourapp.gateway.gw_instance'),
        )

    where C{yourproject.yourapp.gateway.gw_instance} refers to an instance of
    this class.

    @ivar expose_request: The standard Django view always has the request
        object as the first parameter. To disable this functionality, set this
        to C{False}.
    """

    csrf_exempt = True

    def __init__(self, *args, **kwargs):
        kwargs['expose_request'] = kwargs.get('expose_request', True)

        try:
            tz = conf.settings.AMF_TIME_OFFSET
        except AttributeError:
            tz = None

        try:
            debug = conf.settings.DEBUG
        except AttributeError:
            debug = False

        kwargs['timezone_offset'] = kwargs.get('timezone_offset', tz)
        kwargs['debug'] = kwargs.get('debug', debug)

        gateway.BaseGateway.__init__(self, *args, **kwargs)

    def getResponse(self, http_request, request):
        """
        Processes the AMF request, returning an AMF response.

        @param http_request: The underlying HTTP Request.
        @type http_request: U{HTTPRequest<http://docs.djangoproject.com
            /en/dev/ref/request-response/#httprequest-objects>}
        @param request: The AMF Request.
        @type request: L{Envelope<pyamf.remoting.Envelope>}
        @rtype: L{Envelope<pyamf.remoting.Envelope>}
        """
        response = remoting.Envelope(request.amfVersion)

        for name, message in request:
            http_request.amf_request = message

            processor = self.getProcessor(message)
            response[name] = processor(message, http_request=http_request)

        return response

    def __call__(self, http_request):
        """
        Processes and dispatches the request.
        """
        if http_request.method != 'POST':
            return http.HttpResponseNotAllowed(['POST'])

        stream = None
        timezone_offset = self._get_timezone_offset()

        # Decode the request
        try:
            request = remoting.decode(http_request.raw_post_data,
                strict=self.strict, logger=self.logger,
                timezone_offset=timezone_offset)
        except (pyamf.DecodeError, IOError):
            if self.logger:
                self.logger.exception('Error decoding AMF request')

            response = ("400 Bad Request\n\nThe request body was unable to "
                "be successfully decoded.")

            if self.debug:
                response += "\n\nTraceback:\n\n%s" % gateway.format_exception()

            # support for Django 0.96
            http_response = http.HttpResponse(mimetype='text/plain',
                content=response)

            http_response.status_code = 400

            return http_response
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            if self.logger:
                self.logger.exception('Unexpected error decoding AMF request')

            response = ('500 Internal Server Error\n\n'
                'An unexpected error occurred.')

            if self.debug:
                response += "\n\nTraceback:\n\n%s" % gateway.format_exception()

            return http.HttpResponseServerError(mimetype='text/plain',
                content=response)

        if self.logger:
            self.logger.debug("AMF Request: %r" % request)

        # Process the request
        try:
            response = self.getResponse(http_request, request)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            if self.logger:
                self.logger.exception('Error processing AMF request')

            response = ("500 Internal Server Error\n\nThe request was "
                "unable to be successfully processed.")

            if self.debug:
                response += "\n\nTraceback:\n\n%s" % gateway.format_exception()

            return http.HttpResponseServerError(mimetype='text/plain',
                content=response)

        if self.logger:
            self.logger.debug("AMF Response: %r" % response)

        # Encode the response
        try:
            stream = remoting.encode(response, strict=self.strict,
                logger=self.logger, timezone_offset=timezone_offset)
        except:
            if self.logger:
                self.logger.exception('Error encoding AMF request')

            response = ("500 Internal Server Error\n\nThe request was "
                "unable to be encoded.")

            if self.debug:
                response += "\n\nTraceback:\n\n%s" % gateway.format_exception()

            return http.HttpResponseServerError(
                mimetype='text/plain', content=response)

        buf = stream.getvalue()

        http_response = http.HttpResponse(mimetype=remoting.CONTENT_TYPE)
        http_response['Server'] = gateway.SERVER_NAME
        http_response['Content-Length'] = str(len(buf))

        http_response.write(buf)

        return http_response
