""" A  Base Handler for Backup and Recovery related handlers. """

import json
import logging
import webapp2

from common.constants import HTTP_DENIED

class BaseHandler(webapp2.RequestHandler):
   def error_out(self, reason):
    """ Sets the error code and error reason.

     Args:
       reason: The reason for erroring out.
    """
    logging.error(reason)
    self.response.set_status(HTTP_DENIED)
    json_result = {"success": False, "reason": reason}
    self.response.write(json.dumps(json_result) )
