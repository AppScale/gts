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



"""Convenience wrapper for starting bulkload_client.py"""


import os
import sys

sys.stderr.write("This version of bulkload_client.py has been deprecated; "
                 "please use the version at the root of your Google App "
                 "Engine SDK install.")


if not hasattr(sys, 'version_info'):
  sys.stderr.write('Very old versions of Python are not supported. Please '
                   'use version 2.5 or greater.\n')
  sys.exit(1)
version_tuple = tuple(sys.version_info[:2])
if version_tuple < (2, 4):
  sys.stderr.write('Error: Python %d.%d is not supported. Please use '
                   'version 2.5 or greater.\n' % version_tuple)
  sys.exit(1)
if version_tuple == (2, 4):
  sys.stderr.write('Warning: Python 2.4 is not supported; this program may '
                   'break. Please use version 2.5 or greater.\n')

BULKLOAD_CLIENT_PATH = 'google/appengine/tools/bulkload_client.py'

DIR_PATH = os.path.abspath(os.path.dirname(
               os.path.dirname(os.path.realpath(__file__))))

EXTRA_PATHS = [
 DIR_PATH,
 os.path.join(DIR_PATH, 'lib', 'django'),
 os.path.join(DIR_PATH, 'lib', 'webob'),
 os.path.join(DIR_PATH, 'lib', 'yaml', 'lib'),
]

if __name__ == '__main__':
  sys.path = EXTRA_PATHS + sys.path
  script_path = os.path.join(DIR_PATH, BULKLOAD_CLIENT_PATH)
  execfile(script_path, globals())
