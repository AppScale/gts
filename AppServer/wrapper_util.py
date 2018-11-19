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
"""Finds the directory and target script name for App Engine SDK scripts."""

import os
import sys


def reject_old_python_versions(minimum_version):
  """Guard against old python versions.

  Args:
    minimum_version: a tuple that indicates the minimum Python version.
  """
  minimum_version_string = '.'.join(str(x) for x in minimum_version)
  if not hasattr(sys, 'version_info'):
    sys.stderr.write('Very old versions of Python are not supported. Please '
                     'use version %s.\n' % minimum_version_string)
    sys.exit(1)
  version_tuple = tuple(sys.version_info[:2])
  if version_tuple < minimum_version:
    sys.stderr.write('Error: Python %d.%d is not supported. Please use '
                     'version %s.\n' % (version_tuple[0], version_tuple[1],
                                        minimum_version_string))
    sys.exit(1)


def get_dir_path(script_file, sibling):
  """Get a path to the directory of the script script_file.

  By default, the canonical path (symlinks resolved) will be returned. In some
  environments the canonical directory is not sufficient because different
  parts of the SDK are referenced by symlinks, including script_file.
  In this case, the non-canonical path to script_file's directory will be
  returned (i.e., the directory where the symlink lives, not the directory
  where it points).

  Args:
    script_file: The script file whose directory is wanted.
    sibling: Relative path to a sibling of script_file. Choose a sibling
    that is potentially symlinked into the parent directory.

  Returns:
    A directory name.

  Raises:
    ValueError: If no proper path could be determined.
  """
  if 'GAE_SDK_ROOT' in os.environ:
    gae_sdk_root = os.path.abspath(os.environ['GAE_SDK_ROOT'])



    os.environ['GAE_SDK_ROOT'] = gae_sdk_root
    for dir_path in [gae_sdk_root,
                     os.path.join(gae_sdk_root, 'google_appengine')]:
      if os.path.exists(os.path.join(dir_path, sibling)):
        return dir_path
    raise ValueError('GAE_SDK_ROOT %r does not refer to a valid SDK '
                     'directory' % gae_sdk_root)
  else:
    py_file = script_file.replace('.pyc', '.py')
    dir_paths = [os.path.abspath(os.path.dirname(os.path.realpath(py_file))),
                 os.path.abspath(os.path.dirname(py_file))]
    for dir_path in dir_paths:
      sibling_path = os.path.join(dir_path, sibling)
      if os.path.exists(sibling_path):
        return dir_path
    raise ValueError('Could not determine SDK root; please set GAE_SDK_ROOT '
                     'environment variable.')







class Paths(object):
  """Encapsulates the path and unwrapped script details for a wrapper script.

  Most of the attributes of this object are there so that wrapper_script_v1
  can continue to export the same global variables it historically has, in case
  any end-users are referencing those.

  Attributes:
    default_script_dir: the path where the corresponding unwrapped script will
      be found, apart from a few exceptional scripts.
  """

  def __init__(self, dir_path):
    """Make a new Paths object.

    Args:
      dir_path: the directory path where the calling script is to be found.
        This directory should have a lib subdirectory.
    """


    self.v1_extra_paths = [
        dir_path,
        os.path.join(dir_path, 'lib', 'antlr3'),
        os.path.join(dir_path, 'lib', 'django-0.96'),
        os.path.join(dir_path, 'lib', 'fancy_urllib'),
        os.path.join(dir_path, 'lib', 'ipaddr'),
        os.path.join(dir_path, 'lib', 'jinja2-2.6'),
        os.path.join(dir_path, 'lib', 'protorpc-1.0'),
        os.path.join(dir_path, 'lib', 'PyAMF'),
        os.path.join(dir_path, 'lib', 'markupsafe'),
        os.path.join(dir_path, 'lib', 'webob_0_9'),
        os.path.join(dir_path, 'lib', 'webapp2-2.5.2'),
        os.path.join(dir_path, 'lib', 'yaml', 'lib'),
        os.path.join(dir_path, 'lib', 'simplejson'),

        os.path.join(dir_path, 'lib', 'rsa'),
        os.path.join(dir_path, 'lib', 'pyasn1'),
        os.path.join(dir_path, 'lib', 'pyasn1_modules'),
    ]

    self.api_server_extra_paths = [
        os.path.join(dir_path, 'lib', 'argparse'),
    ]




    self.endpointscfg_extra_paths = [
        os.path.join(dir_path, 'lib', 'cherrypy'),
        os.path.join(dir_path, 'lib', 'concurrent'),
        os.path.join(dir_path, 'lib', 'endpoints-1.0'),
    ]


    self.oauth_client_extra_paths = [
        os.path.join(dir_path, 'lib', 'google-api-python-client'),
        os.path.join(dir_path, 'lib', 'httplib2'),
        os.path.join(dir_path, 'lib', 'python-gflags'),
    ]


    self.google_sql_extra_paths = self.oauth_client_extra_paths + [
        os.path.join(dir_path, 'lib', 'enum'),
        os.path.join(dir_path, 'lib', 'grizzled'),
        os.path.join(dir_path, 'lib', 'oauth2'),
        os.path.join(dir_path, 'lib', 'prettytable'),
        os.path.join(dir_path, 'lib', 'sqlcmd'),
    ]

    devappserver2_dir = os.path.join(
        dir_path, 'google', 'appengine', 'tools', 'devappserver2')
    php_runtime_dir = os.path.join(devappserver2_dir, 'php')
    python_runtime_dir = os.path.join(devappserver2_dir, 'python')

    stub_paths = [
        os.path.join(dir_path, 'lib', 'antlr3'),
        os.path.join(dir_path, 'lib', 'fancy_urllib'),
        os.path.join(dir_path, 'lib', 'ipaddr'),
        os.path.join(dir_path, 'lib', 'yaml-3.10'),

        os.path.join(dir_path, 'lib', 'rsa'),
        os.path.join(dir_path, 'lib', 'pyasn1'),
        os.path.join(dir_path, 'lib', 'pyasn1_modules'),
    ]





    self.v2_extra_paths = stub_paths + [
        dir_path,

        os.path.join(dir_path, 'lib', 'simplejson'),



        os.path.join(dir_path, 'lib', 'django-1.4'),
        os.path.join(dir_path, 'lib', 'endpoints-1.0'),
        os.path.join(dir_path, 'lib', 'jinja2-2.6'),
        os.path.join(dir_path, 'lib', 'protorpc-1.0'),
        os.path.join(dir_path, 'lib', 'PyAMF-0.6.1'),
        os.path.join(dir_path, 'lib', 'markupsafe-0.15'),
        os.path.join(dir_path, 'lib', 'webob-1.2.3'),
        os.path.join(dir_path, 'lib', 'webapp2-2.5.2'),
    ]

    devappserver2_paths = stub_paths + [
        dir_path,
        os.path.join(dir_path, 'lib', 'concurrent'),
        os.path.join(dir_path, 'lib', 'cherrypy'),
        os.path.join(dir_path, 'lib', 'jinja2-2.6'),
        os.path.join(dir_path, 'lib', 'webob-1.2.3'),
        os.path.join(dir_path, 'lib', 'webapp2-2.5.1'),
    ]

    php_runtime_paths = [
        dir_path,
        os.path.join(dir_path, 'lib', 'concurrent'),
        os.path.join(dir_path, 'lib', 'cherrypy'),
        os.path.join(dir_path, 'lib', 'yaml-3.10'),
    ]

    python_runtime_paths = [
        dir_path,
        os.path.join(dir_path, 'lib', 'concurrent'),
        os.path.join(dir_path, 'lib', 'cherrypy'),
        os.path.join(dir_path, 'lib', 'fancy_urllib'),
        os.path.join(dir_path, 'lib', 'protorpc-1.0'),
        os.path.join(dir_path, 'lib', 'yaml-3.10'),
    ]

    self._script_to_paths = {
        'api_server.py': self.v1_extra_paths + self.api_server_extra_paths,
        'appcfg.py': self.v1_extra_paths + self.oauth_client_extra_paths,
        'backends_conversion.py': self.v1_extra_paths,
        'bulkload_client.py': self.v1_extra_paths,
        'bulkloader.py': self.v1_extra_paths + self.oauth_client_extra_paths,
        'dev_appserver.py': devappserver2_paths,
        'download_appstats.py': self.v1_extra_paths,
        'endpointscfg.py': self.v1_extra_paths + self.endpointscfg_extra_paths,
        'gen_protorpc.py': self.v1_extra_paths,
        'google_sql.py': self.v1_extra_paths + self.google_sql_extra_paths,
        'old_dev_appserver.py': self.v1_extra_paths,
        'php_cli.py': devappserver2_paths,
        'remote_api_shell.py': self.v1_extra_paths,
        'vmboot.py': self.v1_extra_paths,
        '_php_runtime.py': php_runtime_paths,
        '_python_runtime.py': python_runtime_paths,
    }

    self._wrapper_name_to_real_name = {
        'old_dev_appserver.py': 'dev_appserver_main.py',
        'dev_appserver.py': 'devappserver2.py',
        '_php_runtime.py': 'runtime.py',
        '_python_runtime.py': 'runtime.py',
    }

    self.default_script_dir = os.path.join(
        dir_path, 'google', 'appengine', 'tools')

    self.google_sql_dir = os.path.join(
        dir_path, 'google', 'storage', 'speckle', 'python', 'tool')

    self._script_to_dir = {
        'google_sql.py': self.google_sql_dir,
        'dev_appserver.py': devappserver2_dir,
        '_php_runtime.py': php_runtime_dir,
        '_python_runtime.py': python_runtime_dir,
    }














    self._sys_paths_to_scrub = {
        'dev_appserver.py':
            [os.path.normcase(os.path.join(dir_path, 'launcher'))],
    }

  def script_paths(self, script_name):
    """Returns the sys.path prefix appropriate for this script.

    Args:
      script_name: the basename of the script, for example 'appcfg.py'.
    """
    try:
      return self._script_to_paths[script_name]
    except KeyError:
      raise KeyError('Script name %s not recognized' % script_name)

  def script_file(self, script_name):
    """Returns the absolute name of the wrapped script.

    Args:
      script_name: the basename of the script, for example 'appcfg.py'.
    """
    script_dir = self._script_to_dir.get(script_name, self.default_script_dir)
    script_name = self._wrapper_name_to_real_name.get(script_name, script_name)
    return os.path.join(script_dir, script_name)

  def scrub_path(self, script_name, paths):
    """Removes bad paths from a list of paths.

    Args:
      script_name: the basename of the script, for example 'appcfg.py'.
      paths: a list of paths

    Returns:
      The list of paths with any bad paths removed.
    """
    sys_paths_to_scrub = self._sys_paths_to_scrub.get(script_name, [])


    return [path for path in paths
            if os.path.normcase(path) not in sys_paths_to_scrub]
