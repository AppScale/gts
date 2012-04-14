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




"""Django database client for rdbms.

Encapsulates the logic for starting up a command line client to the database,
for use with the "dbshell" management command.
"""


from django.db import backends


class DatabaseClient(backends.BaseDatabaseClient):
  """Database client for rdbms."""

  def runshell(self):
    """Start an interactive database shell."""
    settings_dict = self.connection.settings_dict
    args = [self.executable_name]
    args = ['', settings_dict.get('INSTANCE')]
    database = settings_dict.get('NAME')
    if database:
      args.append(database)





    from google.storage.speckle.python.tool import google_sql
    google_sql.main(args)
