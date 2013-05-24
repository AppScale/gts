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


if not hasattr(sys, 'version_info'):
  sys.stderr.write('Very old versions of Python are not supported. Please '
                   'use version 2.7.\n')
  sys.exit(1)
version_tuple = tuple(sys.version_info[:2])
if version_tuple < (2, 7):
  sys.stderr.write('Error: Python %d.%d is not supported. Please use '
                   'version 2.7.\n' % version_tuple)
  sys.exit(1)


def _get_dir_path(sibling):
  """Get a path to the directory of this script.

  By default, the canonical path (symlinks resolved) will be returned. In some
  environments the canonical directory is not sufficient because different
  parts of the SDK are referenced by symlinks, including this very module's
  file. In this case, the non-canonical path to this file's directory will be
  returned (i.e., the directory where the symlink lives, not the directory
  where it points).

  Args:
    sibling: Relative path to a sibiling of this module file. Choose a sibling
    that is potentially symlinked into the parent directory.

  Returns:
    A directory name.

  Raises:
    ValueError: If no proper path could be determined.
  """
  py_file = __file__.replace('.pyc', '.py')
  dir_paths = [os.path.abspath(os.path.dirname(os.path.realpath(py_file))),
               os.path.abspath(os.path.dirname(py_file))]
  for dir_path in dir_paths:
    sibling_path = os.path.join(dir_path, sibling)
    if os.path.exists(sibling_path):
      return dir_path
  raise ValueError('Could not determine directory that contains both, this '
                   'file and %s.' % sibling)









_DIR_PATH = _get_dir_path(os.path.join('lib', 'ipaddr'))
_SCRIPT_DIR = os.path.join(_DIR_PATH, 'google', 'appengine', 'tools')
_DEVAPPSERVER2_DIR = os.path.join(
    _DIR_PATH, 'google', 'appengine', 'tools', 'devappserver2')
_PHP_RUNTIME_DIR = os.path.join(_DEVAPPSERVER2_DIR, 'php')
_PYTHON_RUNTIME_DIR = os.path.join(_DEVAPPSERVER2_DIR, 'python')

_STUB_DEPENDENCIES = [
    os.path.join(_DIR_PATH, 'lib', 'antlr3'),
    os.path.join(_DIR_PATH, 'lib', 'fancy_urllib'),
    os.path.join(_DIR_PATH, 'lib', 'ipaddr'),
    os.path.join(_DIR_PATH, 'lib', 'yaml-3.10'),
    ]





EXTRA_PATHS = _STUB_DEPENDENCIES + [
    _DIR_PATH,

    os.path.join(_DIR_PATH, 'lib', 'simplejson'),


    os.path.join(_DIR_PATH, 'lib', 'django-1.4'),
    os.path.join(_DIR_PATH, 'lib', 'jinja2-2.6'),
    os.path.join(_DIR_PATH, 'lib', 'protorpc'),
    os.path.join(_DIR_PATH, 'lib', 'PyAMF-0.6.1'),
    os.path.join(_DIR_PATH, 'lib', 'markupsafe-0.15'),
    os.path.join(_DIR_PATH, 'lib', 'webob-1.2.3'),
    os.path.join(_DIR_PATH, 'lib', 'webapp2-2.5.2'),
    ]

_DEVAPPSERVER2_PATHS = _STUB_DEPENDENCIES + [
    _DIR_PATH,

    os.path.join(_DIR_PATH, 'lib', 'concurrent'),
    os.path.join(_DIR_PATH, 'lib', 'cherrypy'),
    os.path.join(_DIR_PATH, 'lib', 'jinja2-2.6'),
    os.path.join(_DIR_PATH, 'lib', 'webob-1.2.3'),
    os.path.join(_DIR_PATH, 'lib', 'webapp2-2.5.1'),
    ]

_PHP_RUNTIME_PATHS = [
    os.path.join(_DIR_PATH, 'lib', 'concurrent'),
    os.path.join(_DIR_PATH, 'lib', 'cherrypy'),
    os.path.join(_DIR_PATH, 'lib', 'yaml-3.10'),
    ]

_PYTHON_RUNTIME_PATHS = [
    _DIR_PATH,

    os.path.join(_DIR_PATH, 'lib', 'concurrent'),
    os.path.join(_DIR_PATH, 'lib', 'cherrypy'),
    os.path.join(_DIR_PATH, 'lib', 'fancy_urllib'),
    os.path.join(_DIR_PATH, 'lib', 'protorpc'),
    os.path.join(_DIR_PATH, 'lib', 'yaml-3.10'),
    ]


_BOOTSTAP_NAME_TO_REAL_NAME = {
    'dev_appserver.py': 'devappserver2.py',
    '_php_runtime.py': 'runtime.py',
    '_python_runtime.py': 'runtime.py',
    }

_SCRIPT_TO_DIR = {
    'dev_appserver.py': _DEVAPPSERVER2_DIR,
    '_php_runtime.py': _PHP_RUNTIME_DIR,
    '_python_runtime.py': _PYTHON_RUNTIME_DIR,
    }

_SYS_PATH_ADDITIONS = {
    'dev_appserver.py': _DEVAPPSERVER2_PATHS,
    '_php_runtime.py': _PHP_RUNTIME_PATHS,
    '_python_runtime.py': _PYTHON_RUNTIME_PATHS,
    }


def fix_sys_path(extra_extra_paths=()):
  """Fix the sys.path to include our extra paths.

  fix_sys_path should be called before running testbed-based unit tests so that
  third-party modules are correctly added to sys.path.
  """
  sys.path[1:1] = EXTRA_PATHS


def _run_file(file_path, globals_, script_dir=_SCRIPT_DIR):
  """Execute the file at the specified path with the passed-in globals."""
  script_name = os.path.basename(file_path)
  sys.path = _SYS_PATH_ADDITIONS[script_name] + sys.path







  if 'google' in sys.modules:
    del sys.modules['google']

  script_dir = _SCRIPT_TO_DIR.get(script_name, script_dir)
  script_name = _BOOTSTAP_NAME_TO_REAL_NAME.get(script_name, script_name)
  script_path = os.path.join(script_dir, script_name)
  execfile(script_path, globals_)


if __name__ == '__main__':
  _run_file(__file__, globals())
