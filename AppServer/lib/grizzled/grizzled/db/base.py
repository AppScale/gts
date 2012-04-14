# $Id: 969e4c5fd51bb174563d06c1357489c2742813ec $

"""
Base classes for enhanced DB drivers.
"""
from __future__ import absolute_import

__docformat__ = "restructuredtext en"

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import re
import time
import os
import sys
from datetime import date, datetime
from collections import namedtuple

from grizzled.exception import ExceptionWithMessage
from grizzled.decorators import abstract

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = ['DBDriver', 'DB', 'Cursor', 'DBError', 'Error', 'Warning',
           'TableMetadata', 'IndexMetadata', 'RDBMSMetadata']

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class DBError(ExceptionWithMessage):
    """
    Base class for all DB exceptions.
    """
    pass

class Error(DBError):
    """Thrown to indicate an error in the ``db`` module."""
    pass

class Warning(DBError):
    """Thrown to indicate an error in the ``db`` module."""
    pass

TableMetadata = namedtuple('TableMetadata', ['column_name',
                                             'type_string',
                                             'max_char_size',
                                             'precision',
                                             'scale',
                                             'nullable'])

IndexMetadata = namedtuple('IndexMetadata', ['index_name',
                                             'index_columns',
                                             'description'])

RDBMSMetadata = namedtuple('RDBMSMetadata', ['vendor', 'product', 'version'])

class Cursor(object):
    """
    Class for DB cursors returned by the ``DB.cursor()`` method. This class
    conforms to the Python DB cursor interface, including the following
    attributes.

    :IVariables:
        description : tuple
            A read-only attribute that is a sequence of 7-item tuples, one per
            column, from the last query executed. The tuple values are:
            *(name, typecode, displaysize, internalsize, precision, scale)*
        rowcount : int
            A read-only attribute that specifies the number of rows
            fetched in the last query, or -1 if unknown. *Note*: It's best
            not to rely on the row count, because some database drivers
            (such as SQLite) don't report valid row counts.
    """

    def __init__(self, cursor, driver):
        """
        Create a new Cursor object, wrapping the underlying real DB API
        cursor.

        :Parameters:
            cursor
                the real DB API cursor object
            driver
                the driver that is creating this object
        """
        self.__cursor = cursor
        self.__driver = driver
        self.__description = None
        self.__rowcount = -1

    def __get_description(self):
        return self.__description

    description = property(__get_description,
                           doc='The description field. See class docs.')

    def __get_rowcount(self):
        return self.__rowcount

    rowcount = property(__get_rowcount,
                        doc='Number of rows from last query, or -1')

    def close(self):
        """
        Close the cursor.

        :raise Warning: Non-fatal warning
        :raise Error:   Error; unable to close
        """
        dbi = self.__driver.get_import()
        try:
            return self.__cursor.close()
        except dbi.Warning, val:
            raise Warning(val)
        except dbi.Error, val:
            raise Error(val)

    def execute(self, statement, parameters=None):
        """
        Execute a SQL statement string with the given parameters.
        'parameters' is a sequence when the parameter style is
        'format', 'numeric' or 'qmark', and a dictionary when the
        style is 'pyformat' or 'named'. See ``DB.paramstyle()``.

        :Parameters:
            statement : str
                the SQL statement to execute
            parameters : list
                parameters to use, if the statement is parameterized

        :raise Warning: Non-fatal warning
        :raise Error:   Error
        """
        dbi = self.__driver.get_import()
        try:
            if parameters:
                result = self.__cursor.execute(statement, parameters)
            else:
                result = self.__cursor.execute(statement)

            try:
                self.__rowcount = self.__cursor.rowcount
            except AttributeError:
                self.__rowcount = -1
            self.__description = self.__cursor.description
            return result
        except dbi.Warning, val:
            raise Warning(val)
        except dbi.Error, val:
            raise Error(val)
        except:
            raise Error(sys.exc_info()[1])

    def executemany(self, statement, *parameters):
        """
        Execute a SQL statement once for each item in the given parameters.

        :Parameters:
            statement : str
                the SQL statement to execute
            parameters : sequence
                a sequence of sequences when the parameter style
                is 'format', 'numeric' or 'qmark', and a sequence
                of dictionaries when the style is 'pyformat' or
                'named'.

        :raise Warning: Non-fatal warning
        :raise Error:   Error
        """
        dbi = self.__driver.get_import()
        try:
            result = self.__cursor.executemany(statement, *parameters)
            self.__rowcount = self.__cursor.rowcount
            self.__description = self.__cursor.description
            return result
        except dbi.Warning, val:
            raise Warning(val)
        except dbi.Error, val:
            raise Error(val)

    executeMany = executemany

    def fetchone(self):
        """
        Returns the next result set row from the last query, as a sequence
        of tuples. Raises an exception if the last statement was not a query.

        :rtype:  tuple
        :return: Next result set row

        :raise Warning: Non-fatal warning
        :raise Error:   Error
        """
        dbi = self.__driver.get_import()
        try:
            return self.__cursor.fetchone()
        except dbi.Warning, val:
            raise Warning(val)
        except dbi.Error, val:
            raise Error(val)

    def fetchall(self):
        """
        Returns all remaining result rows from the last query, as a sequence
        of tuples. Raises an exception if the last statement was not a query.

        :rtype:  list of tuples
        :return: List of rows, each represented as a tuple

        :raise Warning: Non-fatal warning
        :raise Error:   Error
        """
        dbi = self.__driver.get_import()
        try:
            return self.__cursor.fetchall()
        except dbi.Warning, val:
            raise Warning(val)
        except dbi.Error, val:
            raise Error(val)

    fetchAll = fetchall

    def fetchmany(self, n):
        """
        Returns up to n remaining result rows from the last query, as a
        sequence of tuples. Raises an exception if the last statement was
        not a query.

        :Parameters:
            n : int
                maximum number of result rows to get

        :rtype:  list of tuples
        :return: List of rows, each represented as a tuple

        :raise Warning: Non-fatal warning
        :raise Error:   Error
        """
        dbi = self.__driver.get_import()
        try:
            self.__cursor.fetchmany(n)
        except dbi.Warning, val:
            raise Warning(val)
        except dbi.Error, val:
            raise Error(val)

    fetchMany = fetchmany

    def get_rdbms_metadata(self):
        """
        Return data about the RDBMS: the product name, the version,
        etc. The result is a named tuple, with the following fields:

        vendor
            The product vendor, if applicable, or ``None`` if not known
        product
            The name of the database product, or ``None`` if not known
        version
            The database product version, or ``None`` if not known

        The fields may be accessed by position or name. This method
        just calls through to the equivalent method in the underlying
        ``DBDriver`` implementation.

        :rtype: named tuple
        :return: the vendor information
        """
        # Default implementation
        dbi = self.__driver.get_import()
        try:
            return self.__driver.get_rdbms_metadata(self.__cursor)
        except dbi.Warning, val:
            raise Warning(val)
        except dbi.Error, val:
            raise Error(val)

    def get_table_metadata(self, table):
        """
        Get the metadata for a table. Returns a list of tuples, one for
        each column. Each tuple consists of the following::

            (column_name, type_string, max_char_size, precision, scale, nullable)

        The tuple elements have the following meanings.

        column_name
            the name of the column
        type_string
            the column type, as a string
        max_char_size
            the maximum size for a character field, or ``None``
        precision
            the precision, for a numeric field; or ``None``
        scale
            the scale, for a numeric field; or ``None``
        nullable
            True if the column is nullable, False if it is not

        The tuples are named tuples, so the fields may be referenced by the
        names above or by position.

        The data may come from the DB API's ``cursor.description`` field, or
        it may be richer, coming from a direct SELECT against
        database-specific tables.

        :rtype: list
        :return: list of tuples, as described above

        :raise Warning: Non-fatal warning
        :raise Error:   Error
        """
        # Default implementation
        dbi = self.__driver.get_import()
        try:
            return self.__driver.get_table_metadata(table, self.__cursor)
        except dbi.Warning, val:
            raise Warning(val)
        except dbi.Error, val:
            raise Error(val)

    def get_index_metadata(self, table):
        """
        Get the metadata for the indexes for a table. Returns a list of
        tuples, one for each index. Each tuple consists of the following::

            (index_name, [index_columns], description)

        The tuple elements have the following meanings.

        index_name
            the index name
        index_columns
            a list of column names
        description
            index description, or ``None``

        The tuples are named tuples, so the fields may be referenced by the
        names above or by position.

        :rtype:  list of tuples
        :return: the list of tuples, or ``None`` if not supported in the
                 underlying database

        :raise Warning: Non-fatal warning
        :raise Error:   Error
        """
        dbi = self.__driver.get_import()
        try:
            return self.__driver.get_index_metadata(table, self.__cursor)
        except dbi.Warning, val:
            raise Warning(val)
        except dbi.Error, val:
            raise Error(val)

    def get_tables(self):
        """
        Get the list of tables in the database to which this cursor is
        connected.

        :rtype:  list
        :return: List of table names. The list will be empty if the database
                 contains no tables.

        :raise NotImplementedError: Capability not supported by database driver
        :raise Warning:             Non-fatal warning
        :raise Error:               Error
        """
        dbi = self.__driver.get_import()
        try:
            return self.__driver.get_tables(self.__cursor)
        except dbi.Warning, val:
            raise Warning(val)
        except dbi.Error, val:
            raise Error(val)

class DB(object):
    """
    The object returned by a call to ``DBDriver.connect()``. ``db`` wraps the
    real database object returned by the underlying Python DB API module's
    ``connect()`` method.
    """
    def __init__(self, db, driver):
        """
        Create a new DB object.

        :Parameters:
            db
                the underlying Python DB API database object
            driver : DBDriver
                the driver (i.e., the subclass of ``DBDriver``) that
                created the ``db`` object
        """
        self.__db = db
        self.__driver = driver
        dbi = driver.get_import()
        for attr in ['BINARY', 'NUMBER', 'STRING', 'DATETIME', 'ROWID']:
            try:
                exec 'self.%s = dbi.%s' % (attr, attr)
            except AttributeError:
                exec 'self.%s = 0' % attr

    def paramstyle(self):
        """
        Get the parameter style for the underlying DB API module. The
        result of this method call corresponds exactly to the underlying
        DB API module's 'paramstyle' attribute. It will have one of the
        following values:

        +----------+-----------------------------------------------------------+
        | format   | The parameter marker is '%s', as in string                |
        |          | formatting. A query looks like this::                     |
        |          |                                                           |
        |          |   c.execute('SELECT * FROM Foo WHERE Bar=%s', [x])        |
        +----------+-----------------------------------------------------------+
        | named    | The parameter marker is ``:name``, and parameters         |
        |          | are named. A query looks like this::                      |
        |          |                                                           |
        |          |   c.execute('SELECT * FROM Foo WHERE Bar=:x', {'x':x})    |
        +----------+-----------------------------------------------------------+
        | numeric  | The parameter marker is ``:n``, giving the parameter's    |
        |          | number (starting at 1). A query looks like this::         |
        |          |                                                           |
        |          |   c.execute('SELECT * FROM Foo WHERE Bar=:1', [x])        |
        +----------+-----------------------------------------------------------+
        | pyformat | The parameter marker is ``:name``, and parameters         |
        |          | are named. A query looks like this::                      |
        |          |                                                           |
        |          |   c.execute('SELECT * FROM Foo WHERE Bar=%(x)s', {'x':x}) |
        +----------+-----------------------------------------------------------+
        | qmark    | The parameter marker is "?", and parameters are           |
        |          | substituted in order. A query looks like this::           |
        |          |                                                           |
        |          |   c.execute('SELECT * FROM Foo WHERE Bar=?', [x])         |
        +----------+-----------------------------------------------------------+
        """
        return self.__driver.get_import().paramstyle

    def Binary(self, string):
        """
        Returns an object representing the given string of bytes as a BLOB.

        This method is equivalent to the module-level ``Binary()`` method in
        an underlying DB API-compliant module.

        :Parameters:
            string : str
                the string to convert to a BLOB

        :rtype:  object
        :return: the corresponding BLOB
        """
        return self.__driver.get_import().Binary(string)

    def Date(self, year, month, day):
        """
        Returns an object representing the specified date.

        This method is equivalent to the module-level ``Date()`` method in
        an underlying DB API-compliant module.

        :Parameters:
            year
                the year
            month
                the month
            day
                the day of the month

        :return: an object containing the date
        """
        return self.__driver.get_import().Date(year, month, day)

    def DateFromTicks(self, secs):
        """
        Returns an object representing the date *secs* seconds after the
        epoch. For example:

        .. python::

            import time

            d = db.DateFromTicks(time.time())

        This method is equivalent to the module-level ``DateFromTicks()``
        method in an underlying DB API-compliant module.

        :Parameters:
            secs : int
                the seconds from the epoch

        :return: an object containing the date
        """
        date = date.fromtimestamp(secs)
        return self.__driver.get_import().Date(date.year, date.month, date.day)

    def Time(self, hour, minute, second):
        """
        Returns an object representing the specified time.

        This method is equivalent to the module-level ``Time()`` method in an
        underlying DB API-compliant module.

        :Parameters:
            hour
                the hour of the day
            minute
                the minute within the hour. 0 <= *minute* <= 59
            second
                the second within the minute. 0 <= *second* <= 59

        :return: an object containing the time
        """
        dt = datetime.fromtimestamp(secs)
        return self.__driver.get_import().Time(dt.hour, dt.minute, dt.second)

    def TimeFromTicks(self, secs):
        """
        Returns an object representing the time 'secs' seconds after the
        epoch. For example:

        .. python::

            import time

            d = db.TimeFromTicks(time.time())

        This method is equivalent to the module-level ``TimeFromTicks()``
        method in an underlying DB API-compliant module.

        :Parameters:
            secs : int
                the seconds from the epoch

        :return: an object containing the time
        """
        dt = datetime.fromtimestamp(secs)
        return self.__driver.get_import().Time(dt.hour, dt.minute, dt.second)

    def Timestamp(self, year, month, day, hour, minute, second):
        """
        Returns an object representing the specified time.

        This method is equivalent to the module-level ``Timestamp()`` method
        in an underlying DB API-compliant module.

        :Parameters:
            year
                the year
            month
                the month
            day
                the day of the month
            hour
                the hour of the day
            minute
                the minute within the hour. 0 <= *minute* <= 59
            second
                the second within the minute. 0 <= *second* <= 59

        :return: an object containing the timestamp
        """
        return self.__driver.get_import().Timestamp(year, month, day,
                                                    hour, minute, second)

    def TimestampFromTicks(self, secs):
        """
        Returns an object representing the date and time ``secs`` seconds
        after the epoch. For example:

        .. python::

            import time

            d = db.TimestampFromTicks(time.time())

        This method is equivalent to the module-level ``TimestampFromTicks()``
        method in an underlying DB API-compliant module.

        :Parameters:
            secs : int
                the seconds from the epoch

        :return: an object containing the timestamp
        """
        dt = datetime.now()
        return self.__driver.get_import().Timestamp(dt.year, dt.month, dt.day,
                                                    dt.hour, dt.minute, dt.second)

    def cursor(self):
        """
        Get a cursor suitable for accessing the database. The returned object
        conforms to the Python DB API cursor interface.

        :return: the cursor

        :raise Warning: Non-fatal warning
        :raise Error:   Error
        """
        dbi = self.__driver.get_import()
        try:
            return Cursor(self.__db.cursor(), self.__driver)
        except dbi.Warning, val:
            raise Warning(val)
        except dbi.Error, val:
            raise Error(val)

    def commit(self):
        """
        Commit the current transaction.

        :raise Warning: Non-fatal warning
        :raise Error:   Error
        """
        dbi = self.__driver.get_import()
        try:
            self.__db.commit()
        except dbi.Warning, val:
            raise Warning(val)
        except dbi.Error, val:
            raise Error(val)

    def rollback(self):
        """
        Roll the current transaction back.

        :raise Warning: Non-fatal warning
        :raise Error:   Error
        """
        dbi = self.__driver.get_import()
        try:
            self.__db.rollback()
        except dbi.Warning, val:
            raise Warning(val)
        except dbi.Error, val:
            raise Error(val)

    def close(self):
        """
        Close the database connection.

        :raise Warning: Non-fatal warning
        :raise Error:   Error
        """
        dbi = self.__driver.get_import()
        try:
            self.__db.close()
        except dbi.Warning, val:
            raise Warning(val)
        except dbi.Error, val:
            raise Error(val)

class DBDriver(object):
    """
    Base class for all DB drivers.
    """

    @abstract
    def get_import(self):
        """
        Get a bound import for the underlying DB API module. All subclasses
        must provide an implementation of this method. Here's an example,
        assuming the real underlying Python DB API module is 'foosql':

        .. python::

            def get_import(self):
                import foosql
                return foosql

        :return: a bound module
        """
        pass

    def __display_name(self):
        return self.get_display_name()

    @abstract
    def get_display_name(self):
        """
        Get the driver's name, for display. The returned name ought to be
        a reasonable identifier for the database (e.g., 'SQL Server',
        'MySQL'). All subclasses must provide an implementation of this
        method.

        :rtype:  str
        :return: the driver's displayable name
        """
        pass

    display_name = property(__display_name,
                            doc='get a displayable name for the driver')
    def connect(self,
                host='localhost',
                port=None,
                user=None,
                password='',
                database=None):
        """
        Connect to the underlying database. Subclasses should *not*
        override this method. Instead, a subclass should override the
        ``do_connect()`` method.

        :Parameters:
            host : str
                the host where the database lives
            port : int
                the TCP port to use when connecting, or ``None``
            user : str
                the user to use when connecting, or ``None``
            password : str
                the password to use when connecting, or ``None``
            database : str
                the name of the database to which to connect

        :rtype:  ``db``
        :return: a ``db`` object representing the open database

        :raise Warning: Non-fatal warning
        :raise Error:   Error
        """
        dbi = self.get_import()
        try:
            self.__db = self.do_connect(host=host,
                                       port=port,
                                       user=user,
                                       password=password,
                                       database=database)
            return DB(self.__db, self)
        except dbi.Warning, val:
            raise Warning(val)
        except dbi.Error, val:
            raise Error(val)

    @abstract
    def do_connect(self,
                   host='localhost',
                   port=None,
                   user='',
                   password='',
                   database='default'):
        """
        Connect to the actual underlying database, using the driver.
        Subclasses must provide an implementation of this method. The
        method must return the result of the real DB API implementation's
        ``connect()`` method. For instance:

        .. python::

            def do_connect():
                dbi = self.get_import()
                return dbi.connect(host=host, user=user, passwd=password,
                                   database=database)

        There is no need to catch exceptions; the ``DBDriver`` class's
        ``connect()`` method handles that.

        :Parameters:
            host : str
                the host where the database lives
            port : int
                the TCP port to use when connecting
            user : str
                the user to use when connecting
            password : str
                the password to use when connecting
            database : str
                the name of the database to which to connect

        :rtype:  object
        :return: a DB API-compliant object representing the open database

        :raise Warning: Non-fatal warning
        :raise Error:   Error
        """
        pass

    def get_rdbms_metadata(self, cursor):
        """
        Return data about the RDBMS: the product name, the version,
        etc. The result is a named tuple, with the following fields.

        vendor
            The product vendor, if applicable, or ``None`` if not known
        product
            The name of the database product, or ``None`` if not known
        version
            The database product version, or ``None`` if not known

        :Parameters:
            cursor : Cursor
                a ``Cursor`` object from a recent query

        :rtype: named tuple
        :return: the vendor information
        """
        return RDBMSMetadata('unknown', 'unknown', 'unknown')

    def get_index_metadata(self, table, cursor):
        """
        Get the metadata for the indexes for a table. Returns a list of
        tuples, one for each index. Each tuple consists of the following::

            (index_name, [index_columns], description)

        The tuple elements have the following meanings.

        index_name
            the index name
        index_columns
            a list of column names
        description
            index description, or ``None``

        The tuples are named tuples, so the fields may be referenced by the
        names above or by position.

        The default implementation of this method returns `None`

        :Parameters:
            table : str
                table name
            cursor : Cursor
                a ``Cursor`` object from a recent query

        :rtype:  list of tuples
        :return: the list of tuples, or ``None`` if not supported in the
                 underlying database

        :raise Warning: Non-fatal warning
        """
        return None

    def get_table_metadata(self, table, cursor):
        """
        Get the metadata for a table. Returns a list of tuples, one for
        each column. Each tuple consists of the following::

            (column_name, type_string, max_char_size, precision, scale, nullable)

        The tuple elements have the following meanings.

        column_name
            the name of the column
        type_string
            the column type, as a string
        max_char_size
            the maximum size for a character field, or ``None``
        precision
            the precision, for a numeric field; or ``None``
        scale
            the scale, for a numeric field; or ``None``
        nullable
            ``True`` if the column is nullable, ``False`` if it is not

        The tuples are named tuples, so the fields may be referenced by the
        names above or by position.

        The default implementation uses the DB API's ``cursor.description``
        field. Subclasses are free to override this method to produce their
        own version that uses other means.

        :Parameters:
            table : str
                the table name for which metadata is desired
            cursor : Cursor
                a ``Cursor`` object from a recent query

        :rtype: list
        :return: list of tuples, as described above

        :raise Warning: Non-fatal warning
        :raise Error:   Error
        """
        self._ensure_valid_table(cursor, table)
        dbi = self.get_import()
        cursor.execute('SELECT * FROM %s WHERE 1=0' % table)
        result = []
        for col in cursor.description:
            name = col[0]
            type = col[1]
            size = col[2]
            internalSize = col[3]
            precision = col[4]
            scale = col[5]
            nullable = col[6]

            sType = None
            try:
                if type == dbi.BINARY:
                    stype = 'blob'
                elif type == dbi.DATETIME:
                    stype = 'datetime'
                elif type == dbi.NUMBER:
                    stype = 'numeric'
                elif type == dbi.STRING:
                    sz = internalSize
                    if sz == None:
                        sz = size
                    elif sz <= 0:
                        sz = size

                    if sz == 1:
                        stype = 'char'
                    else:
                        stype = 'varchar'
                    size = sz
                elif type == dbi.ROWID:
                    stype = 'id'
            except AttributeError:
                stype = None

            if not sType:
                stype = 'unknown (type code=%s)' % str(type)

            data = TableMetadata(name, stype, size, precision, scale, nullable)
            result += [data]

        return result

    def get_tables(self, cursor):
        """
        Get the list of tables in the database.

        :Parameters:
            cursor : Cursor
                a ``Cursor`` object from a recent query

        :rtype:  list
        :return: List of table names. The list will be empty if the database
                 contains no tables.

        :raise NotImplementedError: Capability not supported by database driver
        :raise Warning:             Non-fatal warning
        :raise Error:               Error
        """
        raise NotImplementedError

    def _ensure_valid_table(self, cursor, table_name):
        """
        Determines whether a table name represents a legal table in the
        current database, throwing an ``Error`` if not.

        :Parameters:
            cursor : Cursor
                an open ``Cursor``

            table_name : str
                the table name

        :raise Error: bad table name
        """
        if not self._is_valid_table(cursor, table_name):
            raise Error, 'No such table: "%s"' % table_name

    def _is_valid_table(self, cursor, table_name):
        """
        Determines whether a table name represents a legal table in the
        current database, throwing an ``Error`` if not.

        :Parameters:
            cursor : Cursor
                an open ``Cursor``

            table_name : str
                the table name

        :rtype: bool
        :return: ``True`` if the table is valid, ``False`` if not
        """
        tables = self.get_tables(cursor)
        return table_name in tables
