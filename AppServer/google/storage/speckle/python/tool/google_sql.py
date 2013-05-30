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




"""Command line client for Google SQL Service.

This module makes use of the sqlcmd Python library (with some minor
modifications to support alternate commands and syntax), and defines the
following classes:

  DatabaseConfig: A small container object to pass around database configuration
    settings, like the Google SQL instance ID and database name.  The sqlcmd
    APIs don't allow for extra, database specific configuration variables, so
    we combine the instance ID with the database name, and pass this object as
    the value for database.

  GoogleSqlDriver: Grizzled DB Driver for Google SQL Service. sqlcmd makes use
    of the Grizzled Python library to handle database connectivity, and we
    provide an appropriate driver for connecting to a Google SQL instance.

  GoogleSqlCmd: A subclass of the sqlcmd.SQLCmd class, which is the main class
    of the application.  It overrides a few pieces of the parent class to change
    some UI elements, command syntax, and support for additional commands.
"""


import logging
import optparse
import os
import sys




from google.storage.speckle.python.api import rdbms_googleapi

from grizzled import db
from grizzled.db import mysql
import prettytable
import sqlcmd
from sqlcmd import config


logging.basicConfig(level=logging.WARNING)
sqlcmd.log = logging.getLogger('google_sql')


sqlcmd.DEFAULT_CONFIG_DIR = os.path.join(os.environ.get('HOME', os.getcwd()),
                                         '.googlesql')

sqlcmd.RC_FILE = os.path.join(sqlcmd.DEFAULT_CONFIG_DIR, 'config')
sqlcmd.HISTORY_FILE_FORMAT = os.path.join(sqlcmd.DEFAULT_CONFIG_DIR, '%s.hist')
sqlcmd.INTRO = 'Google SQL Client\n\nType "help" or "?" for help.\n'

DEFAULT_ENCODING = 'utf-8'
USAGE = '%prog [options] instance [database]'


class DatabaseConfig(object):
  """A small configuration object used to pass around database settings.

  Attributes:
    instance: The Google SQL instance ID.
    name: The database name to use.
    oauth_credentials_path: A location to use for oauth credentials storage
      instead of the default
  """

  def __init__(self, instance, name=None, oauth_credentials_path=None):
    self.instance = instance
    self.name = name
    self.oauth_credentials_path = oauth_credentials_path

  def __str__(self):
    result = self.instance
    if self.name:
      result = '%s|%s' % (result, self.name)
    return result


class GoogleSqlDriver(mysql.MySQLDriver):
  """Grizzled DB Driver for Google SQL Service."""

  NAME = 'googlesql'



  def get_import(self):
    return rdbms_googleapi

  def get_display_name(self):
    return 'Google SQL'


  def do_connect(self, host, port, user, password, database):
    """Connect to the actual underlying database, using the driver.

    Args:
      host: The host where the database lives.
      port: The TCP port to use when connecting. (UNUSED)
      user: The user to use when connecting.
      password: The password to use when connecting.
      database: A DatabaseConfig instance containing the instance id and
          database name.

    Returns:
      The DB API Connection object.
    """
    dbi = self.get_import()
    return dbi.connect(
        host, database.instance, database=database.name, user=user,
        password=password,
        oauth_credentials_path=database.oauth_credentials_path)


class GoogleSqlCmd(sqlcmd.SQLCmd):
  """The SQLCmd command interpreter for Google SQL."""

  sqlcmd.SQLCmd.MAIN_PROMPT = 'sql> '
  sqlcmd.SQLCmd.CONTINUATION_PROMPT = '  -> '




  sqlcmd.SQLCmd.NO_SEMI_NEEDED.update(
      ['about', 'connect', 'desc', 'describe', 'echo', 'exit', 'h', 'hist',
       'history', 'load', 'quit', 'run', 'set', 'show', 'var', 'vars'])



  for method in [x for x in dir(sqlcmd.SQLCmd) if x.startswith('do_dot_')]:
    setattr(sqlcmd.SQLCmd, method.replace('dot_', ''), getattr(
        sqlcmd.SQLCmd, method))
    delattr(sqlcmd.SQLCmd, method)



  def __init__(self, *args, **kwargs):
    sqlcmd.SQLCmd.__init__(self, *args, **kwargs)
    self.prompt = sqlcmd.SQLCmd.MAIN_PROMPT
    self.output_encoding = DEFAULT_ENCODING

  def set_output_encoding(self, encoding):
    self.output_encoding = encoding

  def do_quit(self, args):
    """Quit the google_sql.  Same as exit."""
    return self.do_exit(args)

  def _BuildTable(self, cursor):
    """Builds an output PrettyTable from the results in the given cursor."""
    if not cursor.description:
      return None

    column_names = [column[0] for column in cursor.description]
    table = prettytable.PrettyTable(column_names)
    rows = cursor.fetchall()
    if not rows:
      return table


    for i, col in enumerate(rows[0]):
      table.set_field_align(
          column_names[i], isinstance(col, basestring) and 'l' or 'r')

    for row in rows:
      table.add_row(row)
    return table

  def _SQLCmd__handle_select(self, args, cursor, command='select'):
    """Overrides SQLCmd.__handle_select to display output with prettytable."""
    self._SQLCmd__exec_SQL(cursor, command, args)
    table = self._BuildTable(cursor)
    if table:
      output = table.get_string()
      if isinstance(output, unicode):
        print output.encode(self.output_encoding)
      else:
        print output


def _CreateConfigDir():
  """Creates the sqlcmd config directory if necessary."""
  directory = sqlcmd.DEFAULT_CONFIG_DIR
  if not os.access(directory, os.R_OK | os.W_OK | os.X_OK):
    old_umask = os.umask(077)
    os.makedirs(sqlcmd.DEFAULT_CONFIG_DIR)
    os.umask(old_umask)


def main(argv):
  parser = optparse.OptionParser(usage=USAGE)
  parser.add_option('-e', '--output_encoding', dest='output_encoding',
                    default=DEFAULT_ENCODING,
                    help='Output encoding. Defaults to %s.' % DEFAULT_ENCODING)
  parser.add_option('--oauth_credentials_path', dest='oauth_credentials_path',
                    default=None, help=optparse.SUPPRESS_HELP)

  (options, args) = parser.parse_args(argv[1:])

  if len(args) < 1 or len(args) > 2:
    parser.print_help(sys.stderr)
    sys.exit(1)

  instance = args[0]


  instance_alias = instance.replace(':', '#')
  database = None
  if len(args) == 2:
    database = args[1]


  _CreateConfigDir()




  database = DatabaseConfig(instance, database, options.oauth_credentials_path)
  db.add_driver(GoogleSqlDriver.NAME, GoogleSqlDriver)
  sql_cmd_config = config.SQLCmdConfig(None)
  sql_cmd_config.add('__googlesql__', instance_alias, None, None, database,
                     GoogleSqlDriver.NAME, None, None)
  sql_cmd = GoogleSqlCmd(sql_cmd_config)
  sql_cmd.set_output_encoding(options.output_encoding)
  sql_cmd.set_database(instance_alias)
  sql_cmd.cmdloop()


if __name__ == '__main__':
  main(sys.argv)
