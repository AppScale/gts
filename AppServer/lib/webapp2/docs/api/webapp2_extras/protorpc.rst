.. _api.webapp2_extras.protorpc:

ProtoRPC
========
.. module:: webapp2_extras.protorpc

``webapp2_extras.protorpc`` makes webapp2 compatible with ProtoRPC services.
You can register service mappings in a normal webapp2 WSGI application, and it
will be fully compatible with the ProtoRPC library.

Check the `ProtoRPC documentation`_ or the `ProtoRPC project page`_ for usage
details.

.. warning::
   This is an experimental package, as the ProtoRPC API is not stable yet.
   ``webapp2_extras.protorpc`` is compatible with the ProtoRPC version shipped
   with the App Engine SDK (since version 1.5.1).

.. autofunction:: service_mapping
.. autofunction:: get_app
.. autofunction:: run_services


.. _ProtoRPC documentation: http://code.google.com/appengine/docs/python/tools/protorpc/overview.html
.. _ProtoRPC project page: http://code.google.com/p/google-protorpc/
