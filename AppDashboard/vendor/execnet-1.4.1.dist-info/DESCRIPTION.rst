execnet: distributed Python deployment and communication
========================================================

.. _execnet: http://codespeak.net/execnet

execnet_ provides carefully tested means to ad-hoc interact with Python
interpreters across version, platform and network barriers.  It provides
a minimal and fast API targetting the following uses:

* distribute tasks to local or remote processes
* write and deploy hybrid multi-process applications
* write scripts to administer multiple hosts

Features
------------------

* zero-install bootstrapping: no remote installation required!

* flexible communication: send/receive as well as
  callback/queue mechanisms supported

* simple serialization of python builtin types (no pickling)

* grouped creation and robust termination of processes

* well tested between CPython 2.6-3.X, Jython 2.5.1 and PyPy 2.2
  interpreters.

* interoperable between Windows and Unix-ish systems.

* integrates with different threading models, including standard
  os threads, eventlet and gevent based systems.



