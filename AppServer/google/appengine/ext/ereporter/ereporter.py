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




"""A logging handler that records information about unique exceptions.

'Unique' in this case is defined as a given (exception class, location) tuple.
Unique exceptions are logged to the datastore with an example stacktrace and an
approximate count of occurrences, grouped by day and application version.

A cron handler, in google.appengine.ext.ereporter.report_generator, constructs
and emails a report based on the previous day's exceptions.

Example usage:

In your handler script(s), add:

  import logging
  from google.appengine.ext import ereporter

  ereporter.register_logger()

In your app.yaml, add:

  handlers:
  - url: /_ereporter/.*
    script: $PYTHON_LIB/google/appengine/ext/ereporter/report_generator.py
    login: admin

In your cron.yaml, add:

  cron:
  - description: Daily exception report
    url: /_ereporter?sender=you@yourdomain.com
    schedule: every day 00:00

This will cause a daily exception report to be generated and emailed to all
admins, with exception traces grouped by minor version. If you only want to
get exception information for the most recent minor version, add the
'versions=latest' argument to the query string. For other valid query string
arguments, see report_generator.py.

If you anticipate a lot of exception traces (for example, if you're deploying
many minor versions, each of which may have its own set of exceptions), you
can ensure that the traces from the newest minor versions get included by adding
this to your index.yaml:

  indexes:
  - kind: ExceptionRecord
    properties:
    - name: date
    - name: major_version
    - name: minor_version
      direction: desc
"""









import datetime
import logging
import os
import sha
import traceback
import urllib

from google.appengine.api import memcache
from google.appengine.api import namespace_manager
from google.appengine.ext import db
from google.appengine.ext import webapp



MAX_SIGNATURE_LENGTH = 256


class ExceptionRecord(db.Model):
  """Datastore model for a record of a unique exception."""

  signature = db.StringProperty(required=True)
  major_version = db.StringProperty(required=True)
  minor_version = db.IntegerProperty(required=True)
  date = db.DateProperty(required=True)
  count = db.IntegerProperty(required=True, default=0)


  stacktrace = db.TextProperty(required=True)
  http_method = db.TextProperty(required=True)
  url = db.TextProperty(required=True)
  handler = db.TextProperty(required=True)

  @classmethod
  def get_key_name(cls, signature, version, date=None):
    """Generates a key name for an exception record.

    Args:
      signature: A signature representing the exception and its site.
      version: The major/minor version of the app the exception occurred in.
      date: The date the exception occurred.

    Returns:
      The unique key name for this exception record.
    """
    if not date:
      date = datetime.date.today()
    return '%s@%s:%s' % (signature, date, version)


class ExceptionRecordingHandler(logging.Handler):
  """A handler that records exception data to the App Engine datastore."""

  def __init__(self, log_interval=10):
    """Constructs a new ExceptionRecordingHandler.

    Args:
      log_interval: The minimum interval at which we will log an individual
        exception. This is a per-exception timeout, so doesn't affect the
        aggregate rate of exception logging, only the rate at which we record
        ocurrences of a single exception, to prevent datastore contention.
    """
    self.log_interval = log_interval
    logging.Handler.__init__(self)

  @classmethod
  def __RelativePath(cls, path):
    """Rewrites a path to be relative to the app's root directory.

    Args:
      path: The path to rewrite.

    Returns:
      The path with the prefix removed, if that prefix matches the app's
        root directory.
    """
    cwd = os.getcwd()
    if path.startswith(cwd):
      path = path[len(cwd)+1:]
    return path

  @classmethod
  def __GetSignature(cls, exc_info):
    """Returns a unique signature string for an exception.

    Args:
      exc_info: The exc_info object for an exception.

    Returns:
      A unique signature string for the exception, consisting of fully
      qualified exception name and call site.
    """
    ex_type, unused_value, trace = exc_info
    frames = traceback.extract_tb(trace)

    fulltype = '%s.%s' % (ex_type.__module__, ex_type.__name__)
    path, line_no = frames[-1][:2]
    path = cls.__RelativePath(path)
    site = '%s:%d' % (path, line_no)
    signature = '%s@%s' % (fulltype, site)
    if len(signature) > MAX_SIGNATURE_LENGTH:
      signature = 'hash:%s' % sha.new(signature).hexdigest()

    return signature

  @classmethod
  def __GetURL(cls):
    """Returns the URL of the page currently being served.

    Returns:
      The full URL of the page currently being served.
    """
    if os.environ['SERVER_PORT'] == '80':
      scheme = 'http://'
    else:
      scheme = 'https://'
    host = os.environ['SERVER_NAME']
    script_name = urllib.quote(os.environ['SCRIPT_NAME'])
    path_info = urllib.quote(os.environ['PATH_INFO'])
    qs = os.environ.get('QUERY_STRING', '')
    if qs:
      qs = '?' + qs
    return scheme + host + script_name + path_info + qs

  def __GetFormatter(self):
    """Returns the log formatter for this handler.

    Returns:
      The log formatter to use.
    """
    if self.formatter:
      return self.formatter
    else:
      return logging._defaultFormatter

  def emit(self, record):
    """Log an error to the datastore, if applicable.

    Args:
      The logging.LogRecord object.
        See http://docs.python.org/library/logging.html#logging.LogRecord
    """
    try:
      if not record.exc_info:

        return

      signature = self.__GetSignature(record.exc_info)

      old_namespace = namespace_manager.get_namespace()
      try:
        namespace_manager.set_namespace('')


        if not memcache.add(signature, None, self.log_interval):
          return


        db.run_in_transaction_custom_retries(1, self.__EmitTx, signature,
                                             record.exc_info)
      finally:
        namespace_manager.set_namespace(old_namespace)
    except Exception:
      self.handleError(record)

  def __EmitTx(self, signature, exc_info):
    """Run in a transaction to insert or update the record for this transaction.

    Args:
      signature: The signature for this exception.
      exc_info: The exception info record.
    """
    today = datetime.date.today()
    version = os.environ['CURRENT_VERSION_ID']
    major_ver, minor_ver = version.rsplit('.', 1)
    minor_ver = int(minor_ver)
    key_name = ExceptionRecord.get_key_name(signature, version)

    exrecord = ExceptionRecord.get_by_key_name(key_name)
    if not exrecord:
      exrecord = ExceptionRecord(
          key_name=key_name,
          signature=signature,
          major_version=major_ver,
          minor_version=minor_ver,
          date=today,
          stacktrace=self.__GetFormatter().formatException(exc_info),
          http_method=os.environ['REQUEST_METHOD'],
          url=self.__GetURL(),
          handler=self.__RelativePath(os.environ['PATH_TRANSLATED']))

    exrecord.count += 1
    exrecord.put()


def register_logger(logger=None):
  if not logger:
    logger = logging.getLogger()
  handler = ExceptionRecordingHandler()
  logger.addHandler(handler)
  return handler
