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
"""Monitors a directory tree for changes using mtime polling."""

import os
import threading
import warnings


class MtimeFileWatcher(object):
  """Monitors a directory tree for changes using mtime polling."""

  def __init__(self, directory):
    self._directory = directory
    self._quit_event = threading.Event()
    self._filename_to_mtime = None
    self._has_changes = False
    self._has_changes_lock = threading.Lock()
    self._watcher_thread = threading.Thread(target=self._watch_changes)
    self._watcher_thread.daemon = True

  def start(self):
    """Start watching a directory for changes."""
    self._watcher_thread.start()

  def quit(self):
    """Stop watching a directory for changes."""
    self._quit_event.set()

  def has_changes(self):
    """Returns True if the watched directory has changed since the last call.

    start() must be called before this method.

    Returns:
      Returns True if the watched directory has changed since the last call to
      has_changes or, if has_changes has never been called, since start was
      called.
    """
    with self._has_changes_lock:
      has_changes = self._has_changes
      self._has_changes = False
    return has_changes

  def _watch_changes(self):
    while not self._quit_event.wait(1):
      self._check_for_changes()

  def _check_for_changes(self):
    if self._has_changed_paths():
      with self._has_changes_lock:
        self._has_changes = True

  def _has_changed_paths(self):
    self._filename_to_mtime, old_filename_to_mtime = (
        self._generate_filename_to_mtime(), self._filename_to_mtime)
    return (old_filename_to_mtime is not None and
            self._filename_to_mtime != old_filename_to_mtime)

  def _generate_filename_to_mtime(self):
    filename_to_mtime = {}
    num_files = 0
    for dirname, dirnames, filenames in os.walk(self._directory,
                                                followlinks=True):
      for filename in filenames + dirnames:
        if num_files == 10000:
          warnings.warn(
              'There are too many files in your application for '
              'changes in all of them to be monitored. You may have to '
              'restart the development server to see some changes to your '
              'files.')
          return filename_to_mtime
        num_files += 1
        path = os.path.join(dirname, filename)
        try:
          mtime = os.path.getmtime(path)
        except (IOError, OSError):
          pass
        else:
          filename_to_mtime[path] = mtime
    return filename_to_mtime
