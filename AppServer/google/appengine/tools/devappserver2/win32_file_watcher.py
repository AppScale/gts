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
"""Monitors a directory tree for changes using win32 APIs."""


import ctypes
import os

# FindNextChangeNotification constants (defined in FileAPI.h):
FILE_NOTIFY_CHANGE_FILE_NAME = 0x00000001
FILE_NOTIFY_CHANGE_DIR_NAME = 0x00000002
FILE_NOTIFY_CHANGE_ATTRIBUTES = 0x00000004
FILE_NOTIFY_CHANGE_SIZE = 0x00000008
FILE_NOTIFY_CHANGE_LAST_WRITE = 0x00000010
FILE_NOTIFY_CHANGE_CREATION = 0x00000040
FILE_NOTIFY_CHANGE_SECURITY = 0x00000100

# WaitForSingleObject return values (defined in WinBase.h):
WAIT_OBJECT_0 = 0x00000000L
WAIT_TIMEOUT = 0x00000102L
WAIT_FAILED = 0xffffffff

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

_INTERESTING_NOTIFICATIONS = (FILE_NOTIFY_CHANGE_FILE_NAME |
                              FILE_NOTIFY_CHANGE_DIR_NAME |
                              FILE_NOTIFY_CHANGE_ATTRIBUTES |
                              FILE_NOTIFY_CHANGE_SIZE |
                              FILE_NOTIFY_CHANGE_LAST_WRITE |
                              FILE_NOTIFY_CHANGE_CREATION |
                              FILE_NOTIFY_CHANGE_SECURITY)


class Win32FileWatcher(object):
  """Monitors a directory tree for changes using inotify."""

  def __init__(self, directory):
    """Initializer for InotifyFileWatcher.

    Args:
      directory: A string representing the path to a directory that should
          be monitored for changes i.e. files and directories added, renamed,
          deleted or changed.
    """
    self._directory = os.path.abspath(directory)
    self._find_change_handle = None

  def start(self):
    """Start watching the directory for changes."""
    self._find_change_handle = (
        ctypes.windll.kernel32.FindFirstChangeNotificationA(
            self._directory,
            True,  # Recursive.
            _INTERESTING_NOTIFICATIONS))
    if self._find_change_handle == INVALID_HANDLE_VALUE:
      raise ctypes.WinError()

    if not ctypes.windll.kernel32.FindNextChangeNotification(
        self._find_change_handle):
      raise ctypes.WinError()

  def quit(self):
    """Stop watching the directory for changes."""
    ctypes.windll.kernel32.FindCloseChangeNotification(self._find_change_handle)

  def has_changes(self):
    """Returns True if the watched directory has changed since the last call.

    start() must be called before this method.

    Returns:
      Returns True if the watched directory has changed since the last call to
      has_changes or, if has_changes has never been called, since start was
      called.
    """
    found_change = False
    # Loop until no new changes are found. This prevents future calls to
    # has_changes() from returning True for changes that happened before this
    # call was made.
    while True:
      wait_result = ctypes.windll.kernel32.WaitForSingleObject(
          self._find_change_handle, 0)
      if wait_result == WAIT_OBJECT_0:
        if not ctypes.windll.kernel32.FindNextChangeNotification(
            self._find_change_handle):
          raise ctypes.WinError()
        found_change = True
        continue
      elif wait_result == WAIT_TIMEOUT:
        return found_change
      elif wait_result == WAIT_FAILED:
        raise ctypes.WinError()
      else:
        assert 'Unexpected result for WaitForSingleObject: %r' % wait_result
