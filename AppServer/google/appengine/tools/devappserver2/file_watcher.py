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
"""Monitors a directory tree for changes."""


import sys
import types

from google.appengine.tools.devappserver2 import inotify_file_watcher
from google.appengine.tools.devappserver2 import mtime_file_watcher
from google.appengine.tools.devappserver2 import win32_file_watcher


class _MultipleFileWatcher(object):
  """A FileWatcher than can watch many directories."""

  def __init__(self, directories, use_mtime_file_watcher):
    self._file_watchers = [get_file_watcher([directory], use_mtime_file_watcher)
                           for directory in directories]

  def start(self):
    for watcher in self._file_watchers:
      watcher.start()

  def quit(self):
    for watcher in self._file_watchers:
      watcher.quit()

  def has_changes(self):
    has_changes = False
    for watcher in self._file_watchers:
      # .has_changes() returns True if there has been any changes since the
      # last call to .has_changes() so it must be called for every FileWatcher
      # to prevent spurious change notifications on subsequent calls.
      has_changes = watcher.has_changes() or has_changes
    return has_changes


def get_file_watcher(directories, use_mtime_file_watcher):
  """Returns an instance that monitors a hierarchy of directories.

  Args:
    directories: A list representing the paths of the directories to monitor.
    use_mtime_file_watcher: A bool containing whether to use mtime polling to
        monitor file changes even if other options are available on the current
        platform.

  Returns:
    A FileWatcher appropriate for the current platform. start() must be called
    before has_changes().
  """
  assert not isinstance(directories, types.StringTypes), 'expected list got str'
  if len(directories) != 1:
    return _MultipleFileWatcher(directories, use_mtime_file_watcher)

  directory = directories[0]
  if use_mtime_file_watcher:
    return mtime_file_watcher.MtimeFileWatcher(directory)
  elif sys.platform.startswith('linux'):
    return inotify_file_watcher.InotifyFileWatcher(directory)
  elif sys.platform.startswith('win'):
    return win32_file_watcher.Win32FileWatcher(directory)
  return mtime_file_watcher.MtimeFileWatcher(directory)

  # NOTE: The Darwin-specific watcher implementation (found in the deleted file
  # fsevents_file_watcher.py) was incorrect - the Mac OS X FSEvents
  # implementation does not detect changes in symlinked files or directories. It
  # also does not provide file-level change precision before Mac OS 10.7.
  #
  # It is still possible to provide an efficient implementation by watching all
  # symlinked directories and using mtime checking for symlinked files. On any
  # change in a directory, it would have to be rescanned to see if a new
  # symlinked file or directory was added. It also might be possible to use
  # kevents instead of the Carbon API to detect files changes.
