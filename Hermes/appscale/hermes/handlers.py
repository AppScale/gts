""" Handlers for accepting HTTP requests. """

from tornado.web import RequestHandler


class Respond404Handler(RequestHandler):
  """
  This class is aimed to stub unavailable route.
  Hermes master has some extra routes which are not available on slaves,
  also Hermes stats can work in lightweight or verbose mode and verbose
  mode has extra routes.
  This handlers is configured with a reason why specific resource
  is not available on the instance of Hermes.
  """

  def initialize(self, reason):
    self.reason = reason

  def get(self):
    self.set_status(404, self.reason)
