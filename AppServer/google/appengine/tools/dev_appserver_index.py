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




"""Utilities for generating and updating index.yaml."""







from google.appengine.api import apiproxy_stub_map
from google.appengine.datastore.datastore_stub_index import *

def SetupIndexes(unused_app_id, unused_root_path):
  apiproxy_stub_map.apiproxy.GetStub('datastore_v3')._SetupIndexes()
