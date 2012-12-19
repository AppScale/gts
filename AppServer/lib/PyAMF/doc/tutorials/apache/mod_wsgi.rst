*************
  mod_wsgi
*************

.. topic:: Introduction

   This tutorial shows you how to easily publish your PyAMF applications
   with the `Apache 2`_ webserver and mod_wsgi_. Mod_wsgi is an Apache module
   which can host any Python application which supports the Python WSGI_
   interface. This was tested with Python 2.5, Apache 2.0.55 and mod_wsgi 2.x.

   This tutorial assumes you already installed the Apache webserver
   running (on 192.168.1.100). Flash applications will be able to access
   your PyAMF remoting gateway on http://192.168.1.100/flashservices/gateway.

.. contents::

Create your PyAMF application
=============================

Create a folder for your application:

.. code-block:: bash

   mkdir /var/www/myApp

Create your application in ``/var/www/myApp/application.py``:

.. literalinclude:: ../examples/apache/mod_wsgi.py
    :linenos:


WSGI startup file
=================

Create a folder for the WSGI startup file:

.. code-block:: bash

   mkdir /var/www/wsgi


Create the WSGI startup file for your application in
``/var/www/wsgi/myApp.wsgi``:

.. literalinclude:: ../examples/apache/myApp.wsgi
    :linenos:


About logging
-------------

When using mod_wsgi, unless you take specific action to
catch exceptions and present the details in an alternate
manner, the only place that details of uncaught exceptions
will be recorded is in the Apache error log files. The
Apache error log files are therefore your prime source of
information when things go wrong.

This example tries to make your life easier by using a
custom ``RotatingFile`` logger, that writes log messages to
a file.


Setup Apache virtual host
=========================

Create a new virtual host or modify an existing one:

.. literalinclude:: ../examples/apache/mod_wsgi.vhost
    :language: apache
    :linenos:

This sample assumes you have a copy of the PyAMF source installed in
``/usr/src/pyamf`` but you can comment out line 1 if you installed
PyAMF in your Python's ``site-packages`` folder.

Make sure your Apache user (``www-data``) has access to your
application files.


Restart Apache
==============

That's it! Your Adobe Flash Player and AMF clients will now be able
to access your PyAMF application through
http://192.168.1.100/flashservices/gateway. 

Test the gateway
----------------

To test the gateway you can use a Python AMF client like this:

.. literalinclude:: ../examples/apache/client.py
   :linenos:


Useful Resources
================

http://code.google.com/p/modwsgi/wiki/ConfigurationGuidelines
   Configuration guidelines for mod_wsgi.

http://code.google.com/p/modwsgi/wiki/ConfigurationDirectives
    Configuration directives for mod_wsgi.


.. _configured: http://pythonpaste.org/modules/exceptions.html#paste.exceptions.errormiddleware.ErrorMiddleware
.. _Apache 2: http://httpd.apache.org
.. _mod_wsgi: http://modwsgi.org
.. _WSGI: http://wsgi.org
