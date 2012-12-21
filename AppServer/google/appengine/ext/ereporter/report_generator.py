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




"""Generates and emails daily exception reports.

See google/appengine/ext/ereporter/__init__.py for usage details.

Valid query string arguments to the report_generator script include:
delete:   Set to 'false' to prevent deletion of exception records from the
          datastore after sending a report. Defaults to 'true'.
debug:    Set to 'true' to return the report in the response instead of
          emailing it.
date:     The date to generate the report for, in yyyy-mm-dd format. Defaults to
          yesterday's date. Useful for debugging.
max_results: Maximum number of entries to include in a report.
sender:   The email address to use as the sender. Must be an administrator.
to:       If specified, send reports to this address. If not specified, all
          admins are sent the report.
versions: 'all' to report on all minor versions, or 'latest' for the latest.
"""









import datetime
import itertools
import os
import re
from xml.sax import saxutils

from google.appengine.api import namespace_manager
from google.appengine.api import mail
from google.appengine.ext import db
from google.appengine.ext import ereporter
from google.appengine.ext import webapp
from google.appengine.ext.webapp import _template
from google.appengine.ext.webapp.util import run_wsgi_app


def isTrue(val):
  """Determines if a textual value represents 'true'.

  Args:
    val: A string, which may be 'true', 'yes', 't', '1' to indicate True.
  Returns:
    True or False
  """
  val = val.lower()
  return val == 'true' or val == 't' or val == '1' or val == 'yes'


class ReportGenerator(webapp.RequestHandler):
  """Handler class to generate and email an exception report."""

  DEFAULT_MAX_RESULTS = 100

  def __init__(self, *args, **kwargs):
    super(ReportGenerator, self).__init__(*args, **kwargs)


    self.send_mail = mail.send_mail
    self.send_mail_to_admins = mail.send_mail_to_admins

  def GetQuery(self, order=None):
    """Creates a query object that will retrieve the appropriate exceptions.

    Returns:
      A query to retrieve the exceptions required.
    """
    q = ereporter.ExceptionRecord.all()
    q.filter('date =', self.yesterday)
    q.filter('major_version =', self.major_version)
    if self.version_filter.lower() == 'latest':
      q.filter('minor_version =', self.minor_version)
    if order:
      q.order(order)
    return q

  def GenerateReport(self, exceptions):
    """Generates an HTML exception report.

    Args:
      exceptions: A list of ExceptionRecord objects. This argument will be
        modified by this function.
    Returns:
      An HTML exception report.
    """

    exceptions.sort(key=lambda e: (e.minor_version, -e.count))
    versions = [(minor, list(excs)) for minor, excs
                in itertools.groupby(exceptions, lambda e: e.minor_version)]

    template_values = {
        'version_filter': self.version_filter,
        'version_count': len(versions),

        'exception_count': sum(len(excs) for _, excs in versions),

        'occurrence_count': sum(y.count for x in versions for y in x[1]),
        'app_id': self.app_id,
        'major_version': self.major_version,
        'date': self.yesterday,
        'versions': versions,
    }
    path = os.path.join(os.path.dirname(__file__), 'templates', 'report.html')
    return _template.render(path, template_values)

  def SendReport(self, report):
    """Emails an exception report.

    Args:
      report: A string containing the report to send.
    """
    subject = ('Daily exception report for app "%s", major version "%s"'
               % (self.app_id, self.major_version))
    report_text = saxutils.unescape(re.sub('<[^>]+>', '', report))
    mail_args = {
        'sender': self.sender,
        'subject': subject,
        'body': report_text,
        'html': report,
    }
    if self.to:
      mail_args['to'] = self.to
      self.send_mail(**mail_args)
    else:
      self.send_mail_to_admins(**mail_args)

  def get(self):
    self.version_filter = self.request.GET.get('versions', 'all')
    self.sender = self.request.GET['sender']
    self.to = self.request.GET.get('to', None)
    report_date = self.request.GET.get('date', None)
    if report_date:
      self.yesterday = datetime.date(*[int(x) for x in report_date.split('-')])
    else:
      self.yesterday = datetime.date.today() - datetime.timedelta(days=1)
    self.app_id = os.environ['APPLICATION_ID']
    version = os.environ['CURRENT_VERSION_ID']
    self.major_version, self.minor_version = version.rsplit('.', 1)
    self.minor_version = int(self.minor_version)
    self.max_results = int(self.request.GET.get('max_results',
                                                self.DEFAULT_MAX_RESULTS))
    self.debug = isTrue(self.request.GET.get('debug', 'false'))
    self.delete = isTrue(self.request.GET.get('delete', 'true'))

    namespace_manager.set_namespace('')
    try:
      exceptions = self.GetQuery(order='-minor_version').fetch(self.max_results)
    except db.NeedIndexError:

      exceptions = self.GetQuery().fetch(self.max_results)

    if exceptions:
      report = self.GenerateReport(exceptions)
      if self.debug:
        self.response.out.write(report)
      else:
        self.SendReport(report)


      if self.delete:
        db.delete(exceptions)


application = webapp.WSGIApplication([('.*', ReportGenerator)])


def main():
  run_wsgi_app(application)


if __name__ == '__main__':
  main()
