# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Flex Messaging implementation.

This module contains the message classes used with Flex Data Services.

@see: U{RemoteObject on OSFlash (external)
<http://osflash.org/documentation/amf3#remoteobject>}

@since: 0.1
"""

import uuid

import pyamf.util
from pyamf import amf3


__all__ = [
    'RemotingMessage',
    'CommandMessage',
    'AcknowledgeMessage',
    'ErrorMessage',
    'AbstractMessage',
    'AsyncMessage'
]

NAMESPACE = 'flex.messaging.messages'

SMALL_FLAG_MORE = 0x80


class AbstractMessage(object):
    """
    Abstract base class for all Flex messages.

    Messages have two customizable sections; headers and data. The headers
    property provides access to specialized meta information for a specific
    message instance. The data property contains the instance specific data
    that needs to be delivered and processed by the decoder.

    @see: U{AbstractMessage on Livedocs<http://
        livedocs.adobe.com/flex/201/langref/mx/messaging/messages/AbstractMessage.html>}

    @ivar body: Specific data that needs to be delivered to the remote
        destination.
    @type body: C{mixed}
    @ivar clientId: Indicates which client sent the message.
    @type clientId: C{str}
    @ivar destination: Message destination.
    @type destination: C{str}
    @ivar headers: Message headers. Core header names start with DS.
    @type headers: C{dict}
    @ivar messageId: Unique Message ID.
    @type messageId: C{str}
    @ivar timeToLive: How long the message should be considered valid and
        deliverable.
    @type timeToLive: C{int}
    @ivar timestamp: Timestamp when the message was generated.
    @type timestamp: C{int}
    """

    class __amf__:
        amf3 = True
        static = ('body', 'clientId', 'destination', 'headers', 'messageId',
            'timestamp', 'timeToLive')

    #: Each message pushed from the server will contain this header identifying
    #: the client that will receive the message.
    DESTINATION_CLIENT_ID_HEADER = "DSDstClientId"
    #: Messages are tagged with the endpoint id for the channel they are sent
    #: over.
    ENDPOINT_HEADER = "DSEndpoint"
    #: Messages that need to set remote credentials for a destination carry the
    #: C{Base64} encoded credentials in this header.
    REMOTE_CREDENTIALS_HEADER = "DSRemoteCredentials"
    #: The request timeout value is set on outbound messages by services or
    #: channels and the value controls how long the responder will wait for an
    #: acknowledgement, result or fault response for the message before timing
    #: out the request.
    REQUEST_TIMEOUT_HEADER = "DSRequestTimeout"

    SMALL_ATTRIBUTE_FLAGS = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40]
    SMALL_ATTRIBUTES = dict(zip(
        SMALL_ATTRIBUTE_FLAGS,
        __amf__.static
    ))

    SMALL_UUID_FLAGS = [0x01, 0x02]
    SMALL_UUIDS = dict(zip(
        SMALL_UUID_FLAGS,
        ['clientId', 'messageId']
    ))

    def __new__(cls, *args, **kwargs):
        obj = object.__new__(cls)

        obj.__init__(*args, **kwargs)

        return obj

    def __init__(self, *args, **kwargs):
        self.body = kwargs.get('body', None)
        self.clientId = kwargs.get('clientId', None)
        self.destination = kwargs.get('destination', None)
        self.headers = kwargs.get('headers', {})
        self.messageId = kwargs.get('messageId', None)
        self.timestamp = kwargs.get('timestamp', None)
        self.timeToLive = kwargs.get('timeToLive', None)

    def __repr__(self):
        m = '<%s ' % self.__class__.__name__

        for k in self.__dict__:
            m += ' %s=%r' % (k, getattr(self, k))

        return m + " />"

    def decodeSmallAttribute(self, attr, input):
        """
        @since: 0.5
        """
        obj = input.readObject()

        if attr in ['timestamp', 'timeToLive']:
            return pyamf.util.get_datetime(obj / 1000.0)

        return obj

    def encodeSmallAttribute(self, attr):
        """
        @since: 0.5
        """
        obj = getattr(self, attr)

        if not obj:
            return obj

        if attr in ['timestamp', 'timeToLive']:
            return pyamf.util.get_timestamp(obj) * 1000.0
        elif attr in ['clientId', 'messageId']:
            if isinstance(obj, uuid.UUID):
                return None

        return obj

    def __readamf__(self, input):
        flags = read_flags(input)

        if len(flags) > 2:
            raise pyamf.DecodeError('Expected <=2 (got %d) flags for the '
                'AbstractMessage portion of the small message for %r' % (
                    len(flags), self.__class__))

        for index, byte in enumerate(flags):
            if index == 0:
                for flag in self.SMALL_ATTRIBUTE_FLAGS:
                    if flag & byte:
                        attr = self.SMALL_ATTRIBUTES[flag]
                        setattr(self, attr, self.decodeSmallAttribute(attr, input))
            elif index == 1:
                for flag in self.SMALL_UUID_FLAGS:
                    if flag & byte:
                        attr = self.SMALL_UUIDS[flag]
                        setattr(self, attr, decode_uuid(input.readObject()))

    def __writeamf__(self, output):
        flag_attrs = []
        uuid_attrs = []
        byte = 0

        for flag in self.SMALL_ATTRIBUTE_FLAGS:
            value = self.encodeSmallAttribute(self.SMALL_ATTRIBUTES[flag])

            if value:
                byte |= flag
                flag_attrs.append(value)

        flags = byte
        byte = 0

        for flag in self.SMALL_UUID_FLAGS:
            attr = self.SMALL_UUIDS[flag]
            value = getattr(self, attr)

            if not value:
                continue

            byte |= flag
            uuid_attrs.append(amf3.ByteArray(value.bytes))

        if not byte:
            output.writeUnsignedByte(flags)
        else:
            output.writeUnsignedByte(flags | SMALL_FLAG_MORE)
            output.writeUnsignedByte(byte)

        [output.writeObject(attr) for attr in flag_attrs]
        [output.writeObject(attr) for attr in uuid_attrs]

    def getSmallMessage(self):
        """
        Return a ISmallMessage representation of this object. If one is not
        available, L{NotImplementedError} will be raised.

        @since: 0.5
        """
        raise NotImplementedError


class AsyncMessage(AbstractMessage):
    """
    I am the base class for all asynchronous Flex messages.

    @see: U{AsyncMessage on Livedocs<http://
        livedocs.adobe.com/flex/201/langref/mx/messaging/messages/AsyncMessage.html>}

    @ivar correlationId: Correlation id of the message.
    @type correlationId: C{str}
    """

    #: Messages that were sent with a defined subtopic property indicate their
    #: target subtopic in this header.
    SUBTOPIC_HEADER = "DSSubtopic"

    class __amf__:
        static = ('correlationId',)

    def __init__(self, *args, **kwargs):
        AbstractMessage.__init__(self, *args, **kwargs)

        self.correlationId = kwargs.get('correlationId', None)

    def __readamf__(self, input):
        AbstractMessage.__readamf__(self, input)

        flags = read_flags(input)

        if len(flags) > 1:
            raise pyamf.DecodeError('Expected <=1 (got %d) flags for the '
                'AsyncMessage portion of the small message for %r' % (
                    len(flags), self.__class__))

        byte = flags[0]

        if byte & 0x01:
            self.correlationId = input.readObject()

        if byte & 0x02:
            self.correlationId = decode_uuid(input.readObject())

    def __writeamf__(self, output):
        AbstractMessage.__writeamf__(self, output)

        if not isinstance(self.correlationId, uuid.UUID):
            output.writeUnsignedByte(0x01)
            output.writeObject(self.correlationId)
        else:
            output.writeUnsignedByte(0x02)
            output.writeObject(pyamf.amf3.ByteArray(self.correlationId.bytes))

    def getSmallMessage(self):
        """
        Return a ISmallMessage representation of this async message.

        @since: 0.5
        """
        return AsyncMessageExt(**self.__dict__)


class AcknowledgeMessage(AsyncMessage):
    """
    I acknowledge the receipt of a message that was sent previously.

    Every message sent within the messaging system must receive an
    acknowledgement.

    @see: U{AcknowledgeMessage on Livedocs<http://
        livedocs.adobe.com/flex/201/langref/mx/messaging/messages/AcknowledgeMessage.html>}
    """

    #: Used to indicate that the acknowledgement is for a message that
    #: generated an error.
    ERROR_HINT_HEADER = "DSErrorHint"

    def __readamf__(self, input):
        AsyncMessage.__readamf__(self, input)

        flags = read_flags(input)

        if len(flags) > 1:
            raise pyamf.DecodeError('Expected <=1 (got %d) flags for the '
                'AcknowledgeMessage portion of the small message for %r' % (
                    len(flags), self.__class__))

    def __writeamf__(self, output):
        AsyncMessage.__writeamf__(self, output)

        output.writeUnsignedByte(0)

    def getSmallMessage(self):
        """
        Return a ISmallMessage representation of this acknowledge message.

        @since: 0.5
        """
        return AcknowledgeMessageExt(**self.__dict__)


class CommandMessage(AsyncMessage):
    """
    Provides a mechanism for sending commands related to publish/subscribe
    messaging, ping, and cluster operations.

    @see: U{CommandMessage on Livedocs<http://
        livedocs.adobe.com/flex/201/langref/mx/messaging/messages/CommandMessage.html>}

    @ivar operation: The command
    @type operation: C{int}
    @ivar messageRefType: hmm, not sure about this one.
    @type messageRefType: C{str}
    """

    #: The server message type for authentication commands.
    AUTHENTICATION_MESSAGE_REF_TYPE = "flex.messaging.messages.AuthenticationMessage"
    #: This is used to test connectivity over the current channel to the remote
    #: endpoint.
    PING_OPERATION = 5
    #: This is used by a remote destination to sync missed or cached messages
    #: back to a client as a result of a client issued poll command.
    SYNC_OPERATION = 4
    #: This is used to request a list of failover endpoint URIs for the remote
    #: destination based on cluster membership.
    CLUSTER_REQUEST_OPERATION = 7
    #: This is used to send credentials to the endpoint so that the user can be
    #: logged in over the current channel. The credentials need to be C{Base64}
    #: encoded and stored in the body of the message.
    LOGIN_OPERATION = 8
    #: This is used to log the user out of the current channel, and will
    #: invalidate the server session if the channel is HTTP based.
    LOGOUT_OPERATION = 9
    #: This is used to poll a remote destination for pending, undelivered
    #: messages.
    POLL_OPERATION = 2
    #: Subscribe commands issued by a consumer pass the consumer's C{selector}
    #: expression in this header.
    SELECTOR_HEADER = "DSSelector"
    #: This is used to indicate that the client's session with a remote
    #: destination has timed out.
    SESSION_INVALIDATE_OPERATION = 10
    #: This is used to subscribe to a remote destination.
    SUBSCRIBE_OPERATION = 0
    #: This is the default operation for new L{CommandMessage} instances.
    UNKNOWN_OPERATION = 1000
    #: This is used to unsubscribe from a remote destination.
    UNSUBSCRIBE_OPERATION = 1
    #: This operation is used to indicate that a channel has disconnected.
    DISCONNECT_OPERATION = 12

    class __amf__:
        static = ('operation',)

    def __init__(self, *args, **kwargs):
        AsyncMessage.__init__(self, *args, **kwargs)

        self.operation = kwargs.get('operation', None)

    def __readamf__(self, input):
        AsyncMessage.__readamf__(self, input)

        flags = read_flags(input)

        if not flags:
            return

        if len(flags) > 1:
            raise pyamf.DecodeError('Expected <=1 (got %d) flags for the '
                'CommandMessage portion of the small message for %r' % (
                    len(flags), self.__class__))

        byte = flags[0]

        if byte & 0x01:
            self.operation = input.readObject()

    def __writeamf__(self, output):
        AsyncMessage.__writeamf__(self, output)

        if self.operation:
            output.writeUnsignedByte(0x01)
            output.writeObject(self.operation)
        else:
            output.writeUnsignedByte(0)

    def getSmallMessage(self):
        """
        Return a ISmallMessage representation of this command message.

        @since: 0.5
        """
        return CommandMessageExt(**self.__dict__)


class ErrorMessage(AcknowledgeMessage):
    """
    I am the Flex error message to be returned to the client.

    This class is used to report errors within the messaging system.

    @see: U{ErrorMessage on Livedocs<http://
        livedocs.adobe.com/flex/201/langref/mx/messaging/messages/ErrorMessage.html>}
    """

    #: If a message may not have been delivered, the faultCode will contain
    #: this constant.
    MESSAGE_DELIVERY_IN_DOUBT = "Client.Error.DeliveryInDoubt"
    #: Header name for the retryable hint header.
    #:
    #: This is used to indicate that the operation that generated the error may
    #: be retryable rather than fatal.
    RETRYABLE_HINT_HEADER = "DSRetryableErrorHint"

    class __amf__:
        static = ('extendedData', 'faultCode', 'faultDetail', 'faultString',
            'rootCause')

    def __init__(self, *args, **kwargs):
        AcknowledgeMessage.__init__(self, *args, **kwargs)
        #: Extended data that the remote destination has chosen to associate
        #: with this error to facilitate custom error processing on the client.
        self.extendedData = kwargs.get('extendedData', {})
        #: Fault code for the error.
        self.faultCode = kwargs.get('faultCode', None)
        #: Detailed description of what caused the error.
        self.faultDetail = kwargs.get('faultDetail', None)
        #: A simple description of the error.
        self.faultString = kwargs.get('faultString', None)
        #: Should a traceback exist for the error, this property contains the
        #: message.
        self.rootCause = kwargs.get('rootCause', {})

    def getSmallMessage(self):
        """
        Return a ISmallMessage representation of this error message.

        @since: 0.5
        """
        raise NotImplementedError


class RemotingMessage(AbstractMessage):
    """
    I am used to send RPC requests to a remote endpoint.

    @see: U{RemotingMessage on Livedocs<http://
        livedocs.adobe.com/flex/201/langref/mx/messaging/messages/RemotingMessage.html>}
    """

    class __amf__:
        static = ('operation', 'source')

    def __init__(self, *args, **kwargs):
        AbstractMessage.__init__(self, *args, **kwargs)
        #: Name of the remote method/operation that should be called.
        self.operation = kwargs.get('operation', None)
        #: Name of the service to be called including package name.
        #: This property is provided for backwards compatibility.
        self.source = kwargs.get('source', None)


class AcknowledgeMessageExt(AcknowledgeMessage):
    """
    An L{AcknowledgeMessage}, but implementing C{ISmallMessage}.

    @since: 0.5
    """

    class __amf__:
        external = True


class CommandMessageExt(CommandMessage):
    """
    A L{CommandMessage}, but implementing C{ISmallMessage}.

    @since: 0.5
    """

    class __amf__:
        external = True


class AsyncMessageExt(AsyncMessage):
    """
    A L{AsyncMessage}, but implementing C{ISmallMessage}.

    @since: 0.5
    """

    class __amf__:
        external = True


def read_flags(input):
    """
    @since: 0.5
    """
    flags = []

    done = False

    while not done:
        byte = input.readUnsignedByte()

        if not byte & SMALL_FLAG_MORE:
            done = True
        else:
            byte = byte ^ SMALL_FLAG_MORE

        flags.append(byte)

    return flags


def decode_uuid(obj):
    """
    Decode a L{ByteArray} contents to a C{uuid.UUID} instance.

    @since: 0.5
    """
    return uuid.UUID(bytes=str(obj))


pyamf.register_package(globals(), package=NAMESPACE)
pyamf.register_class(AcknowledgeMessageExt, 'DSK')
pyamf.register_class(CommandMessageExt, 'DSC')
pyamf.register_class(AsyncMessageExt, 'DSA')
