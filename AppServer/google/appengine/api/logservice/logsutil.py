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




"""Utility methods for working with logs."""


import os
import time



REQUEST_LOG_ID = 'REQUEST_LOG_ID'


def RequestID():
  """Returns the ID of the current request assigned by App Engine."""
  return os.environ.get(REQUEST_LOG_ID, None)


def ParseLogEntry(entry):
  """Parses a single log entry emitted by app_logging.AppLogsHandler.

  Parses a log entry of the form LOG <level> <timestamp> <message> where the
  level is in the range [0, 4]. If the entry is not of that form, take the whole
  entry to be the message. Null characters in the entry are replaced by
  newlines.

  Args:
    entry: The log entry to parse.

  Returns:
    A (timestamp, level, message) tuple.
  """
  split = entry.split(' ', 3)
  if len(split) == 4 and split[0] == 'LOG':
    level = split[1]
    timestamp = split[2]
    message = split[3]
    try:
      message = str(message)
      timestamp = int(timestamp)
      level = int(level)
    except ValueError:
      pass
    else:
      if 0 <= level <= 4:
        return timestamp, level, message.replace('\0', '\n')
  usec = int(time.time() * 1e6)
  return usec, 3, entry.replace('\0', '\n')


def ParseLogs(logs):
  """Parses a str containing newline separated log entries.

  Parses a series of log entries in the form LOG <level> <timestamp> <message>
  where the level is in the range [0, 4].  Null characters in the entry are
  replaced by newlines.

  Args:
    logs: A string containing the log entries.

  Returns:
    A list of (timestamp, level, message) tuples.
  """
  return [ParseLogEntry(line) for line in logs.split('\n') if line]
