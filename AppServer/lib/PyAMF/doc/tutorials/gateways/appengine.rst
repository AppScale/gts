**********************
  Google App Engine 
**********************

.. image:: images/appengine-logo.gif

.. topic:: Introduction

   This document explains how to get a PyAMF application running on Google
   App Engine for Python.

   `Google App Engine`_ (GAE) lets you run your web applications on Google's
   infrastructure for free. You can serve your app using a free domain name
   on the appspot.com domain, or use `Google Apps`_ to serve it from your
   own domain.

   GAE applications are implemented using Python 2.5.2. The `runtime
   environment`_ includes the full Python language and most_
   of the Python standard library, including :doc:`django`.

.. contents::

Prerequisites
=============

Before you can start using GAE you need to download and install:

- Python 2.5 or newer for your platform from `the Python website`_. Users of
  Mac OS X 10.5 or newer already have an up-to-date Python installed.
- `Google App Engine SDK`_ for Python
- :doc:`PyAMF</community/download>` 0.3.1 or newer


Create Project
==============

Start a new GAE project:

- Create a new folder for your project
- Copy ``main.py``, ``app.yaml``, and ``index.yaml`` from
  ``google_appengine/new_project_template`` to your new folder. On a Mac
  you can find it under ``/usr/local``
- Move the ``pyamf`` folder from your unpacked ``PyAMF-0.x.x`` folder
  to the root folder of the new GAE project

Using a terminal the steps above would translate into something like:

.. code-block:: bash

    cp -R /usr/local/google_appengine/new_project_template MyProject
    cp -R PyAMF-0.5.1/pyamf MyProject
    cd MyProject
    ls -l

The folder structure of your project should look something like this:

.. code-block:: bash

   + MyProject
     - app.yaml
     - index.yaml
     - main.py
     - pyamf


Application
===========

You can setup your application using the ``WebAppGateway`` or the
``WSGIGateway``.


WebApp Gateway
--------------

The :class:`pyamf.remoting.gateway.google.WebAppGateway` class allows a GAE
application to handle AMF requests on the root URL and other standard HTTP
requests on another URL (``/helloworld`` in the examples below).

The ``main.py`` module tells GAE what code to launch. Modify it for PyAMF:

.. literalinclude:: ../examples/gateways/appengine/webapp.py
   :linenos:


WSGI Gateway
------------

If you don't want to use the pure ``google.appengine`` approach as
described above, you can also use
:class:`pyamf.remoting.gateway.wsgi.WSGIGateway` by modifying your
``main.py`` like this:

.. literalinclude:: ../examples/gateways/appengine/wsgi.py
   :linenos:


Start the server
================

Run this command from your application folder:

.. code-block:: bash

   /usr/local/google_appengine/dev_appserver.py --debug --address=localhost --port=8080 .

Once the server started it usually prints something like:

.. code-block:: bash

   INFO     2010-03-10 00:06:22,840 dev_appserver_main.py:399] Running application new-project-template on port 8080: http://localhost:8080


Test the application
====================

When you visit http://localhost:8080/helloworld in your browser it should
show a simple message:

.. code-block:: html

   Hello, webapp World!

The AMF gateway is available on http://localhost:8080, so this should return a
405 in the browser:

.. code-block:: html

    405 Method Not Allowed

    To access this PyAMF gateway you must use POST requests (GET received)


Python
------

To test the gateway you can use a Python AMF client like this:

.. literalinclude:: ../examples/gateways/appengine/client.py
   :linenos:


Flash
-----

Create a new Adobe Flash document and place a ``TextField`` on
the stage. Make it dynamic in the Properties pane, and give it
the instance name ``output``. Then, paste the following code
into the Actions pane:

.. literalinclude:: ../examples/gateways/appengine/flash.as
   :language: actionscript
   :linenos:

Run ``Debug`` > ``Debug`` movie to test PyAMF with Google App
Engine! Other examples for Flex etc can be found on the
Examples page.


Useful Resources
================

http://aralbalkan.com/1307
   Aral Balkan - Building Flash applications with Google App Engine.

:doc:`../gateways/django`
   PyAMF integration with Django.

:doc:`../actionscript/bytearray`
   ByteArray example using Django and Flex.

http://blog.pyamf.org/2008/04/pyamf-and-google-app-engine
   Related post on PyAMF blog.

http://pyamf-test.appspot.com
   Run the PyAMF test suite on the Google App Engine.


.. _Google App Engine: http://code.google.com/appengine
.. _Google Apps: http://www.google.com/a/help/intl/en/index.html
.. _runtime environment: http://code.google.com/appengine/docs/python
.. _most: http://code.google.com/appengine/docs/python/purepython.html
.. _the Python website: http://python.org/download
.. _Google App Engine SDK: http://code.google.com/appengine/downloads.html
