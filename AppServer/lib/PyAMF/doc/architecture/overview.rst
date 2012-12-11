============
  Features
============

Here's a brief description of the features in PyAMF. The
:doc:`CHANGES <../changelog>` document contains a more detailed
summary of all new features.

- :mod:`AMF0 <pyamf.amf0>` encoder/decoder for legacy Adobe Flash Players (version 6-8)
- :mod:`AMF3 <pyamf.amf3>` encoder/decoder for the new AMF format in Adobe Flash Player 9
  and newer
- Optional C-extension for maximum performance, created using `Cython`_
- Support for ``IExternalizable``, :class:`ArrayCollection <pyamf.flex.ArrayCollection>`,
  :class:`ObjectProxy <pyamf.flex.ObjectProxy>`, :class:`ByteArray <pyamf.amf3.ByteArray>`,
  :class:`RecordSet <pyamf.amf0.RecordSet>`, ``RemoteObject`` and ``more``
- Remoting gateways for :doc:`Twisted <../tutorials/gateways/twisted>`,
  :doc:`Django <../tutorials/gateways/django>`,
  :doc:`Google App Engine <../tutorials/gateways/appengine>`,
  :doc:`Pylons <../tutorials/gateways/pylons>`,
  :doc:`TurboGears2 <../tutorials/gateways/turbogears>`,
  :doc:`web2py <../tutorials/gateways/web2py>`, and any compatible WSGI_ framework
- :doc:`Adapter framework <../architecture/adapters>` to integrate
  nicely with third-party Python projects including
  :doc:`Django <../tutorials/gateways/django>`,
  :doc:`Google App Engine <../tutorials/gateways/appengine>` and
  :doc:`SQLAlchemy <../tutorials/gateways/sqlalchemy>`
- :doc:`Authentication <../tutorials/general/authentication/index>`/``setCredentials`` support
- Python AMF :doc:`client <../tutorials/general/client>` with HTTP(S)
  and authentication support
- Service Browser requests supported
- :doc:`Local Shared Object <../tutorials/general/sharedobject>`
  support

Also see the our plans for :doc:`future development <future>`.


.. _WSGI: http://wsgi.org
.. _Cython: http://cython.org
