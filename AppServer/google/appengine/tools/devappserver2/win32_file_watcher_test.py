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
"""Tests for google.apphosting.tools.devappserver2.win32_file_watcher."""


import ctypes
import os
import unittest

import google
import mox

from google.appengine.tools.devappserver2 import win32_file_watcher


class WinError(Exception):
  pass


class Win32FileWatcherTest(unittest.TestCase):
  def setUp(self):
    self.mox = mox.Mox()
    ctypes.windll = self.mox.CreateMockAnything()
    ctypes.windll.kernel32 = self.mox.CreateMockAnything()
    ctypes.windll.kernel32.FindFirstChangeNotificationA = (
        self.mox.CreateMockAnything())
    ctypes.windll.kernel32.FindNextChangeNotification = (
        self.mox.CreateMockAnything())
    ctypes.windll.kernel32.WaitForSingleObject = self.mox.CreateMockAnything()
    ctypes.windll.kernel32.FindCloseChangeNotification = (
        self.mox.CreateMockAnything())
    ctypes.WinError = WinError

  def tearDown(self):
    self.mox.UnsetStubs()
    del ctypes.windll
    del ctypes.WinError

  def test_start_successful(self):
    watcher = win32_file_watcher.Win32FileWatcher('/tmp')

    ctypes.windll.kernel32.FindFirstChangeNotificationA(
        os.path.abspath('/tmp'), True,
        win32_file_watcher._INTERESTING_NOTIFICATIONS).AndReturn(5)
    ctypes.windll.kernel32.FindNextChangeNotification(5).AndReturn(True)

    self.mox.ReplayAll()
    watcher.start()
    self.mox.VerifyAll()

  def test_start_find_first_change_notification_failed(self):
    watcher = win32_file_watcher.Win32FileWatcher('/tmp')

    ctypes.windll.kernel32.FindFirstChangeNotificationA(
        os.path.abspath('/tmp'), True,
        win32_file_watcher._INTERESTING_NOTIFICATIONS).AndReturn(
            win32_file_watcher.INVALID_HANDLE_VALUE)

    self.mox.ReplayAll()
    self.assertRaises(WinError, watcher.start)
    self.mox.VerifyAll()

  def test_start_find_next_change_notification_failed(self):
    watcher = win32_file_watcher.Win32FileWatcher('/tmp')

    ctypes.windll.kernel32.FindFirstChangeNotificationA(
        os.path.abspath('/tmp'), True,
        win32_file_watcher._INTERESTING_NOTIFICATIONS).AndReturn(5)
    ctypes.windll.kernel32.FindNextChangeNotification(5).AndReturn(False)

    self.mox.ReplayAll()
    self.assertRaises(WinError,
                      watcher.start)
    self.mox.VerifyAll()

  def test_has_changes_with_changes(self):
    watcher = win32_file_watcher.Win32FileWatcher('/tmp')
    watcher._find_change_handle = 5

    ctypes.windll.kernel32.WaitForSingleObject(5, 0).AndReturn(
        win32_file_watcher.WAIT_OBJECT_0)
    ctypes.windll.kernel32.FindNextChangeNotification(5).AndReturn(True)
    ctypes.windll.kernel32.WaitForSingleObject(5, 0).AndReturn(
        win32_file_watcher.WAIT_TIMEOUT)

    self.mox.ReplayAll()
    self.assertTrue(watcher.has_changes())
    self.mox.VerifyAll()

  def test_has_changes_no_changes(self):
    watcher = win32_file_watcher.Win32FileWatcher('/tmp')
    watcher._find_change_handle = 5

    ctypes.windll.kernel32.WaitForSingleObject(5, 0).AndReturn(
        win32_file_watcher.WAIT_TIMEOUT)

    self.mox.ReplayAll()
    self.assertFalse(watcher.has_changes())
    self.mox.VerifyAll()

  def test_has_changes_wait_failed(self):
    watcher = win32_file_watcher.Win32FileWatcher('/tmp')
    watcher._find_change_handle = 5

    ctypes.windll.kernel32.WaitForSingleObject(5, 0).AndReturn(
        win32_file_watcher.WAIT_FAILED)

    self.mox.ReplayAll()
    self.assertRaises(WinError, watcher.has_changes)
    self.mox.VerifyAll()

  def test_has_changes_find_next_change_notification_failed(self):
    watcher = win32_file_watcher.Win32FileWatcher('/tmp')
    watcher._find_change_handle = 5

    ctypes.windll.kernel32.WaitForSingleObject(5, 0).AndReturn(
        win32_file_watcher.WAIT_OBJECT_0)
    ctypes.windll.kernel32.FindNextChangeNotification(5).AndReturn(False)

    self.mox.ReplayAll()
    self.assertRaises(WinError, watcher.has_changes)
    self.mox.VerifyAll()

if __name__ == '__main__':
  unittest.main()
