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
import cStringIO
import email.Utils
import logging
import mimetypes
import os
import re
import sys
import time
import traceback

from google.appengine.api import users
from google.appengine.ext import admin
from google.appengine.ext import webapp
from google.appengine.ext.appstats import datamodel_pb
from google.appengine.ext.appstats import recording
from google.appengine.ext.webapp import _template
from google.appengine.ext.webapp import util

DEBUG = recording.config.DEBUG


def _add_billed_ops_to_map(billed_ops_map, billed_ops_list):
  """Adds the BilledOpProto objects to the given map.

  The map is from BilledOpProto.op to the pb.

  Args:
    billed_ops_map: The map to populate.
    billed_ops_list: List containing the BilledOpProtos to add to the map.
  """
  for billed_op in billed_ops_list:
    if billed_op.op() not in billed_ops_map:
      update_me = datamodel_pb.BilledOpProto()
      update_me.set_op(billed_op.op())
      update_me.set_num_ops(0)
      billed_ops_map[billed_op.op()] = update_me
    update_me = billed_ops_map[billed_op.op()]
    update_me.set_num_ops(update_me.num_ops() + billed_op.num_ops())


def _billed_ops_to_str(billed_ops):
  """Builds a string representation of a list of BilledOpProto."""
  ops_as_strs = []
  for op in billed_ops:
    op_name = datamodel_pb.BilledOpProto.BilledOp_Name(op.op())
    ops_as_strs.append('%s:%s' % (op_name, op.num_ops()))
  return ', '.join(ops_as_strs)


def _as_percentage_of(cost_micropennies, total_cost_micropennies):
  """The cost as a percentage of the total cost, rounded to hundredths."""
  if total_cost_micropennies == 0:
    return 0
  return round((float(cost_micropennies) / float(total_cost_micropennies))
               * 100, 1)


def render(tmplname, data):
  """Helper function to render a template."""
  here = os.path.dirname(__file__)
  tmpl = os.path.join(here, 'templates', tmplname)
  data['env'] = os.environ
  data['shell_ok'] = recording.config.SHELL_OK
  data['multithread'] = os.getenv('wsgi.multithread')
  try:
    return _template.render(tmpl, data)
  except Exception, err:
    logging.exception('Failed to render %s', tmpl)
    return 'Problematic template %s: %s' % (tmplname, err)


class AllStatsInfo(object):
  """AllStats data."""

  def __init__(self, calls, cost, billed_ops):
    self.calls = calls
    self.cost = cost
    self.billed_ops = billed_ops


class PathStatsInfo(object):
  """PathStats data."""

  def __init__(self, cost, billed_ops, num_requests, most_recent_requests):
    self.cost = cost
    self.billed_ops = billed_ops
    self.num_requests = num_requests
    self.most_recent_requests = most_recent_requests


class PivotInfo(object):
  """Pivot data. The name attribute can be an rpc or a path."""

  def __init__(self, name, calls, cost, billed_ops, cost_pct):
    self.name = name
    self.calls = calls
    self.cost = cost
    self.billed_ops = billed_ops
    self.cost_pct = cost_pct

  def to_list(self):
    """Convert to a list with values in the locations expected by the ui."""
    return [self.name, self.calls, self.cost, self.billed_ops, self.cost_pct]

  @classmethod
  def from_list(cls, values):
    return cls(values[0], values[1], values[2], values[3], values[4])


class SummaryHandler(webapp.RequestHandler):
  """Request handler for the main stats page (/stats/)."""

  def get(self):
    recording.dont_record()





    if not self.request.path.endswith('/'):
      self.redirect(self.request.path + '/')
      return


    summaries = recording.load_summary_protos()

    data = self._get_summary_data(summaries)


    self.response.out.write(render('main.html', data))

  def _get_summary_data(self, summaries):
    """Extract statistics from summaries."""
    allstats = {}
    pathstats = {}


    pivot_path_rpc = {}


    pivot_rpc_path = {}

    total_cost_micropennies = 0

    summaries = sorted(summaries,
                       key=lambda x: (-x.start_timestamp_milliseconds()))
    for index, summary in enumerate(summaries):




      path_key = recording.config.extract_key(summary)
      if path_key not in pathstats:
        pathstats[path_key] = PathStatsInfo(0, {}, 1, [index+1])
      else:
        pathstats_info = pathstats[path_key]
        pathstats_info.num_requests += 1

        if len(pathstats_info.most_recent_requests) > 10:
          if pathstats_info.most_recent_requests[-1]:

            pathstats_info.most_recent_requests.append(0)
        else:
          pathstats_info.most_recent_requests.append(index+1)
      if path_key not in pivot_path_rpc:
        pivot_path_rpc[path_key] = {}

      for x in summary.rpc_stats_list():
        rpc_key = x.service_call_name()
        total_calls = x.total_amount_of_calls()


        cost_micropennies = x.total_cost_of_calls_microdollars()
        total_cost_micropennies += cost_micropennies
        pathstats[path_key].cost += cost_micropennies
        _add_billed_ops_to_map(pathstats[path_key].billed_ops,
                               x.total_billed_ops_list())
        if rpc_key in allstats:
          allstats[rpc_key].calls += total_calls
          allstats[rpc_key].cost += cost_micropennies
        else:
          allstats[rpc_key] = AllStatsInfo(total_calls, cost_micropennies, {})
        _add_billed_ops_to_map(
            allstats[rpc_key].billed_ops, x.total_billed_ops_list())
        if rpc_key not in pivot_path_rpc[path_key]:
          pivot_path_rpc[path_key][rpc_key] = PivotInfo(rpc_key, 0, 0, {}, 0)
        pivot_path_rpc[path_key][rpc_key].calls += total_calls
        pivot_path_rpc[path_key][rpc_key].cost += cost_micropennies
        _add_billed_ops_to_map(pivot_path_rpc[path_key][rpc_key].billed_ops,
                               x.total_billed_ops_list())

        if rpc_key not in pivot_rpc_path:
          pivot_rpc_path[rpc_key] = {}
        if path_key not in pivot_rpc_path[rpc_key]:

          pivot_rpc_path[rpc_key][path_key] = PivotInfo(path_key, 0, 0, {}, 0)
        pivot_rpc_path[rpc_key][path_key].calls += total_calls
        pivot_rpc_path[rpc_key][path_key].cost += cost_micropennies
        _add_billed_ops_to_map(pivot_rpc_path[rpc_key][path_key].billed_ops,
                               x.total_billed_ops_list())





    allstats_by_count = []
    for k, v in allstats.iteritems():
      for path_vals in pivot_rpc_path[k].itervalues():
        path_vals.billed_ops = _billed_ops_to_str(
            path_vals.billed_ops.itervalues())
        path_vals.cost_pct = _as_percentage_of(
            path_vals.cost, total_cost_micropennies)




      pivot = sorted(pivot_rpc_path[k].itervalues(),
                     key=lambda x: (-x.calls, x.name))
      allstats_by_count.append((
          k, v.calls, v.cost, _billed_ops_to_str(v.billed_ops.itervalues()),
          _as_percentage_of(v.cost, total_cost_micropennies),
          [x.to_list() for x in pivot]))
    allstats_by_count.sort(key=lambda x: (-x[1], x[0]))


    pathstats_by_count = []
    for path_key, pathstats_info in pathstats.iteritems():
      rpc_count = 0
      for rpc_vals in pivot_path_rpc[path_key].itervalues():
        rpc_vals.billed_ops = _billed_ops_to_str(
            rpc_vals.billed_ops.itervalues())
        rpc_vals.cost_pct = _as_percentage_of(
            rpc_vals.cost, total_cost_micropennies)
        rpc_count += rpc_vals.calls




      pivot = sorted(pivot_path_rpc[path_key].itervalues(),
                     key=lambda x: (-x.calls, x.name))
      pathstats_by_count.append((
          path_key, rpc_count, pathstats_info.cost,
          _billed_ops_to_str(pathstats_info.billed_ops.itervalues()),
          _as_percentage_of(pathstats_info.cost, total_cost_micropennies),
          pathstats_info.num_requests,
          pathstats_info.most_recent_requests,
          [x.to_list() for x in pivot]))

    pathstats_by_count.sort(key=lambda x: (-x[1], -x[5], x[0]))


    return {'requests': summaries,
            'allstats_by_count': allstats_by_count,
            'pathstats_by_count': pathstats_by_count,
            }


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
    render_record(self.response, record, './file')


def render_record(response, record, file_url=None, extra_data=None):
  """Render an appstats record in detail.

  This is a minor refactoring of DetailsHandler to support an offline
  tool for analyzing Appstats data and to allow that tool to call
  the original Appstats detailed record visualization. Since the offline
  tool may read Appstats records from other sources (e.g., a downloaded file),
  we are moving the logic of DetailsHandler related to processing and
  visualizing individual Appstats records to this function. This
  function may now be called from outside this file.

  Args:
    response: An instance of the webapp response class representing
      data to be sent in response to a web request.
    record: A RequestStatProto which contains detailed Appstats recording
      for an individual request.
    file_url: Indicates the URL to be used to follow links to files in
      application source code. A default value of 'None' indicates that
      links to files in source code will not be shown.
    extra_data: Optional dict of additional parameters for template.
  """

  data = {}
  if extra_data is not None:
    data.update(extra_data)


  if record is None:

    if extra_data is None:
      response.set_status(404)

    response.out.write(render('details.html', data))
    return

  data.update(get_details_data(record, file_url))
  response.out.write(render('details.html', data))


def get_details_data(record, file_url=None):
  """ Calculate detailed appstats data for a single request.

  Args:
    record: A RequestStatProto which contains detailed Appstats recording
      for an individual request.
    file_url: Indicates the URL to be used to follow links to files in
      application source code. A default value of 'None' indicates that
      links to files in source code will not be shown.

  Returns:
    A dictionary containing detailed appstats data for a single request.
  """

  rpcstats_map = {}
  for rpc_stat in record.individual_stats_list():
    key = rpc_stat.service_call_name()
    count, real, api, rpc_cost_micropennies, billed_ops = rpcstats_map.get(
        key, (0, 0, 0, 0, {}))
    count += 1
    real += rpc_stat.duration_milliseconds()
    api += rpc_stat.api_mcycles()


    rpc_cost_micropennies += rpc_stat.call_cost_microdollars()
    _add_billed_ops_to_map(billed_ops, rpc_stat.billed_ops_list())
    rpcstats_map[key] = (count, real, api, rpc_cost_micropennies, billed_ops)
  rpcstats_by_count = [
      (name, count, real, recording.mcycles_to_msecs(api),
       rpc_cost_micropennies, _billed_ops_to_str(billed_ops.itervalues()))
      for name, (count, real, api, rpc_cost_micropennies, billed_ops)
      in rpcstats_map.iteritems()]
  rpcstats_by_count.sort(key=lambda x: -x[1])


  real_total = 0
  api_total_mcycles = 0
  for i, rpc_stat in enumerate(record.individual_stats_list()):
    real_total += rpc_stat.duration_milliseconds()
    api_total_mcycles += rpc_stat.api_mcycles()

  api_total = recording.mcycles_to_msecs(api_total_mcycles)

  return {'sys': sys,
          'record': record,
          'rpcstats_by_count': rpcstats_by_count,
          'real_total': real_total,
          'api_total': api_total,
          'file_url': file_url,
          }


class ShellHandler(webapp.RequestHandler):
  """Request handler for interactive shell.

  This is like /_ah/admin/interactive, but with Appstats output integrated.

  GET displays a form; POST runs some code and displays its output + stats.
  """

  def _check_access(self):
    if recording.config.SHELL_OK:
      return True
    self.response.set_status(403)
    self.response.out.write('You must enable this feature by setting '
                            'appstats_SHELL_OK = True in appengine_config.py')
    return False

  def get(self):
    recording.dont_record()
    if not self._check_access():
      return
    script = self.request.get('script', recording.config.DEFAULT_SCRIPT)
    extra_data = {'is_shell': True,
                  'script': script,
                  'xsrf_token': admin.get_xsrf_token(),
                  }
    render_record(self.response, None, './file', extra_data)

  @admin.xsrf_required
  def post(self):
    recording.dont_record()
    if not self._check_access():
      return

    recorder = recording.Recorder(os.environ)
    recording.recorder_proxy.set_for_current_request(recorder)

    script = self.request.get('script', '').replace('\r\n', '\n')
    output, errors = self.execute_script(script)

    recording.recorder_proxy.clear_for_current_request()
    recorder.record_http_status(0)
    recorder.save()
    record = recorder.get_full_proto()

    extra_data = {'is_shell': True,
                  'script': script,
                  'output': output,
                  'errors': errors,
                  'time_key': int(recorder.start_timestamp * 1000),
                  'xsrf_token': admin.get_xsrf_token(),
                  }
    render_record(self.response, record, './file', extra_data)

  def execute_script(self, script):
    save_stdout = sys.stdout
    save_stderr = sys.stderr
    new_stdout = cStringIO.StringIO()
    new_stderr = cStringIO.StringIO()
    try:
      sys.stdout = new_stdout
      sys.stderr = new_stderr
      exec(script, {})
    except BaseException:
      traceback.print_exc()
    finally:
      sys.stdout = save_stdout
      sys.stderr = save_stderr
      return new_stdout.getvalue(), new_stderr.getvalue()


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
    recording.dont_record()
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
  ('.*/shell', ShellHandler),
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
