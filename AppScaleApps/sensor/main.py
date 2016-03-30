""" Replies with basic information. """

import json
import webapp2

from common import constants

class Home(webapp2.RequestHandler):
  """ Path for seeing if the API Checker app is up. """
  def get(self):
    """ GET request request handler which returns text to notify 
    caller it is up. 
    """
    self.response.out.write(json.dumps({'status': 'up'}))

  def post(self):
    """ POST request request handler which returns text to notify 
    caller it is up. 
    """
    self.response.out.write(json.dumps({'status': 'up'}))

APP = webapp2.WSGIApplication([
  (r'/', Home),
], debug=constants.DEBUG_MODE)
