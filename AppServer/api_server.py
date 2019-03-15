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
"""Convenience wrapper for starting an appengine tool."""



import os
import sys




sys_path = sys.path
try:
  sys.path = [os.path.dirname(__file__)] + sys.path

  import wrapper_util

finally:
  sys.path = sys_path

wrapper_util.reject_old_python_versions((2, 7))

_DIR_PATH = wrapper_util.get_dir_path(__file__, os.path.join('lib', 'ipaddr'))
_PATHS = wrapper_util.Paths(_DIR_PATH)





EXTRA_PATHS = _PATHS.v2_extra_paths


def fix_google_path():


  if 'google' in sys.modules:
    google_path = os.path.join(os.path.dirname(__file__), 'google')
    google_module = sys.modules['google']
    google_module.__path__.append(google_path)






    if not hasattr(google_module, '__file__') or not google_module.__file__:
      google_module.__file__ = os.path.join(google_path, '__init__.py')


def fix_sys_path(extra_extra_paths=()):
  """Fix the sys.path to include our extra paths.

  fix_sys_path should be called before running testbed-based unit tests so that
  third-party modules are correctly added to sys.path.
  """
  sys.path[1:1] = EXTRA_PATHS
  fix_google_path()


def _run_file(file_path, globals_):
  """Execute the given script with the passed-in globals.

  Args:
    file_path: the path to the wrapper for the given script. This will usually
      be a copy of this file.
    globals_: the global bindings to be used while executing the wrapped script.
  """
  script_name = os.path.basename(file_path)

  sys.path = (_PATHS.script_paths(script_name) +
              _PATHS.scrub_path(script_name, sys.path))

  fix_google_path()

  execfile(_PATHS.script_file(script_name), globals_)


if __name__ == '__main__':

  assert sys.version_info[0] == 2
  _run_file(__file__, globals())
