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





"""The Python datastore protocol buffer definition.

Proto2 compiler expects generated file names to follow specific pattern,
which is not the case for the datastore_pb.py (should be datastore_v3_pb.py).
This file with the expected name redirects to the real legacy file.
"""


from google.appengine.datastore.datastore_pb import *
