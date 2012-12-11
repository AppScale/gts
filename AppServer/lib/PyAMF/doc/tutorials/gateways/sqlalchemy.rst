**************
  SQLAlchemy 
**************


.. image:: images/sqlalchemy-logo.gif


.. topic:: Introduction

    SQLAlchemy_ is the Python SQL toolkit and Object Relational Mapper
    that gives application developers the full power and flexibility of
    SQL.


Overview
========

PyAMF 0.4 and newer includes an adapter for decoding/encoding objects
managed by SQLAlchemy. The adapter is enabled by default, and SQLAlchemy
managed objects are transparently encoded/decoded by the adapter.

To use the adapter, make sure any SQLAlchemy managed classes are mapped
**before** assigning an AMF alias for the class.

.. code-block:: python

   # MUST COME FIRST
   sqlalchemy.orm.mapper(MappedClass, mapped_table)

   # MUST COME LATER
   pyamf.register_class(MappedClass, 'mapped_class_alias')


The adapter adds 2 additional attributes to all encoded objects that are
managed by SQLAlchemy.

- ``sa_key`` -- An Array of values that make up the primary key of the
   encoded object (analogous to ``mapper.primary_key_from_instance(obj)``
   in Python)
- ``sa_lazy`` -- An Array of attribute names that have not yet been
   loaded from the database

The additional information contained in these attributes can be used to lazy
load attributes in the client.

Third party packages
====================

PyAMF also provides support for the excellent Elixir_ library, a thin wrapper,
which provides the ability to create simple Python classes that map directly
to relational database tables (this pattern is often referred to as the
Active Record design pattern)


Useful Resources
================

:doc:`../actionscript/addressbook`
   Demonstrates the use of SQLAlchemy and Flex.

http://api.pyamf.org/0.5.1/toc-pyamf.adapters._sqlalchemy_orm-module.html
   API documentation.

.. _SQLAlchemy: http://www.sqlalchemy.org
.. _Elixir: http://elixir.ematia.de
