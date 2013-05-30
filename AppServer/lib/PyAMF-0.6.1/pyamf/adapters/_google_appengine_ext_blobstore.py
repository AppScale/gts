# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Adapter module for U{google.appengine.ext.blobstore<http://
code.google.com/appengine/docs/python/blobstore/>}.

@since: 0.6
"""

from google.appengine.ext import blobstore

import pyamf


bi = blobstore.BlobInfo


class BlobInfoStub(object):
    """
    Since C{blobstore.BlobInfo} requires __init__ args, we stub the object until
    C{applyAttributes} is called which then magically converts it to the correct
    type.
    """


class BlobInfoClassAlias(pyamf.ClassAlias):
    """
    Fine grain control over C{blobstore.BlobInfo} instances. Required to encode
    the C{key} attribute correctly.
    """

    def createInstance(self, *args, **kwargs):
        return BlobInfoStub()

    def getEncodableAttributes(self, obj, codec=None):
        """
        Returns a dict of kay/value pairs for PyAMF to encode.
        """
        attrs = {
            'content_type': obj.content_type,
            'filename': obj.filename,
            'size': obj.size,
            'creation': obj.creation,
            'key': str(obj.key())
        }

        return attrs

    def applyAttributes(self, obj, attrs, **kwargs):
        """
        Applies C{attrs} to C{obj}. Since C{blobstore.BlobInfo} objects are
        read-only entities, we only care about the C{key} attribute.
        """
        assert type(obj) is BlobInfoStub

        key = attrs.pop('key', None)

        if not key:
            raise pyamf.DecodeError("Unable to build blobstore.BlobInfo "
                "instance. Missing 'key' attribute.")

        try:
            key = blobstore.BlobKey(key)
        except:
            raise pyamf.DecodeError("Unable to build a valid blobstore.BlobKey "
                "instance. Key supplied was %r" % (key,))

        obj.__class__ = blobstore.BlobInfo

        obj.__init__(key)


pyamf.register_alias_type(BlobInfoClassAlias, bi)
pyamf.register_class(bi, '.'.join([blobstore.__name__, bi.__name__]))

del bi
