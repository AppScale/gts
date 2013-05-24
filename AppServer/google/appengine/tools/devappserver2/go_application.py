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
"""An abstraction around the source and executable for a Go application."""


import atexit
import errno
import logging
import os
import os.path
import shutil
import sys
import subprocess
import tempfile

import google
from google.appengine.tools.devappserver2 import errors
from google.appengine.tools.devappserver2 import safe_subprocess


_SDKROOT = os.path.dirname(os.path.dirname(google.__file__))
_GOROOT = os.path.join(_SDKROOT, 'goroot')

_GAB_PATH = os.path.join(_GOROOT, 'bin', 'go-app-builder')
if sys.platform.startswith('win'):
  _GAB_PATH += '.exe'


def _rmtree(directory):
  try:
    shutil.rmtree(directory)
  except:
    pass


class BuildError(errors.Error):
  """Building the GoApplication failed."""


class GoApplication(object):
  """An abstraction around the source and executable for a Go application."""

  def __init__(self, server_configuration):
    """Initializer for Server.

    Args:
      server_configuration: An application_configuration.ServerConfiguration
          instance storing the configuration data for a server.
    """
    self._server_configuration = server_configuration
    self._go_file_to_mtime = {}
    self._extras_hash = None
    self._go_executable = None
    self._work_dir = None
    self._arch = self._get_architecture()

  @property
  def go_executable(self):
    """The path to the Go executable. None if it has not been built."""
    return self._go_executable

  def get_environment(self):
    """Return the environment that used be used to run the Go executable."""
    environ = {'GOROOT': _GOROOT,
               'PWD': self._server_configuration.application_root,
               'TZ': 'UTC'}
    if 'SYSTEMROOT' in os.environ:
      environ['SYSTEMROOT'] = os.environ['SYSTEMROOT']
    if 'USER' in os.environ:
      environ['USER'] = os.environ['USER']
    return environ

  @staticmethod
  def _get_architecture():
    architecture_map = {
        'arm': '5',
        'amd64': '6',
        '386': '8',
    }
    for platform in os.listdir(os.path.join(_GOROOT, 'pkg', 'tool')):
      # Look for 'linux_amd64', 'windows_386', etc.
      if '_' not in platform:
        continue
      architecture = platform.split('_', 1)[1]
      if architecture in architecture_map:
        return architecture_map[architecture]
    if not architecture:
      raise BuildError('no compiler found found in goroot (%s)' % _GOROOT)

  def _get_gab_args(self):
    # Go's regexp package does not implicitly anchor to the start.
    nobuild_files = '^' + str(self._server_configuration.nobuild_files)
    gab_args = [
        _GAB_PATH,
        '-app_base', self._server_configuration.application_root,
        '-arch', self._arch,
        '-binary_name', '_go_app',
        '-dynamic',
        '-goroot', _GOROOT,
        '-nobuild_files', nobuild_files,
        '-unsafe',
        '-work_dir', self._work_dir]
    if 'GOPATH' in os.environ:
      gab_args.extend(['-gopath', os.environ['GOPATH']])
    return gab_args

  def _get_go_files_to_mtime(self):
    """Returns a dict mapping all Go files to their mtimes.

    Returns:
      A dict mapping the path relative to the application root of every .go
      file in the application root, or any of its subdirectories, to the file's
      modification time.
    """
    go_file_to_mtime = {}
    for root, _, file_names in os.walk(
        self._server_configuration.application_root):
      for file_name in file_names:
        if not file_name.endswith('.go'):
          continue
        full_path = os.path.join(root, file_name)
        rel_path = os.path.relpath(
            full_path, self._server_configuration.application_root)
        if self._server_configuration.skip_files.match(rel_path):
          continue
        if self._server_configuration.nobuild_files.match(rel_path):
          continue

        try:
          go_file_to_mtime[rel_path] = os.path.getmtime(full_path)
        except OSError as e:
          # Ignore deleted files.
          if e.errno != errno.ENOENT:
            raise
    return go_file_to_mtime

  def _get_extras_hash(self):
    """Returns a hash of the names and mtimes of package dependencies.

    Returns:
      Returns a string representing a hash.

    Raises:
      BuildError: if the go application builder fails.
    """
    gab_args = self._get_gab_args()
    gab_args.append('-print_extras_hash')
    gab_args.extend(self._go_file_to_mtime)

    gab_process = safe_subprocess.start_process(gab_args,
                                                stdout=subprocess.PIPE,
                                                stderr=subprocess.PIPE,
                                                env={})
    gab_stdout, gab_stderr = gab_process.communicate()
    if gab_process.returncode:
      raise BuildError(
          '%s\n\n(Executed command: %s)' % (gab_stderr,
                                            ' '.join(gab_args)))
    else:
      return gab_stdout

  def _build(self):
    assert self._go_file_to_mtime, 'no .go files'
    logging.debug('Building Go application')

    gab_args = self._get_gab_args()
    gab_args.extend(self._go_file_to_mtime)

    gab_process = safe_subprocess.start_process(gab_args,
                                                stdout=subprocess.PIPE,
                                                stderr=subprocess.PIPE,
                                                env={})
    gab_stdout, gab_stderr = gab_process.communicate()
    if gab_process.returncode:
      raise BuildError(
          '%s\n%s\n\n(Executed command: %s)' % (gab_stdout,
                                                gab_stderr,
                                                ' '.join(gab_args)))
    else:
      logging.debug('Build succeeded:\n%s\n%s', gab_stdout, gab_stderr)
      self._go_executable = os.path.join(self._work_dir, '_go_app')

  def maybe_build(self, maybe_modified_since_last_build):
    """Builds an executable for the application if necessary.

    Args:
      maybe_modified_since_last_build: True if any files in the application root
          or the GOPATH have changed since the last call to maybe_build, False
          otherwise. This argument is used to decide whether a build is Required
          or not.

    Raises:
      BuildError: if building the executable fails for any reason.
    """
    if not self._work_dir:
      self._work_dir = tempfile.mkdtemp('appengine-go-bin')
      atexit.register(_rmtree, self._work_dir)

    if not os.path.exists(_GAB_PATH):
      # TODO: This message should be more useful i.e. point the
      # user to an SDK that does have the right components.
      raise BuildError('Required Go components are missing from the SDK.')

    if self._go_executable and not maybe_modified_since_last_build:
      return

    (self._go_file_to_mtime,
     old_go_file_to_mtime) = (self._get_go_files_to_mtime(),
                              self._go_file_to_mtime)

    if not self._go_file_to_mtime:
      raise BuildError('no .go files found in %s' %
                       self._server_configuration.application_root)

    self._extras_hash, old_extras_hash = (self._get_extras_hash(),
                                          self._extras_hash)

    if (self._go_executable and
        self._go_file_to_mtime == old_go_file_to_mtime and
        self._extras_hash == old_extras_hash):
      return

    if self._go_file_to_mtime != old_go_file_to_mtime:
      logging.debug('Rebuilding Go application due to source modification')
    elif self._extras_hash != old_extras_hash:
      logging.debug('Rebuilding Go application due to GOPATH modification')
    else:
      logging.debug('Building Go application')
    self._build()
