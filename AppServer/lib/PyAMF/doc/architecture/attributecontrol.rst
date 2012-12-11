*********************
  Attribute Control 
*********************

.. topic:: Introduction

   This document explains how to have more fine grain control over what
   gets encoded by PyAMF 0.5 and newer.

.. contents::

Control What Gets Encoded
=========================

A simple example is that of a user object. This ``User`` class has
``username`` and ``password`` attributes as well a number of meta
properties.

We are going to use the Google App Engine adapter for this example,
but the ideas apply in all situations.

.. literalinclude:: examples/attribute-control/models1.py
   :linenos:

This class is used in a (theoretical) PyAMF application to represent
``User`` objects through a gateway:

.. literalinclude:: examples/attribute-control/server.py
   :linenos:


Loading Users
-------------

Lets examine ``getUsers``. Assuming that ``User.all()`` worked as expected
a list of ``User`` objects would be returned to PyAMF for encoding which
is the expected behaviour. What is not the desired behaviour is that the
``password`` attribute will be encoded with each ``User`` object, thereby
handing all user passwords out to whomever desires them. Definitely **not**
a good idea! The best solution would be to completely remove the ``password``
attribute from each ``User`` object as it is encoded.

.. literalinclude:: examples/attribute-control/models2.py
   :linenos:

Notice the class attribute ``__amf__``. PyAMF looks for attributes on the
object class that contain instructions on how to handle encoding and
decoding instances.

The ``exclude`` property is a list of attributes that will be excluded from
encoding and removed from the instance if it exists in decoding. Setting
``exclude = ('password',)`` gives us the desired effect of not sending
the passwords of each ``User`` in the ``user.getUsersservice`` call.


Saving a User
-------------

The first argument of the ``UserService.saveUser`` method is a ``User`` object
that has been decoded by PyAMF and applied to the service method. Some type
checking might be in order here, because anything could be sent as the ``user``
payload.

.. code-block:: python
   :linenos:

    def saveUser(self, user):
        if not isinstance(user, User):
            raise TypeError('User expected')

        db.save(user)

So now we can ensure that any call to ``user.put`` will be an instance
(or subclass) of ``User``. Since we plan to persist the ``User`` object,
some validation is in order. If the correct attribute (``_key``) is sent
to PyAMF, the GAE Adapter will load the instance from the datastore and it
then applies the object attributes on top of this instance. This means that
if the ``_key`` is known to a malicious hacker, a malformed client request
could attempt to change the ``username`` property (or indeed change any
other property on the model). The same thing could apply to the ``password``
field, but that has been solved by excluding it in the previous section.

Certainly something we don't want to happen!

.. literalinclude:: examples/attribute-control/models3.py
   :linenos:

Notice the new ``readonly`` property. This should be pretty self-explanatory
but it is a list of attributes that are considered read-only when applying an
attribute collection to an instance, just after they have been decoded.


Other Things
============

Those are probably the two most used properties out of the way, so what else
is there?

- Static Attributes
- Proxied attributes
- ``IExternalizable`` classes
- Attribute whitelisting (aka public/private attributes)


Static Attributes
-----------------

A static attribute is an attribute that is expected to be on every instance
of a given class. A good example would be the primary key for an ORM object.
It allows the AMF payloads to be reduced substantially (using AMF3 only).

.. literalinclude:: examples/attribute-control/static-attr.py
   :linenos:

This means that the ``gender`` and ``dob`` attributes **must** be on every
instance of the ``Person`` class. Decoding an instance that does not have
these attributes will cause an ``AttributeError`` whilst decoding/encoding.


Proxied Attributes
------------------

Flex provides two classes that are 'bindable' (``ArrayCollection`` and
``ObjectProxy``), making things easier for Flex developers (plenty of
info/tutorial on the web!). A proxied attribute is purely AMF3 specific -
when encoding an attribute, if it is labeled as proxy then a proxied
version will be encoded. The reverse happens on decode, if a proxied
version is encountered then the unproxied version is returned. This
allows transparent proxying without having to disturb the underlying
'raw' attribute.

.. literalinclude:: examples/attribute-control/proxied-attr.py
   :linenos:


IExternalizable
---------------

AMF provides the opportunity for the developer to customise the
(de)serialisation of instances through the implementation of
``IExternalizable`` (once again, plenty of docs and tuts on the web).
PyAMF makes no exception.

To implement ``IExternalizable``:

.. literalinclude:: examples/attribute-control/iexternalizable.py
   :linenos:


Attribute whitelisting
----------------------

Sometimes it becomes necessary to ensure that when de/encoding instance
only a specified list of attributes is used. This could be for performance
or privacy reasons (there is no need to expose more than you have to).

Extending our ``User`` class from above:

.. literalinclude:: examples/attribute-control/whitelist.py
   :linenos:

Notice the new `dynamic` property in the `__amf__` meta declaration. This
instructs PyAMF to create an aggregated whitelist of attributes based on the
class and other instructions (as defined above) and restrict the encodable
and decodable attributes to within that list. Any attribute that is on the
instance that is not on the list is ignored.

**Note:** The ``dynamic`` property works for all types of Python classes, not
just Google AppEngine.


Synonyms
--------

It is possible to use object attribute names in Python that are not supported
in ActionScript. One such example is the name ``public``. Perfectly legal
syntax in Python but is a language construct in ActionScript 3. To support
this use-case, the 0.6 release provides the ability to support property
synonyms.

.. literalinclude:: examples/attribute-control/synonym.py
   :linenos:

The ``synonym`` declaration in the ``__amf__`` class attribute. This is a
``dict`` which maps the Python property names to their ActionScript
equivalent.
