**************
  mod_python 
**************

.. image:: images/mod_python-logo.gif

.. topic:: Introduction

   This tutorial shows you how to easily publish your PyAMF applications
   with the `Apache 2 <http://httpd.apache.org>`_ webserver and
   `mod_python <http://modpython.org>`_. Mod_python is an Apache module
   that embeds the Python interpreter within the server. This was tested
   with Python 2.4.3 and
   `Ubuntu 6.06.1 LTS <https://wiki.ubuntu.com/DapperReleaseNotes>`_. 

   This tutorial assumes you already installed the Apache webserver
   running (on 192.168.1.100). Flash applications will be able to access
   your PyAMF remoting gateway on http://192.168.1.100/flashservices/gateway.

.. contents::

Download WSGI gateway for mod_python
====================================

Create a folder for your application:

.. code-block:: bash

   mkdir /var/www/myApp

Grab the `WSGI gateway for mod_python
<http://www.aminus.net/browser/modpython_gateway.py>`_ and put it in your
application folder:

.. code-block:: bash
   
   wget http://www.aminus.net/browser/modpython_gateway.py?format=raw
   mv modpython_gateway.py?format=raw /var/www/myApp/wsgi.py


Create your PyAMF application
=============================

Create a startup file for your application in ``/var/www/myApp/startup.py``:

.. literalinclude:: ../examples/apache/mod_python.py
    :linenos:

Make sure your Apache user (``www-data``) has access to your application
files.


Setup Apache virtual host
=========================

Create a new virtual host or modify an existing one:

.. literalinclude:: ../examples/apache/mod_python.vhost
    :language: apache
    :linenos:


Restart Apache
==============

That's it! Your Adobe Flash Player and AMF clients will now be able to
access your PyAMF application through http://192.168.1.100/flashservices/gateway. 


Useful Resources
================

http://wiki.pylonshq.com/display/pylonscookbook/Production+deployment+using+mod_python
    Production deployment using mod_python (pylonshq).

http://www.aminus.net/wiki/ModPythonGateway
    ModPythonGateway.

http://www.modpython.org/live/mod_python-3.2.8/doc-html/dir-other-pp.html
   mod_python manual for ``PYTHONPATH``.