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
"""A thread-safe wrapper for the subprocess module."""

import logging
import subprocess
import sys
import threading

# Subprocess creation is not threadsafe in Python. See
# http://bugs.python.org/issue1731717.
_popen_lock = threading.Lock()

# The provided Python binary on OS X also requires _popen_lock be held while
# writing to and closing the stdin of the subprocess.
if sys.platform == 'darwin':
  _SUBPROCESS_STDIN_IS_THREAD_HOSTILE = True
else:
  _SUBPROCESS_STDIN_IS_THREAD_HOSTILE = False


def start_process(args, input_string='', env=None, cwd=None, stdout=None,
                  stderr=None):
  """Starts a subprocess like subprocess.Popen, but is threadsafe.

  The value of input_string is passed to stdin of the subprocess, which is then
  closed.

  Args:
    args: A string or sequence of strings containing the program arguments.
    input_string: A string to pass to stdin of the subprocess.
    env: A dict containing environment variables for the subprocess.
    cwd: A string containing the directory to switch to before executing the
        subprocess.
    stdout: A file descriptor, file object or subprocess.PIPE to use for the
        stdout descriptor for the subprocess.
    stderr: A file descriptor, file object or subprocess.PIPE to use for the
        stderr descriptor for the subprocess.

  Returns:
    A subprocess.Popen instance for the created subprocess.
  """
  with _popen_lock:
    logging.debug('Starting process %r with input=%r, env=%r, cwd=%r',
                  args, input_string, env, cwd)
    p = subprocess.Popen(args, env=env, cwd=cwd, stdout=stdout, stderr=stderr,
                         stdin=subprocess.PIPE)
    if _SUBPROCESS_STDIN_IS_THREAD_HOSTILE:
      p.stdin.write(input_string)
      p.stdin.close()
      p.stdin = None
  if not _SUBPROCESS_STDIN_IS_THREAD_HOSTILE:
    p.stdin.write(input_string)
    p.stdin.close()
    p.stdin = None
  return p
