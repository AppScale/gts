# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Defines the database schema.

@since: 0.1.0
"""

import os, datetime

from sqlalchemy import *

metadata = MetaData()

dsn = 'sqlite:///temp.db'

if 'RECORDSET_DSN' in os.environ:
    dsn = os.environ['RECORDSET_DSN']

language = Table('languages', metadata,
    Column('ID', String(10), primary_key=True),
    Column('Description', String(255), nullable=True, default=None),
    Column('Name', String(50), nullable=True, default=None),
)

software = Table('SoftwareInfo', metadata,
    Column('ID', Integer, primary_key=True, autoincrement=True),
    Column('Name', Text),
    Column('Active', Boolean, default=True),
    Column('Details', String(255), nullable=True, default=None),
    Column('CategoryID', String(50), nullable=True, default=None),
    Column('Url', String(255), nullable=True, default=None)
)

def get_engine():
    return create_engine(dsn)

def create(engine):
    print "Creating tables..."
    metadata.create_all(bind=engine)
