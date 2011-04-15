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




"""Relational database API stub that uses the built-in sqlite3 module.

Also see the rdbms_mysqldb and rdbms modules.
"""







import logging



try:
  import pysqlite2.dbapi2 as sqlite3

  from pysqlite2.dbapi2 import *
except ImportError:
  import sqlite3

  from sqlite3 import *



_sqlite_file = {}

def SetSqliteFile(file):
  """Sets the filename to store the sqlite stub in."""

  global _sqlite_file
  _sqlite_file = file


def connect(instance=None, database=None, **kwargs):
  logging.info('Connecting to SQLite database %r with file %r',
               database, _sqlite_file)
  if kwargs:
    logging.info('Ignoring extra kwargs: %r', kwargs)
  return sqlite3.connect(_sqlite_file)


def set_instance(instance):
  logging.info('set_instance() is a noop in dev_appserver.')
