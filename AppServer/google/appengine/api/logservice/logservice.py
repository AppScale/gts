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




"""
LogService API.

This module allows apps to flush logs and provide status messages.
"""






import os
import sys
import time

from google.appengine.api import api_base_pb
from google.appengine.api import apiproxy_stub_map
from google.appengine.api.logservice import log_service_pb
from google.appengine.runtime import apiproxy_errors


_flush_time = None
_log_buffer_lines = None
_request_id = None


AUTOFLUSH_ENABLED = True


AUTOFLUSH_EVERY_SECONDS = 10


AUTOFLUSH_EVERY_BYTES = 1024


AUTOFLUSH_EVERY_LINES = 20

def Flush():
  """Flushes log lines that are currently buffered."""
  request = log_service_pb.FlushRequest()
  response = api_base_pb.VoidProto()
  apiproxy_stub_map.MakeSyncCall('logservice', 'Flush', request, response)
  _Reset(True)

def SetStatus(status):
  """Indicates the process status."""
  request = log_service_pb.SetStatusRequest()
  request.status = status
  response = api_base_pb.VoidProto()
  apiproxy_stub_map.MakeSyncCall('logservice', 'SetStatus', request, response)

def FlushTime():
  """Returns last time that the log buffer was flushed."""
  return _flush_time

def LogBufferContents():
  """Returns the contents of the logs buffer."""
  try:
    return _LogBuffer().getvalue()
  except AttributeError:


    return ''

def LogBufferBytes():
  """Returns the size of the log buffer, in bytes."""
  return len(LogBufferContents())

def LogBufferLines():
  """Returns the number of log lines currently buffered."""
  return _log_buffer_lines

def AutoFlush(lines_emitted=0):
  """Invoked by app_logging.emit() to automatically flush logs."""
  _CheckNewRequest()
  global _log_buffer_lines, _request_id
  _log_buffer_lines += lines_emitted

  if not AUTOFLUSH_ENABLED:
    return

  if 'SERVER_ID' not in os.environ:
    return

  log_buffer_age = time.time() - FlushTime()
  if AUTOFLUSH_EVERY_SECONDS and log_buffer_age >= AUTOFLUSH_EVERY_SECONDS:
    Flush()
  elif AUTOFLUSH_EVERY_LINES and LogBufferLines() >= AUTOFLUSH_EVERY_LINES:
    Flush()
  elif AUTOFLUSH_EVERY_BYTES and LogBufferBytes() >= AUTOFLUSH_EVERY_BYTES:
    Flush()

def _LogBuffer():
  """Returns the buffer used for log messages."""
  return sys.stderr

def _CheckNewRequest():
  """Checks if a new request is being processed, and if so, clears state."""
  global _request_id
  current_request = None
  if 'REQUEST_ID_HASH' in os.environ:
    current_request = os.environ['REQUEST_ID_HASH']
  if current_request != _request_id:
    _request_id = current_request


    _Reset()

def _Reset(truncate=False):
  """Empties the contents of the log buffer and updates the flush time."""
  global _log_buffer_lines, _flush_time
  if truncate and LogBufferBytes() > 0:
    _LogBuffer().truncate(0)
  _log_buffer_lines = 0
  _flush_time = time.time()

_Reset()
