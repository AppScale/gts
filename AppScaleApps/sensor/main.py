""" Replies with basic information. """

import json
import os
import sys

# Include these paths to get webapp2.
sys.path.append(os.path.join(os.path.dirname(__file__), "../../AppServer/lib/webob-1.2.3"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../../AppServer/lib/webapp2-2.5.2/"))
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
