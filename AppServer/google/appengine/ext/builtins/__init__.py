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




"""Repository for all builtin handlers information.

On initialization, this file generates a list of builtin handlers that have
associated app.yaml information.  This file can then be called to read that
information and make it available.
"""












import logging
import os



DEFAULT_DIR = os.path.join(os.path.dirname(__file__))
HANDLER_DIR = None



AVAILABLE_BUILTINS = None


INCLUDE_FILENAME = 'include.yaml'


class InvalidBuiltinName(Exception):
  """Raised whenever a builtin handler name is specified that is not found."""


def reset_builtins_dir():
  """Public method for resetting builtins directory to default."""
  set_builtins_dir(DEFAULT_DIR)


def set_builtins_dir(path):
  """Sets the appropriate path for testing and reinitializes the module."""
  global HANDLER_DIR, AVAILABLE_BUILTINS
  HANDLER_DIR = path
  AVAILABLE_BUILTINS = []
  _initialize_builtins()


def _initialize_builtins():
  """Scan the immediate subdirectories of the builtins module.

  Encountered subdirectories with an app.yaml file are added to
  AVAILABLE_BUILTINS.
  """
  for filename in os.listdir(HANDLER_DIR):
    if os.path.isfile(_get_yaml_path(filename)):
      AVAILABLE_BUILTINS.append(filename)


def _get_yaml_path(builtin_name):
  """Return expected path to a builtin handler's yaml file without error check.
  """
  return os.path.join(HANDLER_DIR, builtin_name, INCLUDE_FILENAME)


def get_yaml_path(builtin_name):
  """Returns the full path to a yaml file by giving the builtin module's name.

  Args:
    builtin_name: single word name of builtin handler

  Raises:
    ValueError: if handler does not exist in expected directory

  Returns:
    the absolute path to a valid builtin handler include.yaml file
  """
  if builtin_name not in AVAILABLE_BUILTINS:
    raise InvalidBuiltinName('%s is not the name of a valid builtin handler.\n'
                             'Available handlers are: %s' % (
                             builtin_name, ', '.join(AVAILABLE_BUILTINS)))
  return _get_yaml_path(builtin_name)


set_builtins_dir(DEFAULT_DIR)
