import cgi
import datetime
import wsgiref.handlers

from google.appengine.ext import webapp

class MainPage(webapp.RequestHandler):
  def get(self):
    self.response.out.write('<html><body>')
    self.response.out.write('<p>Hello</p>')
    self.response.out.write('</body></html>')

    
application = webapp.WSGIApplication([
  ('/', MainPage),
], debug=True)


def main():
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
