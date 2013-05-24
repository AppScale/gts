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
"""Tests for google.appengine.tools.devappserver2.mtime_file_watcher."""

import logging
import os
import os.path
import shutil
import tempfile
import time
import unittest

from google.appengine.tools.devappserver2 import mtime_file_watcher


class FakeThread(object):
  def start(self):
    pass


class TestMtimeFileWatcher(unittest.TestCase):
  """Tests for mtime_file_watcher.MtimeFileWatcher."""

  def setUp(self):
    self._directory = tempfile.mkdtemp()  # The watched directory
    self._junk_directory = tempfile.mkdtemp()  # A scrap directory.
    self._watcher = mtime_file_watcher.MtimeFileWatcher(self._directory)
    self._watcher._watcher_thread = FakeThread()
    logging.debug('watched directory=%r, junk directory=%r',
                  self._directory, self._junk_directory)

  def tearDown(self):
    self._watcher.quit()
    shutil.rmtree(self._directory)
    shutil.rmtree(self._junk_directory)

  def _create_file(self, relative_path):
    realpath = os.path.realpath(os.path.join(self._directory, relative_path))
    with open(realpath, 'w'):
      pass
    return realpath

  def _create_directory(self, relative_path):
    realpath = os.path.realpath(os.path.join(self._directory, relative_path))
    os.mkdir(realpath)
    return realpath

  def test_file_created(self):
    self._watcher.start()
    self._watcher._has_changed_paths()
    self._create_file('test')
    self.assertTrue(self._watcher._has_changed_paths())

  def test_file_modified(self):
    path = self._create_file('test')
    self._watcher.start()
    self._watcher._has_changed_paths()
    time.sleep(1)
    with open(path, 'w') as f:
      f.write('testing')
    self.assertTrue(self._watcher._has_changed_paths())

  def test_file_read(self):
    path = self._create_file('test')
    with open(path, 'w') as f:
      f.write('testing')
    self._watcher.start()
    self._watcher._has_changed_paths()
    with open(path, 'r') as f:
      f.read()
    # Reads should not trigger updates.
    self.assertFalse(self._watcher._has_changed_paths())

  def test_file_deleted(self):
    path = self._create_file('test')
    self._watcher.start()
    self._watcher._has_changed_paths()
    os.remove(path)
    self.assertTrue(self._watcher._has_changed_paths())

  def test_file_renamed(self):
    source = self._create_file('test')
    target = os.path.join(os.path.dirname(source), 'test2')
    self._watcher.start()
    self._watcher._has_changed_paths()
    os.rename(source, target)
    self.assertTrue(self._watcher._has_changed_paths())

  def test_create_directory(self):
    self._watcher.start()
    self._watcher._has_changed_paths()
    self._create_directory('test')
    self.assertTrue(self._watcher._has_changed_paths())

  def test_file_created_in_directory(self):
    self._create_directory('test')
    self._watcher.start()
    self._watcher._has_changed_paths()
    self._create_file('test/file')
    self.assertTrue(self._watcher._has_changed_paths())

  def test_move_directory(self):
    source = self._create_directory('test')
    target = os.path.join(os.path.dirname(source), 'test2')
    self._watcher.start()
    self._watcher._has_changed_paths()
    os.rename(source, target)
    self.assertTrue(self._watcher._has_changed_paths())

  def test_move_directory_out_of_watched(self):
    source = self._create_directory('test')
    target = os.path.join(self._junk_directory, 'test')
    self._watcher.start()
    self._watcher._has_changed_paths()
    os.rename(source, target)
    self.assertTrue(self._watcher._has_changed_paths())
    with open(os.path.join(target, 'file'), 'w'):
      pass
    # Changes to files in subdirectories that have been moved should be ignored.
    self.assertFalse(self._watcher._has_changed_paths())

  def test_move_directory_into_watched(self):
    source = os.path.join(self._junk_directory, 'source')
    target = os.path.join(self._directory, 'target')
    os.mkdir(source)
    self._watcher.start()
    self._watcher._has_changed_paths()
    os.rename(source, target)
    self.assertTrue(self._watcher._has_changed_paths())
    file_path = os.path.join(target, 'file')
    with open(file_path, 'w+'):
      pass
    self.assertTrue(self._watcher._has_changed_paths())

  def test_directory_deleted(self):
    path = self._create_directory('test')
    self._watcher.start()
    self._watcher._has_changed_paths()
    os.rmdir(path)
    self.assertTrue(self._watcher._has_changed_paths())

  @unittest.skipUnless(hasattr(os, 'symlink'), 'requires os.symlink')
  def test_symlink(self):
    sym_target = os.path.join(self._directory, 'test')
    os.mkdir(os.path.join(self._junk_directory, 'subdir'))
    self._watcher.start()
    self._watcher._has_changed_paths()

    # Check that an added symlinked directory is reported.
    os.symlink(self._junk_directory, sym_target)
    self.assertTrue(self._watcher._has_changed_paths())

    # Check that a file added to the symlinked directory is reported.
    with open(os.path.join(self._junk_directory, 'file1'), 'w'):
      pass
    self.assertTrue(self._watcher._has_changed_paths())

    # Check that a removed symlinked directory is reported.
    os.remove(sym_target)
    self.assertTrue(self._watcher._has_changed_paths())

    # Check that a file added to the removed symlinked directory is *not*
    # reported.
    with open(os.path.join(self._junk_directory, 'subdir', 'file2'), 'w'):
      pass
    self.assertFalse(self._watcher._has_changed_paths())

  def test_too_many_files(self):
    self._watcher.start()
    self._watcher._has_changed_paths()

    for i in range(10001):
      self._create_file('file%d' % i)
    self.assertTrue(self._watcher._has_changed_paths())

  @unittest.skipUnless(hasattr(os, 'symlink'), 'requires os.symlink')
  def test_symlink_loop(self):
    self._watcher.start()
    self._watcher._has_changed_paths()

    for i in range(1000):
      self._create_file('file%d' % i)

    for i in range(11):
      os.symlink(self._directory, os.path.join(self._directory, 'test%d' % i))
    self.assertTrue(self._watcher._has_changed_paths())


if __name__ == '__main__':
  unittest.main()
