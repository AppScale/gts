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
"""Dependencies vendoring helpers."""

import os.path
import site
import sys


PYTHON_VERSION = 'python%d.%d' % (sys.version_info[0], sys.version_info[1])


def add(path, index=1):
  """Insert site dir or virtualenv at a given index in sys.path.

  Args:
    path: relative path to a site dir or virtualenv.
    index: sys.path position to insert the site dir.

  Raises:
    ValueError: path doesn't exist.
  """
  venv_path = os.path.join(path, 'lib', PYTHON_VERSION, 'site-packages')
  if os.path.isdir(venv_path):
    site_dir = venv_path
  elif os.path.isdir(path):
    site_dir = path
  else:
    raise ValueError('virtualenv: cannot access %s: '
                     'No such virtualenv or site directory' % path)



  sys_path = sys.path[:]
  del sys.path[index:]
  site.addsitedir(site_dir)
  sys.path.extend(sys_path[index:])
