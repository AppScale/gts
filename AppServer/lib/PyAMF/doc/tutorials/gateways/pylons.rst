**********
  Pylons 
**********

.. topic:: Introduction

   The following tutorial describes how to set up a bare bones
   Pylons_ project with a gateway exposing a method.

   Since Pylons supports_ generic WSGI (:pep:`333`) apps as
   controllers, setting up a remoting gateway is trivial using the WSGI
   gateway.

.. contents::

Example
=======

1. Create a new Pylons project with:

  .. code-block:: bash

     $ paster create -t pylons testproject


2. ``cd`` into it and create a controller:

  .. code-block:: bash

     $ cd testproject
     $ paster controller gateway


3. Replace the contents of ``testproject/controllers/gateway.py`` with the following:

  .. literalinclude:: ../examples/gateways/pylons/gateway.py
     :linenos:

  You can easily expose more functions by adding them to the dictionary given to ``WSGIGateway``.
  You can also create a totally different controller and expose it under another gateway URL.


4. Add the controller to the routing map, open ``testproject/config/routing.py`` and look for the line:

  .. code-block:: python

     # CUSTOM ROUTES HERE

  Just below that line, add a mapping to the controller you created earlier. This maps URLs with
  the prefix 'gateway' to the AMF gateway.
  
  .. code-block:: python
  
     map.connect('/gateway', controller='gateway')


5. Import the remoting gateway, open ``testproject/lib/helpers.py`` and add:

  .. code-block:: python
    
     from pyamf.remoting.gateway.wsgi import WSGIGateway


6. Copy a ``crossdomain.xml`` file into ``testproject/public``:

  .. literalinclude:: ../examples/gateways/pylons/crossdomain.xml
     :language: xml
     :linenos:


7. Fire up the web server with:

  .. code-block:: bash

     $ paster serve --reload development.ini

  That should print something like:

  .. code-block:: bash

     Starting subprocess with file monitor
     Starting server in PID 4247.
     serving on 0.0.0.0:5000 view at http://127.0.0.1:5000


8. To test the gateway you can use a Python AMF client like this:

  .. literalinclude:: ../examples/gateways/pylons/client.py
     :linenos:


.. _Pylons: http://pylonshq.com
.. _supports: http://wiki.pylonshq.com/display/pylonsdocs/Web+Server+Gateway+Interface+Support
