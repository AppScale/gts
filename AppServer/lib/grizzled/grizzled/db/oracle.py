# $Id: 9efdb91769a07b38061d1041ac0486b77f362738 $

"""
Oracle extended database driver.
"""

__docformat__ = "restructuredtext en"

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import os
import sys

from grizzled.db.base import (DBDriver, Error, Warning,
                              TableMetadata, IndexMetadata, RDBMSMetadata)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VENDOR = 'Oracle Corporation'
PRODUCT = 'Oracle'

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class OracleDriver(DBDriver):
    """DB Driver for Oracle, using the cx_Oracle DB API module."""

    def get_import(self):
        import cx_Oracle
        return cx_Oracle

    def get_display_name(self):
        return "Oracle"

    def do_connect(self,
                   host='localhost',
                   port=None,
                   user='',
                   password='',
                   database='default'):
        dbi = self.get_import()
        return dbi.connect('%s/%s@%s' % (user, password, database))

    def get_tables(self, cursor):
        cursor.execute('select lower(table_name) from all_tables')
        table_names = []
        rs = cursor.fetchone()
        while rs is not None:
            name = rs[0]
            # Skip tables with "$" in them.
            if name.find('$') < 0:
                table_names.append(name)
            rs = cursor.fetchone()

        return table_names

    def get_rdbms_metadata(self, cursor):
        cursor.execute("SELECT banner FROM v$version WHERE "
                       "banner LIKE 'Oracle%'")
        rs = cursor.fetchone()
        if rs is None:
            result = RDBMSMetadata(VENDOR, PRODUCT, 'unknown')
        else:
            result = RDBMSMetadata(VENDOR, PRODUCT, rs[0])

        return result

    def get_table_metadata(self, table, cursor):
        self._ensure_valid_table(cursor, table)
        cursor.execute("select column_name, data_type, data_length, "
                       "data_precision, data_scale, nullable, "
                       "char_col_decl_length from all_tab_columns "
                       "where lower(table_name) = '%s'" % table.lower())
        results = []
        rs = cursor.fetchone()
        while rs:
            column = rs[0]
            coltype = rs[1]
            data_length = rs[2]
            precision = rs[3]
            scale = rs[4]
            nullable = (rs[5] == 'Y')
            declared_char_length = rs[6]

            if declared_char_length:
                length = declared_char_length
            else:
                length = data_length

            results += [TableMetadata(column,
                                      coltype,
                                      length,
                                      precision,
                                      scale,
                                      nullable)]
            rs = cursor.fetchone()

        return results

    def get_index_metadata(self, table, cursor):
        self._ensure_valid_table(cursor, table)
        # First, issue a query to get the list of indexes and some
        # descriptive information.
        cursor.execute("select index_name, index_type, uniqueness, "
                       "max_extents,temporary from all_indexes where "
                       "lower(table_name) = '%s'" % table.lower())

        names = []
        description = {}
        rs = cursor.fetchone()
        while rs is not None:
            (name, index_type, unique, max_extents, temporary) = rs
            desc = 'Temporary ' if temporary == 'Y' else ''
            unique = unique.lower()
            if unique == 'nonunique':
                unique = 'non-unique'
            index_type = index_type.lower()
            desc += '%s %s index' % (index_type, unique)
            if max_extents:
                desc += ' (max_extents=%d)' % max_extents
            names.append(name)
            description[name] = desc
            rs = cursor.fetchone()

        cursor.execute("SELECT aic.index_name, aic.column_name, "
                       "aic.column_position, aic.descend, aic.table_owner, "
                       "CASE alc.constraint_type WHEN 'U' THEN 'UNIQUE' "
                       "WHEN 'P' THEN 'PRIMARY KEY' ELSE '' END "
                       "AS index_type FROM all_ind_columns aic "
                       "LEFT JOIN all_constraints alc "
                       "ON aic.index_name = alc.constraint_name AND "
                       "aic.table_name = alc.table_name AND "
                       "aic.table_owner = alc.owner "
                       "WHERE lower(aic.table_name) = '%s' "
                       "ORDER BY COLUMN_POSITION" % table.lower())
        rs = cursor.fetchone()
        columns = {}
        while rs is not None:
            index_name = rs[0]
            column_name = rs[1]
            asc = rs[3]
            cols = columns.get(index_name, [])
            cols.append('%s %s' % (column_name, asc))
            columns[index_name] = cols
            rs = cursor.fetchone()

        # Finally, assemble the result.
        results = []
        for name in names:
            cols = columns.get(name, [])
            desc = description.get(name, None)
            results += [IndexMetadata(name, cols, desc)]

        return results

