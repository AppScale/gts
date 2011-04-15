#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#




"""Handler library for inbound Mail API.

Contains handlers to help with receiving mail.

  InboundMailHandler: Has helper method for easily setting up
    email recievers.
"""









from google.appengine.api import mail
from google.appengine.ext import webapp


MAIL_HANDLER_URL_PATTERN = '/_ah/mail/.+'


class InboundMailHandler(webapp.RequestHandler):
  """Base class for inbound mail handlers.

  Example:

    # Sub-class overrides receive method.
    class HelloReceiver(InboundMailHandler):

      def receive(self, mail_message):
        logging.info('Received greeting from %s: %s' % (mail_message.sender,
                                                        mail_message.body))


    # Map mail handler to appliction.
    application = webapp.WSGIApplication([
        HelloReceiver.mapping(),
    ])
  """

  def post(self):
    """Transforms body to email request."""
    self.receive(mail.InboundEmailMessage(self.request.body))

  def receive(self, mail_message):
    """Receive an email message.

    Override this method to implement an email receiver.

    Args:
      mail_message: InboundEmailMessage instance representing received
        email.
    """
    pass

  @classmethod
  def mapping(cls):
    """Convenience method to map handler class to application.

    Returns:
      Mapping from email URL to inbound mail handler class.
    """
    return MAIL_HANDLER_URL_PATTERN, cls
