""" A handler with helper functions that other handlers can extend. """

from tornado import web
from tornado.escape import json_encode
from tornado.options import options

from appscale.common.constants import HTTPCodes
from .constants import CustomHTTPError


class BaseHandler(web.RequestHandler):
  """ A handler with helper functions that other handlers can extend. """
  def authenticate(self):
    """ Ensures requests are authenticated.

    Raises:
      CustomHTTPError if the secret is invalid.
    """
    if 'AppScale-Secret' not in self.request.headers:
      message = 'A required header is missing: AppScale-Secret'
      raise CustomHTTPError(HTTPCodes.UNAUTHORIZED, message=message)

    if self.request.headers['AppScale-Secret'] != options.secret:
      raise CustomHTTPError(HTTPCodes.UNAUTHORIZED, message='Invalid secret')

  def write_error(self, status_code, **kwargs):
    """ Writes a custom JSON-based error message.

    Args:
      status_code: An integer specifying the HTTP error code.
    """
    details = {'code': status_code}
    if 'exc_info' in kwargs:
      error = kwargs['exc_info'][1]
      try:
        details.update(error.kwargs)
      except AttributeError:
        pass

    self.finish(json_encode({'error': details}))
