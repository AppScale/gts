# $Id: fa873c96e7b5ed23437473a2b6d0b9a3871d4a18 $

"""
Introduction
============

The ``db`` module is a DB API wrapper. It provides a DB API-compliant API that
wraps real underlying DB API drivers, simplifying some non-portable operations
like ``connect()`` and providing some new operations.

Some drivers come bundled with this package. Others can be added on the fly.

Getting the List of Drivers
===========================

To get a list of all drivers currently registered with this module, use the
``get_driver_names()`` method:

.. python::

    import db

    for driver_name in db.get_driver_names():
        print driver_name

Currently, this module provides the following bundled drivers:

  +------------------+------------+-------------------+
  | Driver Name,     |            |                   |
  | as passed to     |            | Underlying Python |
  | ``get_driver()`` | Database   | DB API module     |
  +==================+============+===================+
  | dummy            | None       | ``db.DummyDB``    |
  +------------------+------------+-------------------+
  | gadfly           | Gadfly     | ``gadfly``        |
  +------------------+------------+-------------------+
  | mysql            | MySQL      | ``MySQLdb``       |
  +------------------+------------+-------------------+
  | oracle           | Oracle     | ``cx_Oracle``     |
  +------------------+------------+-------------------+
  | postgresql       | PostgreSQL | ``psycopg2``      |
  +------------------+------------+-------------------+
  | sqlserver        | SQL Server | ``pymssql``       |
  +------------------+------------+-------------------+
  | sqlite           | SQLite 3   | ``sqlite3``       |
  +------------------+------------+-------------------+

To use a given driver, you must have the corresponding Python DB API module
installed on your system.

Adding a Driver
===============

It's possible to add a new driver to the list of drivers supplied by this
module. To do so:

 1. The driver class must extend ``DBDriver`` and provide the appropriate
    methods. See examples in this module.
 2. The driver's module (or the calling program) must register the driver
    with this module by calling the ``add_driver()`` function.


DB API Factory Functions
========================

The ``Binary()``, ``Date()``, ``DateFromTicks()``, ``Time()``,
``TimeFromTicks()``, ``TimeStamp()`` and ``TimestampFromTicks()`` DB API
functions can be found in the DB class. Thus, to make a string into a BLOB
with this API, you use:

.. python::

    driver = db.get_driver(driver_name)
    db = driver.connect(...)
    blob = db.Binary(some_string)
"""

__docformat__ = "restructuredtext en"

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import re
import time
import os
import sys
from datetime import date, datetime

from grizzled.exception import ExceptionWithMessage
from grizzled.decorators import abstract
from grizzled.db import (base, dummydb, dbgadfly, mysql, oracle, postgresql,
                         sqlite, sqlserver)
from grizzled.db.base import *

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = ['get_driver', 'add_driver', 'get_driver_names', 'DBDriver',
           'DB', 'Cursor', 'DBError', 'Error', 'Warning', 'apilevel',
           'threadsafety', 'paramstyle']

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

DummyDriver = dummydb.DummyDriver
GadflyDriver = dbgadfly.GadflyDriver
MySQLDriver = mysql.MySQLDriver
OracleDriver = oracle.OracleDriver
PostgreSQLDriver = postgresql.PostgreSQLDriver
SQLite3Driver = sqlite.SQLite3Driver
SQLServerDriver = sqlserver.SQLServerDriver

drivers = { 'dummy'      : 'DummyDriver',
            'mysql'      : 'MySQLDriver',
            'postgresql' : 'PostgreSQLDriver',
            'sqlserver'  : 'SQLServerDriver',
            'sqlite'     : 'SQLite3Driver',
            'oracle'     : 'OracleDriver',
            'gadfly'     : 'GadflyDriver'}

apilevel = '2.0'
threadsafety = '1'
paramstyle = None

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def add_driver(key, driver_class, force=False):
    """
    Add a driver class to the list of drivers.

    :Parameters:
        key : str
            the key, also used as the driver's name
        driver_class : class
            the ``DBDriver`` subclass object
        force : bool
            ``True`` to force registration of the driver, even if there's an
            existing driver with the same key; ``False`` to throw an exception
            if there's an existing driver with the same key.

    :raise ValueError: There's an existing driver with the same key, and
                       ``force`` is ``False``
    """
    try:
        drivers[key]
        if not force:
            raise ValueError, 'A DB driver named "%s" is already installed' %\
                  key
    except KeyError:
        pass

    drivers[key] = driver_class

def get_drivers():
    """
    Get the list of drivers currently registered with this API. The result is
    a list of ``DBDriver`` subclasses. Note that these are classes, not
    instances. Once way to use the resulting list is as follows:

    .. python::

        for driver in db.get_drivers():
            print driver.__doc__

    :rtype:  list
    :return: list of ``DBDriver`` class names
    """
    return [str(d) for d in drivers.values()]

def get_driver_names():
    """
    Get the list of driver names currently registered with this API.
    Each of the returned names may be used as the first parameter to
    the ``get_driver()`` function.
    """
    return drivers.keys()

def get_driver(driver_name):
    """
    Get the DB API object for the specific database type. The list of
    legal database types are available by calling ``get_driver_names()``.

    :Parameters:
        driver_name : str
            name (key) of the driver

    :rtype: DBDriver
    :return: the instantiated driver

    :raise ValueError: Unknown driver name
    """
    try:
        o = drivers[driver_name]
        if type(o) == str:
            exec 'd = %s()' % o
        else:
            d = o()
        return d
    except KeyError:
        raise ValueError, 'Unknown driver name: "%s"' % driver_name
