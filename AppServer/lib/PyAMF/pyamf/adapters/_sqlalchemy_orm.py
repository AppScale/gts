# Copyright (c) The PyAMF Project.
# See LICENSE for details.

"""
SQLAlchemy adapter module.

@see: U{SQLAlchemy homepage<http://www.sqlalchemy.org>}

@since: 0.4
"""

from sqlalchemy import orm, __version__

try:
    from sqlalchemy.orm import class_mapper
except ImportError:
    from sqlalchemy.orm.util import class_mapper

import pyamf

UnmappedInstanceError = None

try:
    class_mapper(dict)
except Exception, e:
    UnmappedInstanceError = e.__class__


class_checkers = []


class SaMappedClassAlias(pyamf.ClassAlias):
    KEY_ATTR = 'sa_key'
    LAZY_ATTR = 'sa_lazy'
    EXCLUDED_ATTRS = [
        '_entity_name', '_instance_key', '_sa_adapter', '_sa_appender',
        '_sa_class_manager', '_sa_initiator', '_sa_instance_state',
        '_sa_instrumented', '_sa_iterator', '_sa_remover', '_sa_session_id',
        '_state'
    ]

    STATE_ATTR = '_sa_instance_state'

    if __version__.startswith('0.4'):
        STATE_ATTR = '_state'

    def getCustomProperties(self):
        self.mapper = class_mapper(self.klass)
        self.exclude_attrs.update(self.EXCLUDED_ATTRS)

        self.properties = []

        for prop in self.mapper.iterate_properties:
            self.properties.append(prop.key)

        self.encodable_properties.update(self.properties)
        self.decodable_properties.update(self.properties)

        self.exclude_sa_key = self.KEY_ATTR in self.exclude_attrs
        self.exclude_sa_lazy = self.LAZY_ATTR in self.exclude_attrs

    def getEncodableAttributes(self, obj, **kwargs):
        """
        Returns a C{tuple} containing a dict of static and dynamic attributes
        for C{obj}.
        """
        attrs = pyamf.ClassAlias.getEncodableAttributes(self, obj, **kwargs)

        if not self.exclude_sa_key:
            # primary_key_from_instance actually changes obj.__dict__ if
            # primary key properties do not already exist in obj.__dict__
            attrs[self.KEY_ATTR] = self.mapper.primary_key_from_instance(obj)

        if not self.exclude_sa_lazy:
            lazy_attrs = []

            for attr in self.properties:
                if attr not in obj.__dict__:
                    lazy_attrs.append(attr)

            attrs[self.LAZY_ATTR] = lazy_attrs

        return attrs

    def getDecodableAttributes(self, obj, attrs, **kwargs):
        """
        """
        attrs = pyamf.ClassAlias.getDecodableAttributes(self, obj, attrs, **kwargs)

        # Delete lazy-loaded attrs.
        #
        # Doing it this way ensures that lazy-loaded attributes are not
        # attached to the object, even if there is a default value specified
        # in the __init__ method.
        #
        # This is the correct behavior, because SQLAlchemy ignores __init__.
        # So, an object retreived from a DB with SQLAlchemy will not have a
        # lazy-loaded value, even if __init__ specifies a default value.
        if self.LAZY_ATTR in attrs:
            obj_state = None

            if hasattr(orm.attributes, 'instance_state'):
                obj_state = orm.attributes.instance_state(obj)

            for lazy_attr in attrs[self.LAZY_ATTR]:
                if lazy_attr in obj.__dict__:
                    # Delete directly from the dict, so
                    # SA callbacks are not triggered.
                    del obj.__dict__[lazy_attr]

                # Delete from committed_state so SA thinks this attribute was
                # never modified.
                #
                # If the attribute was set in the __init__ method,
                # SA will think it is modified and will try to update
                # it in the database.
                if obj_state is not None:
                    if lazy_attr in obj_state.committed_state:
                        del obj_state.committed_state[lazy_attr]
                    if lazy_attr in obj_state.dict:
                        del obj_state.dict[lazy_attr]

                if lazy_attr in attrs:
                    del attrs[lazy_attr]

            del attrs[self.LAZY_ATTR]

        if self.KEY_ATTR in attrs:
            del attrs[self.KEY_ATTR]

        return attrs

    def createInstance(self, *args, **kwargs):
        self.compile()

        return self.mapper.class_manager.new_instance()


def is_class_sa_mapped(klass):
    """
    @rtype: C{bool}
    """
    if not isinstance(klass, type):
        klass = type(klass)

    for c in class_checkers:
        if c(klass):
            return False

    try:
        class_mapper(klass)
    except UnmappedInstanceError:
        return False

    return True

pyamf.register_alias_type(SaMappedClassAlias, is_class_sa_mapped)
