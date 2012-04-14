# $Id: 5e4fe45ea4436e0dc7d3743bff9679e052071746 $
# ---------------------------------------------------------------------------
 
"""
A dummy database driver, useful for testing.
"""

__docformat__ = "restructuredtext en"

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

from grizzled.db.base import DBDriver

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BINARY = 0
NUMBER = 1
STRING = 2
DATETIME = 3
ROWID = 4

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class DummyCursor(object):
    def close(self):
        pass

    def execute(self, statement, parameters=None):
        self.rowcount = 0
        self.description = ""
        return None

    def fetchone(self):
        raise ValueError, "No results"

    def fetchall(self):
        raise ValueError, "No results"

    def fetchmany(self, n):
        raise ValueError, "No results"

class DummyDB(object):

    def __init__(self):
        pass

    def cursor(self):
        return DummyCursor()

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass

class DummyDriver(DBDriver):
    """Dummy database driver, for testing."""

    def get_import(self):
        import dummydb
        return dummydb

    def get_display_name(self):
        return "Dummy"

    def do_connect(self,
                   host="localhost",
                   port=None,
                   user='',
                   password='',
                   database='default'):
        return dummydb.DummyDB()
