# $Id: f25618704b7ebe12c191cc1a51055c26db731b85 $

"""
Gadfly extended database driver.
"""

__docformat__ = "restructuredtext en"

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import os
import sys

from grizzled.db.base import (Cursor, DB, DBDriver, Error, Warning,
                              TableMetadata, IndexMetadata, RDBMSMetadata)

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class GadflyCursor(Cursor):
    def __init__(self, real_cursor, driver):
        self.real_cursor = real_cursor
        self.driver = driver

    @property
    def rowcount(self):
        total = len(self.real_cursor.fetchall())
        self.real_cursor.reset_results()
        return total

    @property
    def description(self):
        return self.real_cursor.description

    def close(self):
        try:
            self.real_cursor.close()
        except:
            raise Error(sys.exc_info()[1])

    def execute(self, statement, parameters=None):
        try:
            if parameters:
                result = self.real_cursor.execute(statement, parameters)
            else:
                result = self.real_cursor.execute(statement)
            return result
        except:
            raise Error(sys.exc_info()[1])

    def executemany(self, statement, *parameters):
        try:
            return self.real_cursor.executemany(statement, *parameters)
        except:
            raise Error(sys.exc_info()[1])

    def fetchall(self):
        try:
            return self.real_cursor.fetchall()
        except:
            raise Error(sys.exc_info()[1])

    def fetchone(self):
        try:
            return self.real_cursor.fetchone()
        except:
            s = sys.exc_info()[1]
            if (type(s) == str) and (s.startswith('no more')):
                return None
            raise Error(s)

    def fetchmany(self, n):
        try:
            return self.real_cursor.fetchmany(n)
        except:
            s = sys.exc_info()[1]
            if (type(s) == str) and (s.startswith('no more')):
                return None
            raise Error(s)

class GadflyDB(DB):
    def __init__(self, db, driver):
        DB.__init__(self, db, driver)
        self.__db = db
        self.__driver = driver

    def cursor(self):
        return Cursor(GadflyCursor(self.__db.cursor(), self.__driver),
                      self.__driver)

class GadflyDriver(DBDriver):
    """DB Driver for Gadfly, a pure Python RDBMS"""

    def __init__(self):
        gadfly = self.get_import()
        gadfly.error = Exception()

    def get_import(self):
        import gadfly
        return gadfly

    def get_display_name(self):
        return "Gadfly"

    def connect(self,
                host=None,
                port=None,
                user='',
                password='',
                database='default'):
        gadfly = self.get_import()
        directory = os.path.dirname(database)
        database = os.path.basename(database)
        if database.endswith('.gfd'):
            database = database[:-4]

        try:
            g = gadfly.gadfly()
            g.startup(database, directory)
            return GadflyDB(g, self)
        except IOError:
            raise Error(sys.exc_info()[1])

    def get_tables(self, cursor):
        cursor.execute('SELECT table_name FROM __table_names__ '
                       'WHERE is_view = 0')
        table_names = []
        for row in cursor.fetchall():
            table_names += [row[0]]

        return table_names

    def get_rdbms_metadata(self, cursor):
        import gadfly
        version = '.'.join([str(i) for i in gadfly.version_info])
        return RDBMSMetadata('gadfly', 'gadfly', version)

    def get_table_metadata(self, table, cursor):
        self._ensure_valid_table(cursor, table)

        cursor.execute("SELECT column_name FROM __columns__ "
                       "WHERE table_name = '%s'" % table.upper())
        result = []
        column_names = []
        for row in cursor.fetchall():
            result += [TableMetadata(row[0], 'object', None, None, None, True)]
        return result

    def get_index_metadata(self, table, cursor):
        self._ensure_valid_table(cursor, table)

        cursor.execute("SELECT is_unique, index_name FROM __indices__ "
                       "WHERE table_name = '%s'" % table.upper())
        indexes = []
        result = []
        for row in cursor.fetchall():
            indexes.append(row)

        for unique, index_name in indexes:
            cursor.execute("SELECT column_name FROM __indexcols__ "
                           "WHERE index_name = '%s'" % index_name)
            cols = []
            for row in cursor.fetchall():
                cols.append(row[0])

            if unique:
                description = 'UNIQUE'
            else:
                description = 'NON-UNIQUE'

            result.append(IndexMetadata(index_name, cols, description))

        return result

    def _is_valid_table(self, cursor, table_name):
        tables = self.get_tables(cursor)
        return table_name.upper() in tables

