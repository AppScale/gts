*************
  CherryPy 
*************

.. image:: images/cherrypy-logo.jpg

.. topic:: Introduction

  CherryPy_ 3.0+ allows you to *graft* any WSGI application as a
  controller. PyAMF's WSGI gateway can thus be used to easily
  expose a set of methods via AMF remoting.

.. contents::

Example
=======

Server
------

The following example shows how a single method is exposed in this way.
Create a file called ``server.py`` with the following content:

.. literalinclude:: ../examples/gateways/cherrypy/gateway.py
   :linenos:

You can easily expose more functions by adding them to the dictionary given
to ``WSGIGateway``. You can also create a totally different controller and
expose it under another gateway URL.

Here is a suitable ``crossdomain.xml`` file:

.. literalinclude:: ../examples/gateways/cherrypy/crossdomain.xml
   :language: xml
   :linenos:

Now run the script to start the web server.


Client
------

To test the gateway you can use a Python AMF client like this:

.. literalinclude:: ../examples/gateways/cherrypy/client.py
   :linenos:


.. _CherryPy: http://www.cherrypy.org
