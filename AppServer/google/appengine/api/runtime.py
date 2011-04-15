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





"""Utilities for interacting with the Python Runtime."""







__shutdown_hook = None
__shuting_down = False


def is_shutting_down():
  """Returns true if the server is shutting down."""
  return __shuting_down


def set_shutdown_hook(hook):
  """Registers a function to be called when the server is shutting down.

  The shutdown hook will be called when the server shuts down.  Your code
  will have a short amount of time to save state and exit. The shutdown
  hook should interrupt any long running code you have, e.g. by calling
  apiproxy_stub_map.apiproxy.CancelApiCalls and/or raising an exception.

  Args:
    hook: A no-argument callable which will be called when the server is
    shutting down.

  Returns:
    The previously registered shutdown hook, or None if no hook was
    registered before.

  In some cases it may not be possible to run the shutdown hook
  before the server exits.
  """
  if hook is not None and not callable(hook):
    raise TypeError("hook must be callable, got %s" % hook.__class__)
  global __shutdown_hook
  old_hook = __shutdown_hook
  __shutdown_hook = hook
  return old_hook


def __BeginShutdown():


  global __shuting_down
  __shuting_down = True
  if __shutdown_hook:
    __shutdown_hook()
