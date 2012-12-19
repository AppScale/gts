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




"""Sample Appstats Configuration.

There are four sections:

0) WSGI middleware declaration.
1) Django version declaration.
2) Configuration constants.
3) Configuration functions.

Also a section at the end for the remote_api handler.

"""


import logging
import os
import random
import re

# 0) WSGI middleware declaration.

# Only use this if you're not Django; with Django, it's easier to add
#   'google.appengine.ext.appstats.recording.AppstatsDjangoMiddleware',
# to your Django settings.py file.

# # def webapp_add_wsgi_middleware(app):
# #   from google.appengine.ext.appstats import recording
# #   app = recording.appstats_wsgi_middleware(app)
# #   return app


# 1) Django version declaration.

# If your application uses Django and requires a specific version of
# Django, uncomment the following block of three lines.  Currently
# supported values for the Django version are '0.96' (the default),
# '1.0', and '1.1'.

# # from google.appengine.dist import use_library
# # use_library('django', '1.0')
# # import django


# 2) Configuration constants.

# DEBUG: True or False.  When True, verbose messages are logged at the
# DEBUG level.  Also, this flag is causes tracebacks to be shown in
# the web UI when an exception occurs.  (Tracebacks are always logged
# at the ERROR level as well.)

appstats_DEBUG = False

# DUMP_LEVEL: -1, 0, 1 or 2.  Controls how much debug output is
# written to the logs by the internal dump() function during event
# recording.  -1 dumps nothing; 0 dumps one line of information; 1
# dumps more informat and 2 dumps the maximum amount of information.
# You would only need to change this if you were debugging the
# recording implementation.

appstats_DUMP_LEVEL = -1

# SHELL_OK: True or False.  Defaults to True in SDK, False in production.
# If True, /_ah/stats/shell brings up a UI where you can run arbitrary
# Python code.  This is like /_ah/admin/interactive, but also displays
# full Appstats details about the code you ran.

appstats_SHELL_OK = os.getenv('SERVER_SOFTWARE', '').startswith('Dev')

# DEFAULT_SCRIPT: Default script for shell window.
appstats_DEFAULT_SCRIPT = "print 'Hello, world.'"

# The following constants control the resolution and range of the
# memcache keys used to record information about individual requests.
# Two requests that are closer than KEY_DISTANCE milliseconds will be
# mapped to the same key (thus losing all information about the
# earlier of the two requests).  Up to KEY_MODULUS distinct keys are
# generated; after KEY_DISTANCE * KEY_MODULUS milliseconds the key
# values roll over.  Increasing KEY_MODULUS causes a proportional
# increase of the amount of data saved in memcache.  Increasing
# KEY_DISTANCE causes a requests during a larger timespan to be
# recorded, at the cost of increasing risk of assigning the same key
# to two adjacent requests.

appstats_KEY_DISTANCE = 100
appstats_KEY_MODULUS = 1000

# The following constants control the namespace and key values used to
# store information in memcache.  You can safely leave this alone.

appstats_KEY_NAMESPACE = '__appstats__'
appstats_KEY_PREFIX = '__appstats__'
appstats_KEY_TEMPLATE = ':%06d'
appstats_PART_SUFFIX = ':part'
appstats_FULL_SUFFIX = ':full'
appstats_LOCK_SUFFIX = '<lock>'

# Numerical limits on how much information is saved for each event.
# MAX_STACK limits the number of stack frames saved; MAX_LOCALS limits
# the number of local variables saved per stack frame.  MAX_REPR
# limits the length of the string representation of each variable
# saved; MAX_DEPTH limits the nesting depth used when computing the
# string representation of structured variables (e.g. lists of lists).

appstats_MAX_STACK = 10
appstats_MAX_LOCALS = 10
appstats_MAX_REPR = 100
appstats_MAX_DEPTH = 10

# Regular expressions.  These are matched against the 'code key' of a
# stack frame, which is a string of the form
# '<filename>:<function>:<lineno>'.  If the code key of a stack frame
# matches RE_STACK_BOTTOM, it and all remaining stack frames are
# skipped.  If the code key matches RE_STACK_SKIP, that frame is not
# saved but subsequent frames may be saved.

appstats_RE_STACK_BOTTOM = r'dev_appserver\.py'
appstats_RE_STACK_SKIP = r'recording\.py|apiproxy_stub_map\.py'

# Timeout for memcache lock management, in seconds.

appstats_LOCK_TIMEOUT = 1

# Timezone offset.  This is used to convert recorded times (which are
# all in UTC) to local time.  The default is US/Pacific winter time.

appstats_TZOFFSET = 8*3600

# URL path (sans host) leading to the stats UI.  Should match app.yaml.
# If "builtins: - appstats: on" is used, the path should be /_ah/stats.

appstats_stats_url = '/_ah/stats'

# Fraction of requests to record.  Set this to a float between 0.0
# and 1.0 to record that fraction of all requests.

appstats_RECORD_FRACTION = 1.0

# List of dicts mapping env vars to regular expressions.  Each dict
# specifies a set of filters to be 'and'ed together.  The keys are
# environment variables, the values are *match* regular expressions.
# A request is recorded if it matches all filters of at least one
# dict.  If the FILTER_LIST variable is empty, all requests are
# recorded.  Missing environment variables are considered to have
# the empty string as value.  If a regular expression starts with
# '!', the sense of the match is negated (the value should *not*
# match the expression).

appstats_FILTER_LIST = []

# DATASTORE_DETAILS: True or False. This is an experimental flag
# and is not guaranteed to be supported or work the same way in the
# future. When True, information regarding keys of entities read or
# written during various datastore operations and other related details
# are recorded. Currently the information is logged for the following
# datastore calls: Get, Put, RunQuery and Next.

appstats_DATASTORE_DETAILS = False

# CALC_RPC_COSTS: True or False. This is an experimental flag
# and is not guaranteed to be supported or work the same way in the
# future. When True, the cost and billed operations for each RPC are
# recorded and displayed in the AppStats UI. Turning this option on
# may negatively impact application performance.

appstats_CALC_RPC_COSTS = False

# 3) Configuration functions.

# should_record() can be used to record a random percentage of calls.
# The argument is the CGI or WSGI environment dict.  The default
# implementation returns True iff the request matches FILTER_LIST (see
# above) *and* random.random() < RECORD_FRACTION.

def appstats_should_record(env):
  if appstats_FILTER_LIST:
    logging.debug('FILTER_LIST: %r', appstats_FILTER_LIST)
    for filter_dict in appstats_FILTER_LIST:
      for key, regex in filter_dict.iteritems():
        negated = isinstance(regex, str) and regex.startswith('!')
        if negated:
          regex = regex[1:]
        value = env.get(key, '')
        if bool(re.match(regex, value)) == negated:
          logging.debug('No match on %r for %s=%r', regex, key, value)
          break
      else:
        logging.debug('Match on %r', filter_dict)
        break
    else:
      logging.debug('Non-empty FILTER_LIST, but no filter matches')
      return False
  if appstats_RECORD_FRACTION >= 1.0:
    return True
  return random.random() < appstats_RECORD_FRACTION

# The following functions are called by the UI code only; they don't
# affect the recorded information.

# normalize_path() takes a path and returns an 'path key'.  The path
# key is used by the UI to compute statistics for similar URLs.  If
# your application has a large or infinite URL space (e.g. each issue
# in an issue tracker might have its own numeric URL), this function
# can be used to produce more meaningful statistics.

def appstats_normalize_path(path):
  return path

# extract_key() is a lower-level function with the same purpose as
# normalize_key().  It can be used to lump different request methods
# (e.g. GET and POST) together, or conversely to use other information
# on the request object (mostly the query string) to produce a more
# fine-grained path key.  The argument is a StatsProto object; this is
# a class defined in recording.py.  Useful methods are:

#   - http_method()
#   - http_path()
#   - http_query()
#   - http_status()

# Note that the StatsProto argument is loaded only with summary
# information; this means you cannot access the request headers.

def appstats_extract_key(request):
  key = appstats_normalize_path(request.http_path())
  if request.http_method() != 'GET':
    key = '%s %s' % (request.http_method(), key)
  return key


# ########################################
# Remote_API Authentication configuration.

# See google/appengine/ext/remote_api/handler.py for more information.
# In most cases, you will not want to configure this.

# remoteapi_CUSTOM_ENVIRONMENT_AUTHENTICATION = (
#     'HTTP_X_APPENGINE_INBOUND_APPID', ['a trusted appid here'])
