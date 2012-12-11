*********************
  Adapter Framework 
*********************

.. topic:: Introduction

   The Adapter Framework allows PyAMF to integrate nicely with other Python
   libraries. This includes setting up type conversions, class mappings, etc.


Adapters Overview
=================

We currently have adapters for the following libraries:

- :doc:`../tutorials/gateways/django`
- :doc:`../tutorials/gateways/appengine`
- :doc:`../tutorials/gateways/sqlalchemy`
- Elixir_
- :py:mod:`sets` module
- :py:mod:`decimal` module


How It Works
============

The adapter framework works silently in the background. This means that the user
does not need to specifically import the Django adapter module within PyAMF, it
is all handled in the background. It works by adding a module loader and finder
to :py:data:`sys.meta_path` so it can intercept import calls and) to fire a
callback when, for example the ``django`` module is imported and accessed.

It is important to note that PyAMF does not load all the modules when
registering its adapters and therefore it doesn't load modules that you
don't use in your program.

So, code like this works:

.. code-block:: python

   from django import http
   import pyamf

As well as:

.. code-block:: python
   
   import pyamf
   from django import http

The adapter framework makes it easy to add other packages to the list, as PyAMF
matures.


Building Your Own Adapter
=========================

Your custom module:

.. literalinclude:: examples/adapters/mymodule.py
   :linenos:

Glue code:

.. literalinclude:: examples/adapters/myadapter.py
   :linenos:

And you're done!


What next?
==========

:doc:`Contributions</bugs>` (including unit tests) are always welcome!

.. _Elixir: 		http://www.elixir.ematia.de
.. _Contributions: 	http://pyamf.org/newticket
