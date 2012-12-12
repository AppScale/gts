#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#






"""Contains a metaclass and helper functions used to create
protocol message classes from Descriptor objects at runtime.

Recall that a metaclass is the "type" of a class.
(A class is to a metaclass what an instance is to a class.)

In this case, we use the GeneratedProtocolMessageType metaclass
to inject all the useful functionality into the classes
output by the protocol compiler at compile-time.

The upshot of all this is that the real implementation
details for ALL pure-Python protocol buffers are *here in
this file*.
"""



from google.net.proto2.python.internal import api_implementation
from google.net.proto2.python.public import descriptor as descriptor_mod
from google.net.proto2.python.public import message

_FieldDescriptor = descriptor_mod.FieldDescriptor


if api_implementation.Type() == 'cpp':
  if api_implementation.Version() == 2:
    from google.net.proto2.python.internal.cpp import cpp_message
    _NewMessage = cpp_message.NewMessage
    _InitMessage = cpp_message.InitMessage
  else:
    from google.net.proto2.python.internal import cpp_message
    _NewMessage = cpp_message.NewMessage
    _InitMessage = cpp_message.InitMessage
else:
  from google.net.proto2.python.internal import python_message
  _NewMessage = python_message.NewMessage
  _InitMessage = python_message.InitMessage


class GeneratedProtocolMessageType(type):

  """Metaclass for protocol message classes created at runtime from Descriptors.

  We add implementations for all methods described in the Message class.  We
  also create properties to allow getting/setting all fields in the protocol
  message.  Finally, we create slots to prevent users from accidentally
  "setting" nonexistent fields in the protocol message, which then wouldn't get
  serialized / deserialized properly.

  The protocol compiler currently uses this metaclass to create protocol
  message classes at runtime.  Clients can also manually create their own
  classes at runtime, as in this example:

  mydescriptor = Descriptor(.....)
  class MyProtoClass(Message):
    __metaclass__ = GeneratedProtocolMessageType
    DESCRIPTOR = mydescriptor
  myproto_instance = MyProtoClass()
  myproto.foo_field = 23
  ...
  """



  _DESCRIPTOR_KEY = 'DESCRIPTOR'

  def __new__(cls, name, bases, dictionary):
    """Custom allocation for runtime-generated class types.

    We override __new__ because this is apparently the only place
    where we can meaningfully set __slots__ on the class we're creating(?).
    (The interplay between metaclasses and slots is not very well-documented).

    Args:
      name: Name of the class (ignored, but required by the
        metaclass protocol).
      bases: Base classes of the class we're constructing.
        (Should be message.Message).  We ignore this field, but
        it's required by the metaclass protocol
      dictionary: The class dictionary of the class we're
        constructing.  dictionary[_DESCRIPTOR_KEY] must contain
        a Descriptor object describing this protocol message
        type.

    Returns:
      Newly-allocated class.
    """
    descriptor = dictionary[GeneratedProtocolMessageType._DESCRIPTOR_KEY]
    bases = _NewMessage(bases, descriptor, dictionary)
    superclass = super(GeneratedProtocolMessageType, cls)

    new_class = superclass.__new__(cls, name, bases, dictionary)
    setattr(descriptor, '_concrete_class', new_class)
    return new_class

  def __init__(cls, name, bases, dictionary):
    """Here we perform the majority of our work on the class.
    We add enum getters, an __init__ method, implementations
    of all Message methods, and properties for all fields
    in the protocol type.

    Args:
      name: Name of the class (ignored, but required by the
        metaclass protocol).
      bases: Base classes of the class we're constructing.
        (Should be message.Message).  We ignore this field, but
        it's required by the metaclass protocol
      dictionary: The class dictionary of the class we're
        constructing.  dictionary[_DESCRIPTOR_KEY] must contain
        a Descriptor object describing this protocol message
        type.
    """
    descriptor = dictionary[GeneratedProtocolMessageType._DESCRIPTOR_KEY]
    _InitMessage(descriptor, cls)
    superclass = super(GeneratedProtocolMessageType, cls)
    superclass.__init__(name, bases, dictionary)


def ParseMessage(descriptor, byte_str):
  """Generate a new Message instance from this Descriptor and a byte string.

  Args:
    descriptor: Protobuf Descriptor object
    byte_str: Serialized protocol buffer byte string

  Returns:
    Newly created protobuf Message object.
  """

  class _ResultClass(message.Message):
    __metaclass__ = GeneratedProtocolMessageType
    DESCRIPTOR = descriptor

  new_msg = _ResultClass()
  new_msg.ParseFromString(byte_str)
  return new_msg
