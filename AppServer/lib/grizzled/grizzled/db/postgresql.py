# $Id: f485c4e2802f66973d04d5047ee9d3e5cfd249ce $

"""
PostgreSQL extended database driver.
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
# Constants
# ---------------------------------------------------------------------------

VENDOR  = 'PostgreSQL Global Development Group'
PRODUCT = 'PostgreSQL'

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class PostgreSQLDriver(DBDriver):
    """DB Driver for PostgreSQL, using the psycopg2 DB API module."""

    TYPE_RE = re.compile('([a-z ]+)(\([0-9]+\))?')

    def get_import(self):
        import psycopg2
        return psycopg2

    def get_display_name(self):
        return "PostgreSQL"

    def do_connect(self,
                   host='localhost',
                   port=None,
                   user='',
                   password='',
                   database='default'):
        dbi = self.get_import()
        dsn = 'host=%s dbname=%s user=%s password=%s' %\
            (host, database, user, password)
        return dbi.connect(dsn=dsn)

    def get_rdbms_metadata(self, cursor):
        cursor.execute('SELECT version()')
        rs = cursor.fetchone()
        if rs is None:
            result = RDBMSMetadata(VENDOR, PRODUCT, 'unknown')
        else:
            result = RDBMSMetadata(VENDOR, PRODUCT, rs[0])

        return result

    def get_table_metadata(self, table, cursor):
        self._ensure_valid_table(cursor, table)
        sel = """\
        SELECT a.attname, pg_catalog.format_type(a.atttypid, a.atttypmod),
                    (SELECT substring(d.adsrc for 128)
                     FROM pg_catalog.pg_attrdef d
                     WHERE d.adrelid = a.attrelid AND
                     d.adnum = a.attnum AND a.atthasdef) AS DEFAULT,
                    a.attnotnull,
                    a.attnum,
                    a.attrelid as table_oid
             FROM pg_catalog.pg_attribute a
             WHERE a.attrelid =
             (SELECT c.oid FROM pg_catalog.pg_class c
             LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
             WHERE (pg_table_is_visible(c.oid)) AND c.relname = '%s'
             AND c.relkind in ('r','v'))
             AND a.attnum > 0
             AND NOT a.attisdropped
             ORDER BY a.attnum"""

        cursor.execute(sel % table)
        rs = cursor.fetchone()
        results = []
        while rs is not None:
            column = rs[0]
            coltype = rs[1]
            null = not rs[3]

            match = self.TYPE_RE.match(coltype)
            if match:
                coltype = match.group(1)
                size = match.group(2)
                if size:
                    size = size[1:-1]
                if 'char' in coltype:
                    max_char_size = size
                    precision = None
                else:
                    max_char_size = None
                    precision = size

            data = TableMetadata(column,
                                 coltype,
                                 max_char_size,
                                 precision,
                                 0,
                                 null)
            results += [data]
            rs = cursor.fetchone()

        return results

    def get_index_metadata(self, table, cursor):
        self._ensure_valid_table(cursor, table)
        # First, issue one query to get the list of indexes for the table.
        index_names = self.__get_index_names(table, cursor)

        # Now we need two more queries: One to get the columns in the
        # index and another to get descriptive information.
        results = []
        for name in index_names:
            columns = self.__get_index_columns(name, cursor)
            desc = self.__get_index_description(name, cursor)
            results += [IndexMetadata(name, columns, desc)]

        return results

    def get_tables(self, cursor):

        sel = "SELECT tablename FROM pg_tables " \
              "WHERE tablename NOT LIKE 'pg_%' AND tablename NOT LIKE 'sql\_%'"
        cursor.execute(sel)
        table_names = []
        rs = cursor.fetchone()
        while rs is not None:
            table_names += [rs[0]]
            rs = cursor.fetchone()

        return table_names

    def __get_index_names(self, table, cursor):
        # Adapted from the pgsql command "\d indexname", PostgreSQL 8.
        # (Invoking the pgsql command with -E shows the issued SQL.)

        sel = "SELECT n.nspname, c.relname as \"IndexName\", c2.relname " \
              "FROM pg_catalog.pg_class c " \
              "JOIN pg_catalog.pg_index i ON i.indexrelid = c.oid " \
              "JOIN pg_catalog.pg_class c2 ON i.indrelid = c2.oid " \
              "LEFT JOIN pg_catalog.pg_user u ON u.usesysid = c.relowner " \
              "LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace " \
              "WHERE c.relkind IN ('i','') " \
              "AND n.nspname NOT IN ('pg_catalog', 'pg_toast') " \
              "AND pg_catalog.pg_table_is_visible(c.oid) " \
              "AND c2.relname = '%s'" % table.lower()

        cursor.execute(sel)
        index_names = []
        rs = cursor.fetchone()
        while rs is not None:
            index_names += [rs[1]]
            rs = cursor.fetchone()

        return index_names

    def __get_index_columns(self, index_name, cursor):
        # Adapted from the pgsql command "\d indexname", PostgreSQL 8.
        # (Invoking the pgsql command with -E shows the issued SQL.)

        sel = "SELECT a.attname, " \
              "pg_catalog.format_type(a.atttypid, a.atttypmod), " \
              "a.attnotnull " \
              "FROM pg_catalog.pg_attribute a, pg_catalog.pg_index i " \
              "WHERE a.attrelid in " \
              " (SELECT c.oid FROM pg_catalog.pg_class c " \
              "LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace " \
              " WHERE pg_catalog.pg_table_is_visible(c.oid) " \
              "AND c.relname ~ '^(%s)$') " \
              "AND a.attnum > 0 AND NOT a.attisdropped " \
              "AND a.attrelid = i.indexrelid " \
              "ORDER BY a.attnum" % index_name
        cursor.execute(sel)
        columns = []
        rs = cursor.fetchone()
        while rs is not None:
            columns += [rs[0]]
            rs = cursor.fetchone()

        return columns

    def __get_index_description(self, index_name, cursor):
        sel = "SELECT i.indisunique, i.indisprimary, i.indisclustered, " \
              "a.amname, c2.relname, " \
              "pg_catalog.pg_get_expr(i.indpred, i.indrelid, true) " \
              "FROM pg_catalog.pg_index i, pg_catalog.pg_class c, " \
              "pg_catalog.pg_class c2, pg_catalog.pg_am a " \
              "WHERE i.indexrelid = c.oid AND c.relname ~ '^(%s)$' " \
              "AND c.relam = a.oid AND i.indrelid = c2.oid" % index_name
        cursor.execute(sel)
        desc = ''
        rs = cursor.fetchone()
        if rs is not None:
            if str(rs[1]) == "True":
                desc += "(PRIMARY) "

            if str(rs[0]) == "True":
                desc += "Unique"
            else:
                desc += "Non-unique"

            if str(rs[2]) == "True":
                desc += ", clustered"
            else:
                desc += ", non-clustered"

            if rs[3] is not None:
                desc += " %s" % rs[3]

            desc += ' index'

        if desc == '':
            desc = None

        return desc
