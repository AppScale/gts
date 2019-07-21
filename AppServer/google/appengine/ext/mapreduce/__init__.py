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
















import logging
import os

_version = os.environ.get('CURRENT_VERSION_ID', '').split('.')[0]
_internal_libs = [
    'google.appengine.ext.mapreduce',
    'google.appengine._internal.mapreduce'
]

if __name__ in _internal_libs and _version != 'ah-builtin-python-bundle':
  msg = ('You should not use the mapreduce library that is bundled with the'
         ' SDK. Use the one from'
         ' https://pypi.python.org/pypi/GoogleAppEngineMapReduce instead.')
  logging.warn(msg)

