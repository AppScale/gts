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




"""Main script for appstats analytics."""


import email.Utils
try:
  import json
except ImportError:
  import simplejson as json
import logging
import mimetypes
import os
import re
import time
from google.appengine.ext import webapp
from google.appengine.ext.analytics import process
from google.appengine.ext.analytics import stats
from google.appengine.ext.appstats import loader
from google.appengine.ext.appstats import recording
from google.appengine.ext.appstats import ui
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util


class Cache(object):
  """Cache appstats records for better tool performance.

  Loading full Appstats records from file is time
  consuming mainly because of the overheads in converting binary
  protobuf strings to python protobuf objects. Caching the
  records can help ensure this is done only the first time the
  main page is loaded, and the overheads are avoided as the user
  navigates the tool. Note that caching is intended for the offline
  analysis case (e.g. analyzing locally downloaded files). In online
  production, local caches might not be effective as requests go to
  multiple app servers. Also, there might be issues around memcache
  getting updated periodically. Note that we store the file name
  and the time the file has been last modified to identify if the
  cache is still valid.
  """

  def __init__(self):
    """Constructor."""
    self.hascontents = False
    self.filename = None

    self.mtime = None
    self.recordlist = []

  def Reset(self):
    """Reset and delete cache contents."""
    self.hascontents = False
    self.filename = None
    self.mtime = None
    self.recordlist = []

  def IsCached(self, source, mtime):
    """Check whether data from a file is cached.

    Args:
      source: name of file being read
      mtime: last modification time of file being read

    Returns:
      A boolean: true if cached, false otherwise.
    """
    if not self.hascontents:
      return False
    if self.filename == source and self.mtime == mtime:
      return True
    else:
      return False

  def Insert(self, source, mtime, recordlist):
    """Insert records in cache.

    Args:
      source: name of file whose data is being cached.
      mtime: last modification time of file being cached.
      recordlist: list of StatsProto instances retrieved from
        file in reverse chronological order (i.e. most recent first).
    """
    self.hascontents = True
    self.filename = source
    self.mtime = mtime
    self.recordlist = recordlist


class Filter(object):
  """Returns a subset of records that meet filtering crtieria.

  While navigating the tool, developers may wish to focus on a certain
  subset of records that meet desired filters. This class is used to
  specify the desired filtering criteria. Currently, the supported filters
  are (i) by time of recording; and (ii) request latency.
  """

  url = None
  starttime = None
  endtime = None
  latency_lower = None
  latency_upper = None

  def __init__(self, url=None, starttime=None, endtime=None,
               latency_lower=None, latency_upper=None):
    """Set filtering criteria.

    Args:
      url: consider only requests corresponding to this URL.
      starttime: consider only records recorded with timestamp (in seconds)
        higher than this value. Timestamps are measured from start of recording
        of entire data source.
      endtime: consider only records recorded with timestamp (in seconds)
        lower than this value.
      latency_lower: consider only requests with latency (in milliseconds)
        greater than this value
      latency_upper: consider only requests with latency lower than this value
    """
    self.url = url
    if starttime:
      self.starttime = int(starttime)
    if endtime:
      self.endtime = int(endtime)
    if latency_lower:
      self.latency_lower = int(latency_lower)
    if latency_upper:
      self.latency_upper = int(latency_upper)
    logging.info('Filtering requests: url: %s start: %s end: %s'
                 'latency_lower: %s, latency_upper: %s',
                 url, starttime, endtime, latency_lower, latency_upper)

  def Match(self, url, timestamp, latency):
    """Check if record meets filtering criteria.

    Args:
      url: path of that http request (after normalization)
      timestamp: timestamp of record
      latency: latency of request that record pertains to.

    Returns:
      Boolean which is True if the record matches filtering criteria
      and false otherwise.
    """
    if self.url:
      if url != self.url:
        return False
    if self.starttime:
      if timestamp < self.starttime:
        return False
    if self.endtime:
      if timestamp > self.endtime:
        return False
    if self.latency_lower:
      if latency < self.latency_lower:
        return False
    if self.latency_upper:
      if latency > self.latency_upper:
        return False
    return True


cache = Cache()
mockable_open = open


class StatsPage(webapp.RequestHandler):
  """Handler for analysis page."""

  dirname = os.path.join(os.path.dirname(__file__))

  def FilterRecords(self, recordlist, recording_starttime):
    """Returns subset of records that meet filtering crtieria.

    While navigating the tool, developers may wish to focus on a certain
    subset of records that meet desired filters. Currently, the supported
    filters are (i) by time of recording; and (ii) request latency. Filter
    information is parsed from request arguments.

    Args:
      recordlist: List of raw appstats records over which filtering condition
        must be applied.
      recording_starttime: Timestamp when recording of data starts expressed
        in seconds. This is the timestamp of the earliest recorded Appstats
        data.
    Returns:
      Subset of records that meet the filtering criteria
    """
    url = self.request.get('url')
    latency_lower = self.request.get('latency_lower')
    latency_upper = self.request.get('latency_upper')
    starttime = self.request.get('starttime')
    endtime = self.request.get('endtime')
    filter_condition = Filter(url=url,
                              starttime=starttime,
                              endtime=endtime,
                              latency_lower=latency_lower,
                              latency_upper=latency_upper)
    filtered_records = []
    for record in recordlist:
      path_key = recording.config.extract_key(record)


      reltime = int(record.start_timestamp_milliseconds() * 0.001 -
                    recording_starttime)
      latency = record.duration_milliseconds()
      ismatch = filter_condition.Match(path_key, reltime, latency)
      if ismatch:
        filtered_records.append(record)
    logging.info('Original number of records: %d', len(recordlist))
    logging.info('After filtering: number of records: %d',
                 len(filtered_records))
    return filter_condition, filtered_records

  def RenderMain(self, urlstatsdict, source, recording_starttime):
    """Rendering main page of analysis page.

    Args:
      urlstatsdict: A dictionary with keys being URL paths, and values
        being URLStat objects.
      source: Source of Appstats data. Either filename if being read from
        a file or MEMCACHE if being read from memcache.
      recording_starttime: Timestamp when recording of data starts expressed
        in seconds. This is the timestamp of the earliest recorded Appstats
        data.
    """
    resptime_byfreq, intervals = process.URLFreqRespTime(urlstatsdict)
    data = {
        'resptime_byfreq': resptime_byfreq,
        'intervals': intervals,
        'source': source,
        'recordingstart': time.asctime(time.gmtime(recording_starttime)),
        }
    path = os.path.join(self.dirname, 'templates/main.html')
    self.response.out.write(template.render(path, data))

  def RenderDrill(self, url, urlstatsdict, recording_starttime, source,
                  filter_condition):
    """Rendering analysis page that drills into URL.

    Args:
      url: URL that is being drilled into.
      urlstatsdict: A dictionary with keys being URL paths, and values
        being URLStat objects.
      recording_starttime: Timestamp when recording of data starts expressed
        in seconds. This is the timestamp of the earliest recorded Appstats
        data.
      source: Source of Appstats data. Either filename if being read from
        a file or MEMCACHE if being read from memcache.
      filter_condition: Filter object that specifies filtering criteria on
        which requests must be shown.
    """
    if url in urlstatsdict:
      urlstats = urlstatsdict[url]
      drill = process.DrillURL(urlstats)
      data = {
          'url': url,
          'drill': drill,
          'first_timestamp': recording_starttime,
          'recordingstart': time.asctime(time.gmtime(recording_starttime)),
          'source': source,
          'filter_json': json.dumps(filter_condition.__dict__),
          'filter': filter_condition.__dict__,
          }
      path = os.path.join(self.dirname, 'templates/drill.html')
      self.response.out.write(template.render(path, data))

  def RenderDetail(self, url, urlstatsdict, records_bytimestamp, detail):
    """Renders detailed Appstats view of single request.

    Args:
      url: URL that is being drilled into.
      urlstatsdict: A dictionary with keys being URL paths, and values
        being URLStat objects.
      records_bytimestamp: A dictionary. Each key is the timestamp of an
        Appstats record (expressed in seconds). Each value is the
        corresponding Appstats record (RequestStatProto protobuf).
      detail: An index that can help identify which record is being
        desired.
    """
    if url in urlstatsdict:
      urlstats = urlstatsdict[url]

      revindex = -detail - 1
      ts = urlstats.urlrequestlist[revindex].timestamp
      record = records_bytimestamp[ts]
      ui.render_record(self.response, record)

  def RenderError(self, errormessage, source):
    """Render error message page.

    Args:
      errormessage: Error message to be rendered.
      source: Source of Appstats data. Either filename if being read from
        a file or MEMCACHE if being read from memcache.
    """
    data = {
        'errormessage': errormessage,
        'source': source,
        }
    path = os.path.join(self.dirname, 'templates/error.html')
    self.response.out.write(template.render(path, data))

  def RenderPklList(self, pklfiles):
    """Render directory listing of all pkl files.

    Args:
      pklfiles: A list of pklfiles in the application root directory.
    """
    data = {
        'pklfiles': pklfiles,
        }
    path = os.path.join(self.dirname, 'templates/showPklFiles.html')
    self.response.out.write(template.render(path, data))

  def ReadableTime(self, seconds):
    """Convert seconds into user-friendly time.

    The seconds elapsed since an appstats file is shown on the directory
    page. This is converted into the most appropriate combination of units
    (minute, hour or day) to make it easy for the user to read.

    Args:
      seconds: Seconds elapsed since an Appstats data file was downloaded.
    Returns:
      elapsed: Readable version of seconds elapsed.
    """
    if seconds < 60:
      if int(seconds) == 1:
        elapsed = '%d second ago' %(seconds)
      else:
        elapsed = '%d seconds ago' %(seconds)
    elif seconds < 3600:
      minutes = seconds/60
      if int(minutes) == 1:
        elapsed = '%d minute ago' %(minutes)
      else:
        elapsed = '%d minutes ago' %(minutes)
    elif seconds < 86400:
      hours = seconds/3600
      if int(hours) == 1:
        elapsed = '%d hour ago' %(hours)
      else:
        elapsed = '%d hours ago' %(hours)
    else:
      days = seconds/86400
      if int(days) == 1:
        elapsed = '%d day ago' %(days)
      else:
        elapsed = '%d days ago' %(days)
    return elapsed

  def ListPklFiles(self):
    """Create a list of available pkl files.

    Generates a directory listing of application root directory to obtain
    a list of all pkl files.

    Returns:
      pklfiles: A list of tuples one per pkl file in the application
        root directory. Each tuple contains the file name, seconds
        elapsed since last modification, and a user-friendly version of elapsed
        second information. The list is sorted by seconds elapsed, i.e. most
        recently downloaded files are listed first.
    """
    rootdir = self.GetRoot()
    files = os.listdir(rootdir)
    currtime = time.time()
    pklfiles = []
    for filename in files:
      if re.search('\.pkl$', filename):
        path = os.path.join(rootdir, filename)
        lastmodified = os.path.getmtime(path)
        elapsed_secs = currtime - lastmodified
        elapsed_text = self.ReadableTime(elapsed_secs)
        pklfiles.append((filename, elapsed_secs, elapsed_text))
    pklfiles.sort(key=lambda tuple: tuple[1])
    return pklfiles

  def GetRoot(self):
    """Determine the root directory of the application.

    Returns:
      Root directory of the application, i.e. directory that has app.yaml
      file. Returns None if it cannot locate the root directory.
    """
    rootdir = self.dirname
    tryfile = None
    while rootdir != '/':
      tryfile = os.path.join(rootdir, 'app.yaml')
      if not os.path.exists(tryfile):
        rootdir = os.path.dirname(rootdir)
      else:
        break
    if rootdir != '/':
      logging.info('Application Root directory: %s', rootdir)
      return rootdir
    else:
      if os.path.exists('/app.yaml'):
        logging.info('Application Root directory: %s', rootdir)
        return rootdir
      else:
        logging.error('No parent directory has app.yaml!')
        return None

  def ReadData(self, source):
    """Parses source option and reads appropriate data source.

    Args:
      source: Source of Appstats data. Either filename if being read from
        a file or MEMCACHE if being read from memcache.
    Returns:
      errormessage: An error message to display to the user if an error occured
        while reading data, None if no error occured.
      recordlist: A list of Appstats records in RequestStatProto protobuf format
        in reverse chronological order (i.e. most recent first).
    """
    errormessage = None
    recordlist = None
    if source == 'MEMCACHE':

      recordlist = loader.FromMemcache()
    else:
      rootdir = self.GetRoot()
      if rootdir is None:
        errormessage = 'No parent directory has app.yaml!'
        return errormessage, recordlist
      source_root = os.path.join(rootdir, source)
      try:
        outfile = mockable_open(source_root, 'rb')
      except IOError:
        logging.error('Cannot open %s', source)
        errormessage = 'Unable to open file!'
        return errormessage, recordlist
      mtime = os.path.getmtime(source_root)
      if cache.IsCached(source, mtime):
        logging.info('Using cached records from %s', source)
        recordlist = cache.recordlist
      else:
        logging.info('Reading fresh records from %s', source)
        recordlist = loader.UnpickleFromFile(outfile)
        cache.Insert(source, mtime, recordlist)
    return errormessage, recordlist

  def InitURLStats(self, recordlist):
    """Initialize data structures from appstats data.

    Args:
      recordlist: A list of Appstats records in RequestStatProto protobuf
        format in reverse chronological order (i.e. most recent first).
    Returns:
      records_bytimestamp: A dictionary. Each key is the timestamp of an
        Appstats record (expressed in seconds). Each value is the
        corresponding Appstats record (RequestStatProto protobuf).
      urlstatsdict: A dictionary with keys being URL paths, and values
        being URLStat objects.
    """
    records_bytimestamp = {}
    urlstatsdict = {}
    for record in recordlist:
      ts = record.start_timestamp_milliseconds() * 0.001
      records_bytimestamp[ts] = record
      path_key = recording.config.extract_key(record)
      if not path_key in urlstatsdict:
        urlstatsdict[path_key] = stats.URLStats(path_key)
      urlstatsdict[path_key].AddRequest(record)
    return records_bytimestamp, urlstatsdict

  def get(self):
    """Handler for statistics/diagnostics page."""
    logging.info(self.request.path)
    if not self.request.path.endswith('/'):
      querystring = self.request.query_string
      if not querystring:
        self.redirect(self.request.path + '/')
      else:
        self.redirect(self.request.path + '/?' + self.request.query_string)
      return
    if not 'source' in self.request.arguments():
      pklfiles = self.ListPklFiles()
      self.RenderPklList(pklfiles)
    else:
      source = self.request.get('source')
      logging.info('Before ReadData')
      errormessage, recordlist = self.ReadData(source)
      logging.info('After ReadData')
      if errormessage:
        self.RenderError(errormessage, source)
        return
      if not recordlist:
        self.RenderError('No records in this Appstats snapshot.', source)
        return


      recording_starttime = recordlist[-1].start_timestamp_milliseconds()
      recording_starttime *= 0.001
      filter_condition, filtered_records = self.FilterRecords(
          recordlist, recording_starttime)
      records_bytimestamp, urlstatsdict = self.InitURLStats(filtered_records)
      url = self.request.get('url')
      detail = self.request.get('detail')
      if not url and not detail:
        self.RenderMain(urlstatsdict, source, recording_starttime)
      elif not detail:
        self.RenderDrill(url, urlstatsdict, recording_starttime,
                         source, filter_condition)
      else:
        detail = int(detail)
        self.RenderDetail(url, urlstatsdict, records_bytimestamp, detail)


class LocalStaticHandler(webapp.RequestHandler):
  """Request handler to serve static files.

  Only files directory in the static subdirectory are rendered this
  way (no subdirectories).
  """

  def get(self):
    """Handler for static page."""
    here = os.path.dirname(__file__)
    fn = self.request.path
    i = fn.rfind('/')
    fn = fn[i+1:]
    fn = os.path.join(here, 'static', fn)
    ctype, _ = mimetypes.guess_type(fn)
    assert ctype and '/' in ctype, repr(ctype)
    expiry = 3600
    expiration = email.Utils.formatdate(time.time() + expiry, usegmt=True)
    fp = mockable_open(fn, 'rb')
    try:
      self.response.out.write(fp.read())
    finally:
      fp.close()
    self.response.headers['Content-type'] = ctype
    self.response.headers['Cache-Control'] = 'public, max-age=expiry'
    self.response.headers['Expires'] = expiration


URLMAP = [
    ('/stats/local/.*', LocalStaticHandler),
    ('/stats/*', StatsPage),
    ('/stats/file', ui.FileHandler),
    ('/stats/static/.*', ui.StaticHandler),
    ]

app = webapp.WSGIApplication(URLMAP, debug=True)


def main():
  util.run_bare_wsgi_app(app)


if __name__ == '__main__':
  main()
