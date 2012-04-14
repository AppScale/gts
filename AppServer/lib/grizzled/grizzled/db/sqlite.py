# $Id: 8066a5bbef6962141ae539bef06493250cbeab57 $

"""
SQLite3 extended database driver.
"""

__docformat__ = "restructuredtext en"

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import os
import sys
import re

from grizzled.db.base import (DBDriver, Error, Warning, TableMetadata,
                              IndexMetadata, RDBMSMetadata)

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class SQLite3Driver(DBDriver):
    """DB Driver for SQLite, using the pysqlite DB API module."""

    def get_import(self):
        import sqlite3
        return sqlite3

    def get_display_name(self):
        return "SQLite3"

    def do_connect(self,
                   host=None,
                   port=None,
                   user='',
                   password='',
                   database='default'):
        dbi = self.get_import()
        return dbi.connect(database=database, isolation_level=None)

    def get_rdbms_metadata(self, cursor):
        import sqlite3
        return RDBMSMetadata('SQLite', 'SQLite 3', sqlite3.sqlite_version)

    def get_tables(self, cursor):
        cursor.execute("select name from sqlite_master where type = 'table'")
        table_names = []
        rs = cursor.fetchone()
        while rs is not None:
            table_names += [rs[0]]
            rs = cursor.fetchone()

        return table_names

    def get_table_metadata(self, table, cursor):
        self._ensure_valid_table(cursor, table)

        # The table_info pragma returns results looking something like this:
        #
        # cid name            type              notnull dflt_value pk
        # --- --------------- ----------------- ------- ---------- --
        # 0   id              integer           99      NULL       1
        # 1   action_time     datetime          99      NULL       0
        # 2   user_id         integer           99      NULL       0
        # 3   content_type_id integer           0       NULL       0
        # 4   object_id       text              0       NULL       0
        # 5   object_repr     varchar(200)      99      NULL       0
        # 6   action_flag     smallint unsigned 99      NULL       0
        # 7   change_message  text              99      NULL       0

        cursor.execute('PRAGMA table_info(%s)' % table)
        rs = cursor.fetchone()
        result = []

        char_field_re = re.compile(r'(varchar|char)\((\d+)\)')
        while rs is not None:
            (id, name, type, not_null, default_value, is_primary) = rs
            m = char_field_re.match(type)
            if m:
                type = m.group(1)
                try:
                    max_char_size = int(m.group(2))
                except ValueError:
                    log.error('Bad number in "%s" type for column "%s"' %
                              (type, name))
            else:
                max_char_size = 0

            data = TableMetadata(name, type, max_char_size, 0, 0, not not_null)
            result += [data]

            rs = cursor.fetchone()

        return result

    def get_index_metadata(self, table, cursor):
        self._ensure_valid_table(cursor, table)

        # First, get the list of indexes for the table, using the appropriate
        # pragma. The pragma returns output like this:
        #
        # seq name    unique
        # --- ------- ------
        # 0   id        0
        # 1   name      0
        # 2   address   0

        result = []

        cursor.execute("PRAGMA index_list('%s')" % table)
        indexes = []
        rs = cursor.fetchone()
        while rs is not None:
            indexes += [(rs[1], rs[2])]
            rs = cursor.fetchone()

        # Now, get the data about each index, using another pragma. This
        # pragma returns data like this:
        #
        # seqno cid name
        # ----- --- ---------------
        # 0     3   content_type_id

        for name, unique in indexes:
            cursor.execute("PRAGMA index_info('%s')" % name)
            rs = cursor.fetchone()
            columns = []
            while rs is not None:
                columns += [rs[2]]
                rs = cursor.fetchone()

            description = 'UNIQUE' if unique else ''
            result += [IndexMetadata(name, columns, description)]

        return result
