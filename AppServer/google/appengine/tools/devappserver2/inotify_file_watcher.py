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
"""Monitors a directory tree for changes using the inotify API.

See http://linux.die.net/man/7/inotify.
"""


import ctypes
import ctypes.util
import errno
import itertools
import logging
import os
import select
import struct
import sys

from google.appengine.tools.devappserver2 import watcher_common

IN_MODIFY = 0x00000002
IN_ATTRIB = 0x00000004
IN_MOVED_FROM = 0x00000040
IN_MOVED_TO = 0x00000080
IN_CREATE = 0x00000100
IN_DELETE = 0x00000200

IN_IGNORED = 0x00008000
IN_ISDIR = 0x40000000

_INOTIFY_EVENT = struct.Struct('iIII')
_INOTIFY_EVENT_SIZE = _INOTIFY_EVENT.size
_INTERESTING_INOTIFY_EVENTS = (
    IN_ATTRIB|IN_MODIFY|IN_MOVED_FROM|IN_MOVED_TO|IN_CREATE|IN_DELETE)


class InotifyFileWatcher(object):
  """Monitors a directory tree for changes using inotify."""

  _libc = None

  def __init__(self, directory):
    """Initializer for InotifyFileWatcher.

    Args:
      directory: A string representing the path to a directory that should
          be monitored for changes i.e. files and directories added, renamed,
          deleted or changed.
    """
    self._directory = os.path.abspath(directory)
    self._watch_to_directory = {}
    self._directory_to_watch_descriptor = {}
    self._directory_to_subdirs = {}
    self._inotify_events = ''
    self._inotify_fd = None
    self._inotify_poll = None


  def _remove_watch_for_path(self, path):
    logging.debug('_remove_watch_for_path(%r)', path)
    wd = self._directory_to_watch_descriptor[path]

    if InotifyFileWatcher._libc.inotify_rm_watch(self._inotify_fd, wd) < 0:
      # If the directory is deleted then the watch will removed automatically
      # and inotify_rm_watch will fail. Just log the error.
      logging.debug('inotify_rm_watch failed for %r: %d [%r]',
                    path,
                    ctypes.get_errno(),
                    errno.errorcode[ctypes.get_errno()])

    parent_path = os.path.dirname(path)
    if parent_path in self._directory_to_subdirs:
      self._directory_to_subdirs[parent_path].remove(path)

    # _directory_to_subdirs must be copied because it is mutated in the
    # recursive call.
    for subdir in frozenset(self._directory_to_subdirs[path]):
      self._remove_watch_for_path(subdir)

    del self._watch_to_directory[wd]
    del self._directory_to_watch_descriptor[path]
    del self._directory_to_subdirs[path]

  def _add_watch_for_path(self, path):
    logging.debug('_add_watch_for_path(%r)', path)

    for dirpath, directories, _ in itertools.chain(
        [(os.path.dirname(path), [os.path.basename(path)], None)],
        os.walk(path, topdown=True, followlinks=True)):
      watcher_common.remove_ignored_dirs(directories)
      for directory in directories:
        directory_path = os.path.join(dirpath, directory)
        # dirpath cannot be used as the parent directory path because it is the
        # empty string for symlinks :-(
        parent_path = os.path.dirname(directory_path)

        watch_descriptor = InotifyFileWatcher._libc.inotify_add_watch(
            self._inotify_fd,
            ctypes.create_string_buffer(directory_path),
            _INTERESTING_INOTIFY_EVENTS)
        if watch_descriptor < 0:
          if ctypes.get_errno() == errno.ENOSPC:
            logging.warning(
                'There are too many directories in your application for '
                'changes in all of them to be monitored. You may have to '
                'restart the development server to see some changes to your '
                'files.')
            return
          error = OSError('could not add watch for %r' % directory_path)
          error.errno = ctypes.get_errno()
          error.strerror = errno.errorcode[ctypes.get_errno()]
          error.filename = directory_path
          raise error

        if parent_path in self._directory_to_subdirs:
          self._directory_to_subdirs[parent_path].add(directory_path)
        self._watch_to_directory[watch_descriptor] = directory_path
        self._directory_to_watch_descriptor[directory_path] = watch_descriptor
        self._directory_to_subdirs[directory_path] = set()

  def start(self):
    """Start watching the directory for changes."""
    self._class_setup()

    self._inotify_fd = InotifyFileWatcher._libc.inotify_init()
    if self._inotify_fd < 0:
      error = OSError('failed call to inotify_init')
      error.errno = ctypes.get_errno()
      error.strerror = errno.errorcode[ctypes.get_errno()]
      raise error
    self._inotify_poll = select.poll()
    self._inotify_poll.register(self._inotify_fd, select.POLLIN)
    self._add_watch_for_path(self._directory)

  def quit(self):
    """Stop watching the directory for changes."""
    os.close(self._inotify_fd)

  def _get_changed_paths(self):
    """Return paths for changed files and directories.

    start() must be called before this method.

    Returns:
      A set of strings representing file and directory paths that have changed
      since the last call to get_changed_paths.
    """
    paths = set()
    while True:
      if not self._inotify_poll.poll(0):
        break

      self._inotify_events += os.read(self._inotify_fd, 1024)
      while len(self._inotify_events) > _INOTIFY_EVENT_SIZE:
        wd, mask, cookie, length = _INOTIFY_EVENT.unpack(
            self._inotify_events[:_INOTIFY_EVENT_SIZE])
        if len(self._inotify_events) < _INOTIFY_EVENT_SIZE + length:
          break

        name = self._inotify_events[
            _INOTIFY_EVENT_SIZE:_INOTIFY_EVENT_SIZE+length]
        name = name.rstrip('\0')

        logging.debug('wd=%s, mask=%s, cookie=%s, length=%s, name=%r',
                      wd, hex(mask), cookie, length, name)

        self._inotify_events = self._inotify_events[_INOTIFY_EVENT_SIZE+length:]

        if mask & IN_IGNORED:
          continue
        try:
          directory = self._watch_to_directory[wd]
        except KeyError:
          logging.debug('Watch deleted for watch descriptor=%d', wd)
          continue

        path = os.path.join(directory, name)
        if os.path.isdir(path) or path in self._directory_to_watch_descriptor:
          if mask & IN_DELETE:
            self._remove_watch_for_path(path)
          elif mask & IN_MOVED_FROM:
            self._remove_watch_for_path(path)
          elif mask & IN_CREATE:
            self._add_watch_for_path(path)
          elif mask & IN_MOVED_TO:
            self._add_watch_for_path(path)
        if path not in paths:
          paths.add(path)
    return paths

  def has_changes(self):
    return bool(self._get_changed_paths())

  @classmethod
  def _class_setup(cls):
    if cls._libc:
      return

    libc_name = ctypes.util.find_library('c')
    cls._libc = ctypes.CDLL(libc_name, use_errno=True)
    cls._libc.inotify_init.argtypes = []
    cls._libc.inotify_init.restype = ctypes.c_int
    cls._libc.inotify_add_watch.argtypes = [ctypes.c_int,
                                            ctypes.c_char_p,
                                            ctypes.c_uint32]
    cls._libc.inotify_add_watch.restype = ctypes.c_int
    cls._libc.inotify_rm_watch.argtypes = [ctypes.c_int,
                                           ctypes.c_int]
    cls._libc.inotify_rm_watch.restype = ctypes.c_int
