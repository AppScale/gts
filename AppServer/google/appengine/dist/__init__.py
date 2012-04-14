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




"""Specify the modules for which a stub exists."""






__all__ = [

    'ftplib',
    'httplib',
    'neo_cgi',
    'py_imp',
    'select',
    'socket',
    'subprocess',
    'tempfile',

    'fix_paths',
    'use_library',
    ]

from google.appengine.dist import _library

fix_paths = _library.fix_paths
use_library = _library.use_library
