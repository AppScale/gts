=====================
 AppScale API Server
=====================

A server that handles API requests from App Engine Standard Environment
runtime processes.

How to set up
=============

1. `Install a protocol buffer compiler`_
2. Generate the required Python classes:
   ``protoc --python_out=./appscale/api_server *.proto``
3. Install this package: ``pip install .``
4. Start the server with ``appscale-api-server``

.. _Install a protocol buffer compiler: https://github.com/google/protobuf
