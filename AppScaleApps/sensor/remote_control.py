""" Allows for remote setting/getting of control knobs. """

import json
import webapp2

from common import constants
from settings import API_KEY

class RemoteControl(webapp2.RequestHandler):
  """ Path for setting variables for the API Checker. """
  def post(self):
    """ POST request handler for settings. 
    """
    self.response.out.write(json.dumps({'success': True}))

APP = webapp2.WSGIApplication([
  (r'/remote_control/(.*)', RemoteControl),
], debug=constants.DEBUG_ON)
