**********
  Client 
**********

.. topic:: Introduction

   PyAMF isn't just about the Adobe Flash Player talking to a Python
   backend, oh no. We have put together a client module which allows
   you to make AMF calls to an HTTP Gateway, whether that be PyAMF or
   `other AMF implementations`_. If you come from a Adobe Flash
   background, this API should feel very natural to you.

.. contents::

Examples
========

The examples below are working, so feel free to try this out right now.


Basic Example
-------------

This example connects to a AMF gateway running at
``http://demo.pyamf.org/gateway/recordset`` and invokes the remote Python
``getLanguages`` method that is mapped to ``service.getLanguages``.
The result is printed on stdout.

.. literalinclude:: ../examples/general/client/basic.py
    :linenos:


Authentication
--------------

Use ``setCredentials(username, password)`` to authenticate with an
AMF client:

.. literalinclude:: ../examples/general/client/authentication.py
    :linenos:


Logging
-------

Enable logging with a ``DEBUG`` level to log messages including the timestamp
and level name.

.. literalinclude:: ../examples/general/client/logger.py
    :linenos:


AMF Version
-----------

:data:`AMF0 <pyamf.AMF0>` is the default AMF encoding used by the client. You can force it to use AMF3 by
supplying the `amf_version` keyword to the :class:`RemotingService <pyamf.remoting.client.RemotingService>`.
See :data:`pyamf.ENCODING_TYPES` for more info.

.. literalinclude:: ../examples/general/client/amf_version.py
    :linenos:


User-Agent
----------

By default the client identifies itself with a 'PyAMF/x.x' user agent header. You can modify
this by providing a custom `user_agent` keyword to your :class:`RemotingService <pyamf.remoting.client.RemotingService>`.
The example client below will be seen as 'MyApp/0.1.0' by the server.

.. literalinclude:: ../examples/general/client/user_agent.py
    :linenos:


Referer
-------

The referer also provides the client a way to identify itself, similar to the `user_agent` in
the previous example. You can modify this by providing a custom `referrer` keyword to your
:class:`RemotingService <pyamf.remoting.client.RemotingService>`. The example client below will
be seen as 'client.py' by the server. The default is `None`.

.. literalinclude:: ../examples/general/client/referer.py
    :linenos:


HTTP Headers
------------

You can modify the headers of the HTTP request using this convenient API:

.. literalinclude:: ../examples/general/client/headers.py
    :linenos:


Exception Handling
------------------

As of PyAMF 0.6, the client will now raise an appropriate error if remoting
call returns an error. The default behaviour is to raise a
:class:`RemotingError <pyamf.remoting.RemotingError>` but this behaviour can be modified:

.. code-block:: python

    # service method
    def type_error():
        raise TypeError('some useful message here')

And from the console:

.. literalinclude:: ../examples/general/client/exception.py


The gateway returns an error code which is mapped to an exception class. A number of built-in
exceptions are automatically mapped:

- ``TypeError``
- ``LookupError``
- ``KeyError``
- ``IndexError``
- ``NameError``

Use :func:`pyamf.add_error_class` to add new code/class combos and
:func:`pyamf.remove_error_class` to remove classes.


More
====

Check the `API docs`_ for more information. The source for the
:doc:`../actionscript/recordset` example is also available.


.. _other AMF implementations: http://en.wikipedia.org/wiki/Action_Message_Format
.. _API docs: http://api.pyamf.org
