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




"""MySQL FIELD_TYPE Constants.

These constants represent the various column (field) types that are
supported by MySQL.
"""





from google.storage.speckle.proto import jdbc_type



from google.storage.speckle.proto.jdbc_type import *



DATETIME = jdbc_type.TIMESTAMP
ENUM = jdbc_type.VARCHAR
GEOMETRY = jdbc_type.BINARY
LONG = jdbc_type.BLOB
LONG_BLOB = jdbc_type.BLOB
MEDIUM_BLOB = jdbc_type.BLOB
SET = jdbc_type.VARCHAR
TINY_BLOB = jdbc_type.BLOB
YEAR = jdbc_type.DATE



INT24 = jdbc_type.INTEGER
LONGLONG = jdbc_type.BIGINT
NEWDECIMAL = jdbc_type.DECIMAL
SHORT = jdbc_type.INTEGER
STRING = jdbc_type.VARCHAR
TINY = jdbc_type.TINYINT
VAR_STRING = jdbc_type.VARCHAR
