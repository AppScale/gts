**********
  Ant 
**********

.. image:: images/ant-logo.gif

.. topic:: Introduction

    `Apache Ant`_ is a Java-based build tool. Ant build files are created
    using XML but it also support Python scripts using Jython_.

    This howto was tested with Jython 2.5.0 standalone, PyAMF 0.5,
    Ant 1.7 and Java JDK 1.6.0_13 on Mac OSX 10.5.7.

.. contents::


About JSR-223
=============

There are 2 ways to execute Python scripts in Ant:

- using JSR-223_
- utilising_ the ``PythonInterpreter``

JSR-223 enables dynamic languages to be callable via Java in a seamless
manner, which is supported in Jython 2.2.1 and newer. This howto will
show you how to make use of the ``PythonInterpreter`` class directly.

This style of embedding code is very similar to making use of a
scripting engine, and it has the advantage of working with Jython 2.5
and newer. The JSR-223 requires the unreleased Jython 2.5.1 or newer.
In order to make use of the ``PythonInterpreter`` technique, you only
need to have the standalone ``jython.jar`` in your classpath, there
is no need to have an extra engine involved.


Application Setup
=================

Start out with checking whether Apache Ant is working:

.. code-block:: bash
 
   ant -version

Returns the version number::

  Apache Ant version 1.7.0 compiled on May 21 2009

Make a project folder::

  mkdir jython-ant
  cd jython-ant

Grab a copy of PyAMF and it's documentation from Git:

.. code-block:: bash

  git clone git://github.com/hydralabs/pyamf.git
  cp -R pyamf/doc/tutorials/examples/jython/ant/embedded/* .

Copy ``jython.jar`` from your Jython 2.5 distribution folder
into the project's ``jython`` folder. Make sure you installed
Jython 2.5 in standalone mode which produces a ``jython.jar``
file that contains all necessary files for your application
to run without any other Jython dependencies:

.. code-block:: bash

  mkdir jython
  cp /path/to/jython2.5.x/jython.jar jython/

This ``jython`` folder is on the classpath of your application
so any other ``.jar`` files you may have go in here as well.

Now copy the PyAMF source and put it in the ``jython/Lib``
folder:

.. code-block:: bash

  mkdir jython/Lib
  cp -R pyamf/pyamf jython/Lib/


Run Application
===============

Run Ant from the project's base folder:

.. code-block:: bash

  ant

This will do the following for you:

- clean the ``build`` folder
- compile the ``src/java/org/pyamf/HelloWorld.java`` class
  containing the ``PythonInterpreter``
- create a file called ``HelloWorld.jar`` in
  ``build/classes/org/pyamf`` containing the compiled Java
  ``.class`` file
- run the ``HelloWorld.jar`` application
- try to load the ``src/python/server.py`` script that contains the
  PyAMF remoting gateway for WSGI

It should print the build progress and application output::

  Buildfile: build.xml

  clean:

  compile:
    [mkdir] Created dir: /path/to/jython-ant/build/classes
    [javac] Compiling 1 source file to /path/to/jython-ant/build/classes

  jar:
    [mkdir] Created dir: /path/to/jython-ant/build/jar
      [jar] Building jar: /path/to/jython-ant/build/jar/HelloWorld.jar

  run:
     [java] *sys-package-mgr*: processing new jar, '/path/to/jython-ant/jython/jython.jar'
     [java] *sys-package-mgr*: processing new jar, '/path/to/jython-ant/build/jar/HelloWorld.jar'
     ...
     [java] Running AMF gateway on http://localhost:8000


The first time you run Ant it also includes some caching messages from Jython
that start with ``*sys-package-mgr*: processing new jar``.
The default folder where these cache files are stored is ``jython/cachedir``.

The final line shows your AMF gateway is up and running.
  

Clients
=======

Python
------

Run ``client.py`` in ``src/python/`` which should print:

.. code-block:: bash

   2009-07-20 00:00:32,669 INFO  [root] Connecting to http://localhost:8000
   2009-07-20 00:00:32,783 INFO  [root] Hello world!

And the server running in Ant should show some debug information::

  [java] 2009-07-19 23:48:59,756 DEBUG [root] remoting.decode start
  [java] 2009-07-19 23:49:00,190 DEBUG [root] Remoting target: u'echo.echo'
  [java] 2009-07-19 23:49:00,223 DEBUG [root] remoting.decode end
  [java] 2009-07-19 23:49:00,232 INFO  [root] AMF Request: <Envelope amfVersion=0 clientType=0>
  [java]  (u'/1', <Request target=u'echo.echo'>[u'Hello world!']</Request>)
  [java] </Envelope>
  [java] 2009-07-19 23:49:00,323 INFO  [root] AMF Response: <Envelope amfVersion=0 clientType=0>
  [java]  (u'/1', <Response status=/onResult>u'Hello world!'</Response>)
  [java] </Envelope>
  [java] 127.0.0.1 - - [19/Jul/2009 23:49:00] "POST / HTTP/1.1" 200 44

Flash
-----

The :doc:`Hello World <../general/helloworld/index>` examples should all work with this
example's ``server.py``.


.. _Apache Ant: http://ant.apache.org
.. _Jython: http://jython.org
.. _JSR-223: http://jythonpodcast.hostjava.net/jythonbook/chapter10.html#jsr-223
.. _utilising: http://jythonpodcast.hostjava.net/jythonbook/chapter10.html#utilizing-pythoninterpreter
