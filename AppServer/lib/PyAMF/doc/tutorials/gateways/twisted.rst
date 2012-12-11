*************
  Twisted 
*************

.. topic:: Introduction

  Twisted_ is a powerful Internet framework allowing you to develop
  networked applications quickly.

  PyAMF features the ``TwistedGateway`` that allows you to bridge the gap
  between your Twisted application and AMF based programs.

.. contents::

Examples
========

Classic
-------

The following example is the 'classic' way of setting up a Twisted web
service, where you import the reactor manually and start it yourself.
For the current, canonical way of setting up a service, see the next
section.

The example below is a complete standalone ``twisted.web`` server that
exposes various functions via PyAMF. We added comments to attempt to
explain all relevant lines of code:

.. literalinclude:: ../examples/gateways/twisted/classic.py
   :linenos:


The gateway supports returning a Deferred from your callable. If you are
not familiar with Deferreds you should check out the
`Twisted documentation`_.

Hopefully this gives you a basic understanding of how to expose functions
within Twisted.


Preferred Method
----------------

Here is the same service, designed to be run with ``twistd``:

.. literalinclude:: ../examples/gateways/twisted/preferred.py
   :linenos:


WSGI
----

You can also use Twisted WSGI support in combination with PyAMF
``WSGIGateway`` like this:

.. literalinclude:: ../examples/gateways/twisted/wsgi.py
   :linenos:


Run the example using twistd
============================

Save this in a file called something like ``mytest.tac`` and then start the
web server with the following command:

.. code-block:: bash

   twistd -noy mytest.tac

Using Twisted's twistd_ commandline tool and a ``.tac`` file is good for
many reasons. Here are some highlights:

- Using this infrastructure frees you from from having to write a
  large amount of boilerplate code by hooking your application into
  existing tools that manage daemonization, logging, choosing a reactor
  and more.
- This provides a convenient and standard methodology for separating
  Twisted services and service configuration from the rest of your
  project (i.e., the code upon which your service(s) depend).
- It's easy to run with a daemon manager (e.g. daemontools_).


Test the example
================

To test the gateway you can use a Python AMF client like this:

.. literalinclude:: ../examples/gateways/twisted/client.py
   :linenos:


Other Twisted Examples
======================

:doc:`../actionscript/socket`
   Binary Socket using Twisted and Flex.

:doc:`../actionscript/guestbook`
   Simple guestbook using Twisted and Flex.

http://www.artima.com/weblogs/viewpost.jsp?thread=230001
   Concurrency with Python, Twisted, and Flex.

:doc:`stackless`
   Using Stackless Python and Twisted.


.. _Twisted:			http://twistedmatrix.com
.. _Twisted documentation:	http://twistedmatrix.com/documents/current/core/howto/defer.html
.. _twistd:			http://twistedmatrix.com/documents/current/core/howto/application.html#auto4
.. _daemontools:		http://cr.yp.to/daemontools.html
