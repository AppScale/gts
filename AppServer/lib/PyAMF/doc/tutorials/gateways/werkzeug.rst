************
  Werkzeug 
************

.. topic:: Introduction

   The following tutorial describes how to set up a bare bones
   Werkzeug_ project with a gateway exposing a method.

   Since Werkzeug supports generic WSGI apps, setting up a
   remoting gateway is trivial using the WSGI gateway.

.. contents::

Example
=======

Create a new Werkzeug project by creating a file called
``server.py``:

.. literalinclude:: ../examples/gateways/werkzeug/server.py
    :linenos:


Fire up the web server with:

.. code-block:: bash

   python server.py


That should print something like:

.. code-block:: bash

   * Running on http://localhost:8000/
   * Restarting with reloader...


To test the gateway you can use a Python AMF client
like this:

.. literalinclude:: ../examples/gateways/werkzeug/client.py
   :linenos:


.. _Werkzeug: http://werkzeug.pocoo.org
