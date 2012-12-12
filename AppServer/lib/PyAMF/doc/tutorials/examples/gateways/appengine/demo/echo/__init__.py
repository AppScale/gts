# -*- encoding: utf-8 -*-
#
# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Echo test core functionality. This module sets up the class
mappings related to the echo_test.swf client on the
U{EchoTest<http://pyamf.org/wiki/EchoTest>} wiki page.

@since: 0.1.0
"""

from pyamf import register_class

ECHO_NS = 'org.red5.server.webapp.echo'

class RemoteClass(object):
    """
    This Python class is mapped to the clientside ActionScript class.
    """
    pass

class ExternalizableClass(object):
    """
    An example of an externalizable class.
    """
    def __readamf__(self, input):
        """
        This function is invoked when the C{obj} needs to be deserialized.

        @type obj: L{ExternalizableClass}
        @param obj: The object in question.
        @param input: The input stream to read from.
        @type input L{DataInput<pyamf.amf3.DataInput>}
        """
        assert input.readBoolean() == True
        assert input.readBoolean() == False
        assert input.readByte() == 0
        assert input.readByte() == -1
        assert input.readByte() == 1
        assert input.readByte() == 127
        assert input.readByte() == -127
        assert input.readDouble() == 1.0
        assert input.readFloat() == 2.0
        assert input.readInt() == 0
        assert input.readInt() == -1
        assert input.readInt() == 1
        input.readMultiByte(7, 'iso-8859-1')
        input.readMultiByte(14, 'utf8')
        assert input.readObject() == [1, 'one', 1.0]
        assert input.readShort() == 0
        assert input.readShort() == -1
        assert input.readShort() == 1
        assert input.readUnsignedInt() == 0
        assert input.readUnsignedInt() == 1
        assert input.readUTF() == "Hello world!"
        assert input.readUTFBytes(12) == "Hello world!"

    def __writeamf__(self, output):
        """
        This function is invoked when the C{obj} needs to be serialized.

        @type obj: L{ExternalizableClass}
        @param obj: The object in question.
        @param input: The output stream to write to.
        @type input L{DataOutput<pyamf.amf3.DataOutput>}
        """
        output.writeBoolean(True)
        output.writeBoolean(False)
        output.writeByte(0)
        output.writeByte(-1)
        output.writeByte(1)
        output.writeByte(127)
        output.writeByte(-127)
        output.writeDouble(1.0)
        output.writeFloat(2.0)
        output.writeInt(0)
        output.writeInt(-1)
        output.writeInt(1)
        output.writeMultiByte(u"\xe4\xf6\xfc\xc4\xd6\xdc\xdf", 'iso-8859-1')
        output.writeMultiByte(u"\xe4\xf6\xfc\xc4\xd6\xdc\xdf", 'utf8')
        output.writeObject([1, 'one', 1])
        output.writeShort(0)
        output.writeShort(-1)
        output.writeShort(1)
        output.writeUnsignedInt(0)
        output.writeUnsignedInt(1)
        output.writeUTF("Hello world!")
        output.writeUTFBytes("Hello world!")

def echo(data):
    """
    Return data back to the client.

    @type data: C{mixed}
    @param data: Decoded AS->Python data.
    """
    return data

# Map ActionScript class to Python class
try:
    register_class(RemoteClass, '%s.%s' % (ECHO_NS, 'RemoteClass'))
except ValueError:
    pass
try:
    register_class(ExternalizableClass, '%s.%s' % (ECHO_NS, 
        'ExternalizableClass'), metadata=['external'])
except ValueError:
    pass
