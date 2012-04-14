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




"""Web-based User Interface for appstats.

This is a simple set of webapp-based request handlers that display the
collected statistics and let you drill down on the information in
various ways.

Template files are in the templates/ subdirectory.  Static files are
in the static/ subdirectory.

The templates are written to work with either Django 0.96 or Django
1.0, and most likely they also work with Django 1.1.
"""


import cgi
import email.Utils
import logging
import mimetypes
import os
import re
import sys
import time

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import _template
from google.appengine.ext.webapp import util

from google.appengine.ext.appstats import recording

DEBUG = recording.config.DEBUG


def render(tmplname, data):
  """Helper function to render a template."""
  here = os.path.dirname(__file__)
  tmpl = os.path.join(here, 'templates', tmplname)
  data['env'] = os.environ
  try:
    return _template.render(tmpl, data)
  except Exception, err:
    logging.exception('Failed to render %s', tmpl)
    return 'Problematic template %s: %s' % (tmplname, err)


class SummaryHandler(webapp.RequestHandler):
  """Request handler for the main stats page (/stats/)."""

  def get(self):
    recording.dont_record()





    if not self.request.path.endswith('/'):
      self.redirect(self.request.path + '/')
      return


    summaries = recording.load_summary_protos()


    allstats = {}
    pathstats = {}
    pivot_path_rpc = {}
    pivot_rpc_path = {}
    for index, summary in enumerate(summaries):




      path_key = recording.config.extract_key(summary)
      if path_key not in pathstats:
        pathstats[path_key] = [1, index+1]
      else:
        values = pathstats[path_key]

        values[0] += 1
        if len(values) >= 11:
          if values[-1]:
            values.append(0)
        else:
          values.append(index+1)
      if path_key not in pivot_path_rpc:
        pivot_path_rpc[path_key] = {}

      for x in summary.rpc_stats_list():
        rpc_key = x.service_call_name()
        value = x.total_amount_of_calls()
        if rpc_key in allstats:
          allstats[rpc_key] += value
        else:
          allstats[rpc_key] = value
        if rpc_key not in pivot_path_rpc[path_key]:
          pivot_path_rpc[path_key][rpc_key] = 0
        pivot_path_rpc[path_key][rpc_key] += value
        if rpc_key not in pivot_rpc_path:
          pivot_rpc_path[rpc_key] = {}
        if path_key not in pivot_rpc_path[rpc_key]:
          pivot_rpc_path[rpc_key][path_key] = 0
        pivot_rpc_path[rpc_key][path_key] += value


    allstats_by_count = []
    for k, v in allstats.iteritems():
      pivot = sorted(pivot_rpc_path[k].iteritems(),
                     key=lambda x: (-x[1], x[0]))
      allstats_by_count.append((k, v, pivot))
    allstats_by_count.sort(key=lambda x: (-x[1], x[0]))


    pathstats_by_count = []
    for path_key, values in pathstats.iteritems():
      pivot = sorted(pivot_path_rpc[path_key].iteritems(),
                     key=lambda x: (-x[1], x[0]))
      rpc_count = sum(x[1] for x in pivot)
      pathstats_by_count.append((path_key, rpc_count,
                                 values[0], values[1:], pivot))
    pathstats_by_count.sort(key=lambda x: (-x[1], -x[2], x[0]))


    data = {'requests': summaries,
            'allstats_by_count': allstats_by_count,
            'pathstats_by_count': pathstats_by_count,
            }
    self.response.out.write(render('main.html', data))


class DetailsHandler(webapp.RequestHandler):
  """Request handler for the details page (/stats/details)."""

  def get(self):
    recording.dont_record()


    time_key = self.request.get('time')
    timestamp = None
    record = None
    if time_key:
      try:
        timestamp = int(time_key) * 0.001
      except Exception:
        pass
    if timestamp:
      record = recording.load_full_proto(timestamp)


    if record is None:
      self.response.set_status(404)

      self.response.out.write(render('details.html', {}))
      return


    rpcstats_map = {}
    for rpc_stat in record.individual_stats_list():
      key = rpc_stat.service_call_name()
      count, real, api = rpcstats_map.get(key, (0, 0, 0))
      count += 1
      real += rpc_stat.duration_milliseconds()
      api += rpc_stat.api_mcycles()
      rpcstats_map[key] = (count, real, api)
    rpcstats_by_count = [
        (name, count, real, recording.mcycles_to_msecs(api))
        for name, (count, real, api) in rpcstats_map.iteritems()]
    rpcstats_by_count.sort(key=lambda x: -x[1])


    real_total = 0
    api_total_mcycles = 0
    for i, rpc_stat in enumerate(record.individual_stats_list()):
      real_total += rpc_stat.duration_milliseconds()
      api_total_mcycles += rpc_stat.api_mcycles()

    api_total = recording.mcycles_to_msecs(api_total_mcycles)

    data = {'sys': sys,
            'record': record,
            'rpcstats_by_count': rpcstats_by_count,
            'real_total': real_total,
            'api_total': api_total,
            'file_url': './file',
            }
    self.response.out.write(render('details.html', data))


class FileHandler(webapp.RequestHandler):
  """Request handler for displaying any text file in the system.

  NOTE: This gives any admin of your app full access to your source code.
  """








  def get(self):
    recording.dont_record()

    lineno = self.request.get('n')
    try:
      lineno = int(lineno)
    except:
      lineno = 0

    filename = self.request.get('f') or ''
    orig_filename = filename

    match = re.match('<path\[(\d+)\]>(.*)', filename)
    if match:
      index, tail = match.groups()
      index = int(index)
      if index < len(sys.path):
        filename = sys.path[index] + tail

    try:
      fp = open(filename)
    except IOError, err:
      self.response.out.write('<h1>IOError</h1><pre>%s</pre>' %
                              cgi.escape(str(err)))
      self.response.set_status(404)
    else:

      try:
        data = {'fp': fp,
                'filename': filename,
                'orig_filename': orig_filename,
                'lineno': lineno,
                }
        self.response.out.write(render('file.html', data))
      finally:
        fp.close()


class StaticHandler(webapp.RequestHandler):
  """Request handler to serve static files.

  Only files directory in the static subdirectory are rendered this
  way (no subdirectories).
  """

  def get(self):
    here = os.path.dirname(__file__)
    fn = self.request.path
    i = fn.rfind('/')
    fn = fn[i+1:]
    fn = os.path.join(here, 'static', fn)
    ctype, encoding = mimetypes.guess_type(fn)
    assert ctype and '/' in ctype, repr(ctype)
    expiry = 3600
    expiration = email.Utils.formatdate(time.time() + expiry, usegmt=True)
    fp = open(fn, 'rb')
    try:
      self.response.out.write(fp.read())
    finally:
      fp.close()
    self.response.headers['Content-type'] = ctype
    self.response.headers['Cache-Control'] = 'public, max-age=expiry'
    self.response.headers['Expires'] = expiration




URLMAP = [
  ('.*/details', DetailsHandler),
  ('.*/file', FileHandler),
  ('.*/static/.*', StaticHandler),
  ('.*', SummaryHandler),
  ]


class AuthCheckMiddleware(object):
  """Middleware which conducts an auth check."""

  def __init__(self, application):
    self._application = application

  def __call__(self, environ, start_response):
    if not environ.get('SERVER_SOFTWARE', '').startswith('Dev'):
      if not users.is_current_user_admin():
        if users.get_current_user() is None:
          start_response('302 Found',
                         [('Location',
                           users.create_login_url(os.getenv('PATH_INFO', '')))])
          return []
        else:
          start_response('403 Forbidden', [])
          return ['Forbidden\n']
    return self._application(environ, start_response)

app = AuthCheckMiddleware(webapp.WSGIApplication(URLMAP, debug=DEBUG))


def main():
  """Main program. Run the auth checking middleware wrapped WSGIApplication."""
  util.run_bare_wsgi_app(app)


if __name__ == '__main__':
  main()
