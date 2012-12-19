**********
  Django 
**********

.. image:: images/django-logo.png

.. topic:: Introduction

   The Django_ Remoting gateway included in PyAMF allows you to expose
   functions in Django (0.96 or newer) to AMF clients and servers.

.. contents::


Example
=======

Exposing functions for AMF remoting is simple by defining a gateway
(a dispatcher) like this:

.. literalinclude:: ../examples/gateways/django/amfgateway.py
   :linenos:


The ``request`` in the first argument to the ``echo`` function corresponds
to the request object passed to every Django view function. To disable
this function add ``expose_request=False`` when instantiating the
``DjangoGateway``. As in:

.. code-block:: python
   :linenos:

   # yourproject/yourapp/amfgateway.py

   from pyamf.remoting.gateway.django import DjangoGateway

   def echo(data):
       return data

   services = {
       'myservice.echo': echo
       # could include other functions as well
   }

   echoGateway = DjangoGateway(services, expose_request=False, debug=True)


The instance ``echoGateway`` is a callable object suitable to be
used as a Django view. To insert it into your url structure add
it to your ``urlconf``:

.. code-block:: python
   :linenos:
   
   # yourproject/urls.py

   urlpatterns = patterns('',

       # AMF Remoting Gateway
       (r'^gateway/', 'yourproject.yourapp.amfgateway.echoGateway'),
   )


To test the gateway you can use a Python AMF client like this:

.. literalinclude:: ../examples/gateways/django/client.py
   :linenos:


Useful Resources
================

:doc:`../actionscript/bytearray`
   ByteArray example using Flex and Django.

:doc:`../actionscript/shell`
   Python Shell example with Flex and Django.

http://api.pyamf.org/0.5.1/toc-pyamf.remoting.gateway.django-module.html
   DjangoGateway in the API documentation.

http://joelhooks.com/2008/09/21/django-authorization-from-flex-air-actionscript-via-pyamf
   Joel Hooks - Communication with Django from Flex


.. _Django: http://www.djangoproject.com
