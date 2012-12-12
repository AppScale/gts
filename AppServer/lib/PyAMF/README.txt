PyAMF_ provides Action Message Format (AMF_) support for Python_ that is
compatible with the `Adobe Flash Player`_. It includes integration with
Python web frameworks like Django_, Pylons_, Twisted_, SQLAlchemy_,
web2py_ and more_.

The `Adobe Integrated Runtime`_ and `Adobe Flash Player`_ use AMF to
communicate between an application and a remote server. AMF encodes
remote procedure calls (RPC) into a compact binary representation that
can be transferred over HTTP/HTTPS or the `RTMP/RTMPS`_ protocol.
Objects and data values are serialized into this binary format, which
increases performance, allowing applications to load data up to 10 times
faster than with text-based formats such as XML or SOAP.

AMF3, the default serialization for ActionScript_ 3.0, provides various
advantages over AMF0, which is used for ActionScript 1.0 and 2.0. AMF3
sends data over the network more efficiently than AMF0. AMF3 supports
sending ``int`` and ``uint`` objects as integers and supports data types
that are available only in ActionScript 3.0, such as ByteArray_,
ArrayCollection_, ObjectProxy_ and IExternalizable_.


.. _PyAMF: 	http://www.pyamf.org
.. _AMF: 	http://en.wikipedia.org/wiki/Action_Message_Format
.. _Python:	http://python.org
.. _Adobe Flash Player: http://en.wikipedia.org/wiki/Flash_Player
.. _Django:	http://djangoproject.com
.. _Pylons:	http://pylonshq.com
.. _Twisted:	http://twistedmatrix.com
.. _SQLAlchemy: http://sqlalchemy.org
.. _web2py:	http://www.web2py.com
.. _more:	http://pyamf.org/tutorials/index.html
.. _Adobe Integrated Runtime: http://en.wikipedia.org/wiki/Adobe_AIR
.. _RTMP/RTMPS:	http://en.wikipedia.org/wiki/Real_Time_Messaging_Protocol
.. _ActionScript: http://dev.pyamf.org/wiki/ActionScript
.. _ByteArray:	http://dev.pyamf.org/wiki/ByteArray
.. _ArrayCollection: http://dev.pyamf.org/wiki/ArrayCollection
.. _ObjectProxy: http://dev.pyamf.org/wiki/ObjectProxy
.. _IExternalizable: http://dev.pyamf.org/wiki/IExternalizable
