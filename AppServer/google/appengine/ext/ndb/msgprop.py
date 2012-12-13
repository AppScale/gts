"""MessageProperty -- a property storing ProtoRPC Message objects.

Basic usage:

Let's assume you have a protorpc.messages.Message subclass, like this:

  from protorpc import messages

  class Note(messages.Message):
    text = messages.StringField(1, required=True)
    when = messages.IntegerField(2)

Now suppose you'd like to store Notes in the datastore.  Create a
model class to hold your notes, as follows:

  from google.appengine.ext import ndb
  from google.appengine.ext.ndb import msgprop

  class NoteStore(ndb.Model):
    note = msgprop.MessageProperty(Note)
    name = ndb.StringProperty()

(The class name, 'NoteStore', and the property name, 'note', are yours
to choose.)

To store, a Note message, create a NoteStore entity and write it:

  ns = NoteStore(note=my_note, name='foo')
  key = ns.put()

To later retrieve the Note, read the NoteStore entity back:

  ns = key.get()
  my_note = ns.note

The MessageProperty class has many of the usual Property options:
  - name: optional datastore name
  - repeated: if True, stores a list of message values
  - required: if True, the message value cannot be None
  - default: optional default message value to store
  - choices: optional list of allowed choices (must all be messages)
  - validator: optional function to validate message values
  - verbose_name: optional long name for the property

However, MessageProperty does not support the 'indexed' option.
Instead, you can specify a list of field names that will be indexed,
like this:

  class MyStore(ndb.Model):
    author = ndb.StringProperty()
    note = msgprop.MessageProperty(Note, indexed_fields=['text', 'when'])

Now you can query for field values, like this:

  stores = MyStore.query(MyStore.note.when >= 123).fetch()

Note the similarity with StructuredProperty -- in fact,
MessageProperty inherits from StructuredProperty.  The main difference
is that StructuredProperty takes an Model subclass instead of a
protorpc.messages.Message subclass; and StructuredProperty doesn't
index any fields by default.

It works for nested messages (using MessageField) as well:

  class Notes(messages.Message):
    notes = messages.MessageField(Note, 1, repeated=True)

  class MyNotesStore(ndb.Model):
    author = ndb.StringProperty()
    foo = msgprop.MessageProperty(Notes,
                                  indexed_fields=['notes.text, 'notes.when'])

And given this value for indexed_fields, in this example you can also
query for subfields:

  stores = MyNoteStore.query(MyNoteStore.foo.notes.when < 123).fetch()

A final option for MessageProperty is 'protocol'.  This lets you
specify how the message object is serialized to the datastore.  The
values are protocol names as used by protorpc.remote.Protocols class.
Supported protocol names are 'protobuf' and 'protojson'; the default
is 'protobuf'.  (In the future this will use the global protocols
registry that is being added to protorpc; then any registered protocol
name will be acceptable.)

There is also an EnumProperty, which can be used to store a
messages.Enum value without wrapping it in a Message object.  Example:

  class Color(messages.Enum):
    RED = 620
    GREEN = 495
    BLUE = 450

  class Part(ndb.Model):
    name = ndb.StringProperty()
    color = msgprop.EnumProperty(Color, required=True)

  p1 = Part(name='foo', color=Color.RED)
  key1 = p1.put()
  ...
  p2 = key1.get()
  print p2.name, p2.color  # prints "foo RED"

The EnumProperty stores the value as an integer; in fact, EnumProperty
is a subclass of IntegerProperty.  This is handy to know, since it
implies that you can rename your enum values without having to modify
already-stored entities, but you cannot renumber them.

The EnumProperty supports the following standard options:
  - name
  - indexed
  - repeated
  - required
  - default
  - choices
  - validator
  - verbose_name
"""

from protorpc import messages
from protorpc import remote

from . import model
from . import utils

__all__ = ['MessageProperty', 'EnumProperty']

# TODO: Use ProtoRPC's global Protocols instance once it is in the SDK.
_protocols_registry = remote.Protocols.new_default()
_default_protocol = 'protobuf'


class EnumProperty(model.IntegerProperty):
  """Enums are represented in the datastore as integers.

  While this is less user-friendly in the Datastore viewer, it matches
  the representation of enums in the protobuf serialization (although
  not in JSON), and it allows renaming enum values without requiring
  changes to values already stored in the Datastore.
  """

  _enum_type = None

  # Insert enum_type as an initial positional argument.
  _attributes = ['_enum_type'] + model.IntegerProperty._attributes
  _positional = 1 + model.IntegerProperty._positional

  @utils.positional(1 + _positional)
  def __init__(self, enum_type, name=None, default=None, choices=None, **kwds):
    """Constructor.

    Args:
      enum_type: A subclass of protorpc.messages.Enum.
      name: Optional datastore name (defaults to the property name).

    Additional keywords arguments specify the same options as
    supported by IntegerProperty.
    """
    self._enum_type = enum_type
    if default is not None:
      self._validate(default)
    if choices is not None:
      map(self._validate, choices)
    super(EnumProperty, self).__init__(name, default=default,
                                       choices=choices, **kwds)

  def _validate(self, value):
    """Validate an Enum value.

    Raises:
      TypeError if the value is not an instance of self._enum_type.
    """
    if not isinstance(value, self._enum_type):
      raise TypeError('Expected a %s instance, got %r instead' %
                      (self._enum_type.__name__, value))

  def _to_base_type(self, enum):
    """Convert an Enum value to a base type (integer) value."""
    return enum.number

  def _from_base_type(self, val):
    """Convert a base type (integer) value to an Enum value."""
    return self._enum_type(val)


def _analyze_indexed_fields(indexed_fields):
  """Internal helper to check a list of indexed fields.

  Args:
    indexed_fields: A list of names, possibly dotted names.

  (A dotted name is a string containing names separated by dots,
  e.g. 'foo.bar.baz'.  An undotted name is a string containing no
  dots, e.g. 'foo'.)

  Returns:
    A dict whose keys are undotted names.  For each undotted name in
    the argument, the dict contains that undotted name as a key with
    None as a value.  For each dotted name in the argument, the dict
    contains the first component as a key with a list of remainders as
    values.

  Example:
    If the argument is ['foo.bar.baz', 'bar', 'foo.bletch'], the return
    value is {'foo': ['bar.baz', 'bletch'], 'bar': None}.

  Raises:
    TypeError if an argument is not a string.
    ValueError for duplicate arguments and for conflicting arguments
      (when an undotted name also appears as the first component of
      a dotted name).
  """
  result = {}
  for field_name in indexed_fields:
    if not isinstance(field_name, basestring):
      raise TypeError('Field names must be strings; got %r' % (field_name,))
    if '.' not in field_name:
      if field_name in result:
        raise ValueError('Duplicate field name %s' % field_name)
      result[field_name] = None
    else:
      head, tail = field_name.split('.', 1)
      if head not in result:
        result[head] = [tail]
      elif result[head] is None:
        raise ValueError('Field name %s conflicts with ancestor %s' %
                         (field_name, head))
      else:
        result[head].append(tail)
  return result


def _make_model_class(message_type, indexed_fields, **props):
  """Construct a Model subclass corresponding to a Message subclass.

  Args:
    message_type: A Message subclass.
    indexed_fields: A list of dotted and undotted field names.
    **props: Additional properties with which to seed the class.

  Returns:
    A Model subclass whose properties correspond to those fields of
    message_type whose field name is listed in indexed_fields, plus
    the properties specified by the **props arguments.  For dotted
    field names, a StructuredProperty is generated using a Model
    subclass created by a recursive call.

  Raises:
    Whatever _analyze_indexed_fields() raises.
    ValueError if a field name conflicts with a name in **props.
    ValueError if a field name is not valid field of message_type.
    ValueError if an undotted field name designates a MessageField.
  """
  analyzed = _analyze_indexed_fields(indexed_fields)
  for field_name, sub_fields in analyzed.iteritems():
    if field_name in props:
      raise ValueError('field name %s is reserved' % field_name)
    try:
      field = message_type.field_by_name(field_name)
    except KeyError:
      raise ValueError('Message type %s has no field named %s' %
                       (message_type.__name__, field_name))
    if isinstance(field, messages.MessageField):
      if not sub_fields:
        raise ValueError(
          'MessageField %s cannot be indexed, only sub-fields' % field_name)
      sub_model_class = _make_model_class(field.type, sub_fields)
      prop = model.StructuredProperty(sub_model_class, field_name,
                                      repeated=field.repeated)
    else:
      if sub_fields is not None:
        raise ValueError(
          'Unstructured field %s cannot have indexed sub-fields' % field_name)
      if isinstance(field, messages.EnumField):
        prop = EnumProperty(field.type, field_name, repeated=field.repeated)
      elif isinstance(field, messages.BytesField):
        prop = model.BlobProperty(field_name,
                                  repeated=field.repeated, indexed=True)
      else:
        # IntegerField, FloatField, BooleanField, StringField.
        prop = model.GenericProperty(field_name, repeated=field.repeated)
    props[field_name] = prop
  return model.MetaModel('_%s__Model' % message_type.__name__,
                         (model.Model,), props)


class MessageProperty(model.StructuredProperty):
  """Messages are represented in the datastore as structured properties.

  By default, the structured property has a single subproperty
  containing the serialized message.  This property is named 'blob_'
  in Python but __<protocol>__ in the Datastore, where <protocol> is
  the value of the protocol argument (default 'protobuf').
  """

  _message_type = None
  _indexed_fields = ()
  _protocol = _default_protocol
  _protocol_impl = None

  # *Replace* first positional argument with _message_type, since the
  # _modelclass attribute is synthetic.
  _attributes = (['_message_type'] + model.StructuredProperty._attributes[1:] +
                 ['_indexed_fields', '_protocol'])

  @utils.positional(1 + model.StructuredProperty._positional)
  def __init__(self, message_type, name=None,
               indexed_fields=None, protocol=None, **kwds):
    """Constructor.

    Args:
      message_tyoe: A subclass of protorpc.messages.Message.
      name: Optional datastore name (defaults to the property name).
      indexed_fields: Optional list of dotted and undotted field names.
      protocol: Optional protocol name default 'protobuf'.

    Additional keywords arguments specify the same options as
    supported by StructuredProperty, except 'indexed'.
    """
    if not (isinstance(message_type, type) and
            issubclass(message_type, messages.Message)):
      raise TypeError('MessageProperty argument must be a Message subclass')
    self._message_type = message_type
    if indexed_fields is not None:
      # TODO: Check they are all strings naming fields.
      self._indexed_fields = tuple(indexed_fields)
    # NOTE: Otherwise the class default i.e. (), prevails.
    if protocol is None:
      protocol = _default_protocol
    self._protocol = protocol
    self._protocol_impl = _protocols_registry.lookup_by_name(protocol)
    blob_prop = model.BlobProperty('__%s__' % self._protocol)
    # TODO: Solve this without reserving 'blob_'.
    message_class = _make_model_class(message_type, self._indexed_fields,
                                      blob_=blob_prop)
    super(MessageProperty, self).__init__(message_class, name, **kwds)

  def _validate(self, msg):
    """Validate an Enum value.

    Raises:
      TypeError if the value is not an instance of self._message_type.
    """
    if not isinstance(msg, self._message_type):
      raise TypeError('Expected a %s instance for %s property',
                      self._message_type.__name__,
                      self._code_name or self._name)

  def _to_base_type(self, msg):
    """Convert a Message value to a Model instance (entity)."""
    ent = _message_to_entity(msg, self._modelclass)
    ent.blob_ = self._protocol_impl.encode_message(msg)
    return ent

  def _from_base_type(self, ent):
    """Convert a Model instance (entity) to a Message value."""
    if ent._projection:
      # Projection query result.  Reconstitute the message from the fields.
      return _projected_entity_to_message(ent, self._message_type)

    blob = ent.blob_
    if blob is not None:
      protocol = self._protocol_impl
    else:
      # Perhaps it was written using a different protocol.
      protocol = None
      for name in _protocols_registry.names:
        key = '__%s__' % name
        if key in ent._values:
          blob = ent._values[key]
          if isinstance(blob, model._BaseValue):
            blob = blob.b_val
          protocol = _protocols_registry.lookup_by_name(name)
          break
    if blob is None or protocol is None:
      return None  # This will reveal the underlying dummy model.
    msg = protocol.decode_message(self._message_type, blob)
    return msg


def _message_to_entity(msg, modelclass):
  """Recursive helper for _to_base_type() to convert a message to an entity.

  Args:
    msg: A Message instance.
    modelclass: A Model subclass.

  Returns:
    An instance of modelclass.
  """
  ent = modelclass()
  for prop_name, prop in modelclass._properties.iteritems():
    if prop._code_name == 'blob_':  # TODO: Devise a cleaner test.
      continue  # That's taken care of later.
    value = getattr(msg, prop_name)
    if value is not None and isinstance(prop, model.StructuredProperty):
      if prop._repeated:
        value = [_message_to_entity(v, prop._modelclass) for v in value]
      else:
        value = _message_to_entity(value, prop._modelclass)
    setattr(ent, prop_name, value)
  return ent


def _projected_entity_to_message(ent, message_type):
  """Recursive helper for _from_base_type() to convert an entity to a message.

  Args:
    ent: A Model instance.
    message_type: A Message subclass.

  Returns:
    An instance of message_type.
  """
  msg = message_type()
  analyzed = _analyze_indexed_fields(ent._projection)
  for name, sublist in analyzed.iteritems():
    prop = ent._properties[name]
    val = prop._get_value(ent)
    assert isinstance(prop, model.StructuredProperty) == bool(sublist)
    if sublist:
      field = message_type.field_by_name(name)
      assert isinstance(field, messages.MessageField)
      assert prop._repeated == field.repeated
      if prop._repeated:
        assert isinstance(val, list)
        val = [_projected_entity_to_message(v, field.type) for v in val]
      else:
        assert isinstance(val, prop._modelclass)
        val = _projected_entity_to_message(val, field.type)
    setattr(msg, name, val)
  return msg
