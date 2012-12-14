******************
  Authentication
******************

.. topic:: Introduction

   The basic authentication examples show how to use authentication
   for PyAMF with other AMF clients and servers.

   This approach to authentication will work because the PyAMF client
   is using "standard" remoting requests under the hood.

.. contents::

**Warning**: Authentication and authorization via RemoteObject will be
supported through the Plasma_ project in the future, but until then
requests can be made to your services without having the authenticator
called.

Python
------

Python_ AMF examples are available for:

- `client <../../examples/general/authentication/python/client.py>`_
- `server <../../examples/general/authentication/python/server.py>`_


|ActionScript (TM)| examples are available for:

- :doc:`flex` -- MXML/|ActionScript (TM)| 3.0
- :doc:`as3` -- |ActionScript (TM)| 3.0
- :doc:`as2` -- |ActionScript (TM)| 2.0
- :doc:`ssa1` -- Server-Side |ActionScript (TM)|

.. toctree::
   :hidden:
   :maxdepth: 1

   flex.rst
   as3.rst
   as2.rst
   ssa1.rst


.. |ActionScript (TM)| unicode:: ActionScript U+2122
.. _Plasma: http://plasmads.org
.. _Python: http://python.org
