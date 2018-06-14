""" A fallback service for when a requested one is not defined. """

from appscale.api_server.constants import CallNotFound


class BaseService(object):
    """ A fallback service for when a requested one is not defined. """
    def __init__(self, service_name):
        """ Creates a new BaseService.

        Args:
            service_name: A string specifying the service name.
        """
        self.service_name = service_name

    def make_call(self, method, encoded_request, request_id):
        """ Makes the appropriate API call for a given request.

        Args:
            method: A string specifying the requested method.
            encoded_request: A binary type containing the request details.
            request_id: A string specifying the request ID.
        """
        del encoded_request, request_id
        raise CallNotFound('{}.{} does not exist'.format(self.service_name,
                                                         method))
