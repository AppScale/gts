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
"""Common functionality for file watchers."""


# Directories that we should not watch at all.
_IGNORED_DIRS = ('.git', '.hg', '.svn')


def remove_ignored_dirs(dirs):
  """Remove directories from dirs that should not be watched."""
  for d in _IGNORED_DIRS:
    if d in dirs:
      dirs.remove(d)
