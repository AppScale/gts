# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Google App Engine adapter module.

Sets up basic type mapping and class mappings for using the Datastore API
in Google App Engine.

@see: U{Datastore API on Google App Engine<http://
    code.google.com/appengine/docs/python/datastore>}
@since: 0.3.1
"""

from google.appengine.ext import db
from google.appengine.ext.db import polymodel
import datetime

import pyamf
from pyamf.adapters import util


class ModelStub(object):
    """
    This class represents a C{db.Model} or C{db.Expando} class as the typed
    object is being read from the AMF stream. Once the attributes have been
    read from the stream and through the magic of Python, the instance of this
    class will be converted into the correct type.

    @ivar klass: The referenced class either C{db.Model} or C{db.Expando}.
        This is used so we can proxy some of the method calls during decoding.
    @type klass: C{db.Model} or C{db.Expando}
    @see: L{DataStoreClassAlias.applyAttributes}
    """

    def __init__(self, klass):
        self.klass = klass

    def properties(self):
        return self.klass.properties()

    def dynamic_properties(self):
        return []


class GAEReferenceCollection(dict):
    """
    This helper class holds a dict of klass to key/objects loaded from the
    Datastore.

    @since: 0.4.1
    """

    def _getClass(self, klass):
        if not issubclass(klass, (db.Model, db.Expando)):
            raise TypeError('expected db.Model/db.Expando class, got %s' % (klass,))

        return self.setdefault(klass, {})

    def getClassKey(self, klass, key):
        """
        Return an instance based on klass/key.

        If an instance cannot be found then C{KeyError} is raised.

        @param klass: The class of the instance.
        @param key: The key of the instance.
        @return: The instance linked to the C{klass}/C{key}.
        @rtype: Instance of L{klass}.
        """
        d = self._getClass(klass)

        return d[key]

    def addClassKey(self, klass, key, obj):
        """
        Adds an object to the collection, based on klass and key.

        @param klass: The class of the object.
        @param key: The datastore key of the object.
        @param obj: The loaded instance from the datastore.
        """
        d = self._getClass(klass)

        d[key] = obj


class DataStoreClassAlias(pyamf.ClassAlias):
    """
    This class contains all the business logic to interact with Google's
    Datastore API's. Any C{db.Model} or C{db.Expando} classes will use this
    class alias for encoding/decoding.

    We also add a number of indexes to the encoder context to aggressively
    decrease the number of Datastore API's that we need to complete.
    """

    # The name of the attribute used to represent the key
    KEY_ATTR = '_key'

    def _compile_base_class(self, klass):
        if klass in (db.Model, polymodel.PolyModel):
            return

        pyamf.ClassAlias._compile_base_class(self, klass)

    def getCustomProperties(self):
        props = [self.KEY_ATTR]
        self.reference_properties = {}
        self.properties = {}
        reverse_props = []

        for name, prop in self.klass.properties().iteritems():
            self.properties[name] = prop

            props.append(name)

            if isinstance(prop, db.ReferenceProperty):
                self.reference_properties[name] = prop

        if issubclass(self.klass, polymodel.PolyModel):
            del self.properties['_class']
            props.remove('_class')

        # check if the property is a defined as a collection_name. These types
        # of properties are read-only and the datastore freaks out if you
        # attempt to meddle with it. We delete the attribute entirely ..
        for name, value in self.klass.__dict__.iteritems():
            if isinstance(value, db._ReverseReferenceProperty):
                reverse_props.append(name)

        self.encodable_properties.update(self.properties.keys())
        self.decodable_properties.update(self.properties.keys())
        self.readonly_attrs.update(reverse_props)

        if not self.reference_properties:
            self.reference_properties = None

        if not self.properties:
            self.properties = None

        self.no_key_attr = self.KEY_ATTR in self.exclude_attrs

    def getEncodableAttributes(self, obj, codec=None):
        attrs = pyamf.ClassAlias.getEncodableAttributes(self, obj, codec=codec)

        gae_objects = getGAEObjects(codec.context) if codec else None

        if self.reference_properties and gae_objects:
            for name, prop in self.reference_properties.iteritems():
                klass = prop.reference_class
                key = prop.get_value_for_datastore(obj)

                if not key:
                    continue

                try:
                    attrs[name] = gae_objects.getClassKey(klass, key)
                except KeyError:
                    ref_obj = getattr(obj, name)
                    gae_objects.addClassKey(klass, key, ref_obj)
                    attrs[name] = ref_obj

        for k in attrs.keys()[:]:
            if k.startswith('_'):
                del attrs[k]

        for attr in obj.dynamic_properties():
            attrs[attr] = getattr(obj, attr)

        if not self.no_key_attr:
            attrs[self.KEY_ATTR] = str(obj.key()) if obj.is_saved() else None

        return attrs

    def createInstance(self, codec=None):
        return ModelStub(self.klass)

    def getDecodableAttributes(self, obj, attrs, codec=None):
        key = attrs.setdefault(self.KEY_ATTR, None)
        attrs = pyamf.ClassAlias.getDecodableAttributes(self, obj, attrs, codec=codec)

        del attrs[self.KEY_ATTR]
        new_obj = None

        # attempt to load the object from the datastore if KEY_ATTR exists.
        if key and codec:
            new_obj = loadInstanceFromDatastore(self.klass, key, codec)

        # clean up the stub
        if isinstance(obj, ModelStub) and hasattr(obj, 'klass'):
            del obj.klass

        if new_obj:
            obj.__dict__ = new_obj.__dict__.copy()

        obj.__class__ = self.klass
        apply_init = True

        if self.properties:
            for k in [k for k in attrs.keys() if k in self.properties.keys()]:
                prop = self.properties[k]
                v = attrs[k]

                if isinstance(prop, db.FloatProperty) and isinstance(v, (int, long)):
                    attrs[k] = float(v)
                elif isinstance(prop, db.IntegerProperty) and isinstance(v, float):
                    x = long(v)

                    # only convert the type if there is no mantissa - otherwise
                    # let the chips fall where they may
                    if x == v:
                        attrs[k] = x
                elif isinstance(prop, db.ListProperty) and v is None:
                    attrs[k] = []
                elif isinstance(v, datetime.datetime):
                    # Date/Time Property fields expect specific types of data
                    # whereas PyAMF only decodes into datetime.datetime objects.
                    if isinstance(prop, db.DateProperty):
                        attrs[k] = v.date()
                    elif isinstance(prop, db.TimeProperty):
                        attrs[k] = v.time()

                if new_obj is None and isinstance(v, ModelStub) and prop.required and k in self.reference_properties:
                    apply_init = False
                    del attrs[k]

        # If the object does not exist in the datastore, we must fire the
        # class constructor. This sets internal attributes that pyamf has
        # no business messing with ..
        if new_obj is None and apply_init is True:
            obj.__init__(**attrs)

        return attrs


def getGAEObjects(context):
    """
    Returns a reference to the C{gae_objects} on the context. If it doesn't
    exist then it is created.

    @param context: The context to load the C{gae_objects} index from.
    @return: The C{gae_objects} index reference.
    @rtype: Instance of L{GAEReferenceCollection}
    @since: 0.4.1
    """
    return context.extra.setdefault('gae_objects', GAEReferenceCollection())


def loadInstanceFromDatastore(klass, key, codec=None):
    """
    Attempt to load an instance from the datastore, based on C{klass}
    and C{key}. We create an index on the codec's context (if it exists)
    so we can check that first before accessing the datastore.

    @param klass: The class that will be loaded from the datastore.
    @type klass: Sub-class of C{db.Model} or C{db.Expando}
    @param key: The key which is used to uniquely identify the instance in the
        datastore.
    @type key: C{str}
    @param codec: The codec to reference the C{gae_objects} index. If
        supplied,The codec must have have a context attribute.
    @return: The loaded instance from the datastore.
    @rtype: Instance of C{klass}.
    @since: 0.4.1
    """
    if not issubclass(klass, (db.Model, db.Expando)):
        raise TypeError('expected db.Model/db.Expando class, got %s' % (klass,))

    if not isinstance(key, basestring):
        raise TypeError('string expected for key, got %s', (repr(key),))

    key = str(key)

    if codec is None:
        return klass.get(key)

    gae_objects = getGAEObjects(codec.context)

    try:
        return gae_objects.getClassKey(klass, key)
    except KeyError:
        pass

    obj = klass.get(key)
    gae_objects.addClassKey(klass, key, obj)

    return obj


def writeGAEObject(obj, encoder=None):
    """
    The GAE Datastore creates new instances of objects for each get request.
    This is a problem for PyAMF as it uses the id(obj) of the object to do
    reference checking.

    We could just ignore the problem, but the objects are conceptually the
    same so the effort should be made to attempt to resolve references for a
    given object graph.

    We create a new map on the encoder context object which contains a dict of
    C{object.__class__: {key1: object1, key2: object2, .., keyn: objectn}}. We
    use the datastore key to do the reference checking.

    @since: 0.4.1
    """
    if not obj.is_saved():
        encoder.writeObject(obj)

        return

    context = encoder.context
    kls = obj.__class__
    s = obj.key()

    gae_objects = getGAEObjects(context)

    try:
        referenced_object = gae_objects.getClassKey(kls, s)
    except KeyError:
        referenced_object = obj
        gae_objects.addClassKey(kls, s, obj)

    encoder.writeObject(referenced_object)


# initialise the module here: hook into pyamf

pyamf.register_alias_type(DataStoreClassAlias, db.Model)
pyamf.add_type(db.Query, util.to_list)
pyamf.add_type(db.Model, writeGAEObject)
