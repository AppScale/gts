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


from google.net.proto2.python.public import descriptor
from google.net.proto2.python.public import message
from google.net.proto2.python.public import reflection
from google.net.proto2.proto import descriptor_pb2
import sys
try:
  __import__('google.net.rpc.python.rpc_internals')
  __import__('google.net.rpc.python.pywraprpc')
  rpc_internals = sys.modules.get('google.net.rpc.python.rpc_internals')
  pywraprpc = sys.modules.get('google.net.rpc.python.pywraprpc')
  _client_stub_base_class = rpc_internals.StubbyRPCBaseStub
except ImportError:
  _client_stub_base_class = object
try:
  __import__('google.net.rpc.python.rpcserver')
  rpcserver = sys.modules.get('google.net.rpc.python.rpcserver')
  _server_stub_base_class = rpcserver.BaseRpcServer
except ImportError:
  _server_stub_base_class = object



import google.storage.speckle.proto.client_pb2


DESCRIPTOR = descriptor.FileDescriptor(
  name='storage/speckle/proto/sql.proto',
  package='speckle.sql',
  serialized_pb='\n\x1fstorage/speckle/proto/sql.proto\x12\x0bspeckle.sql\x1a\"storage/speckle/proto/client.proto\"\xb9\x01\n\x0b\x45xecRequest\x12\x10\n\x08instance\x18\x01 \x02(\t\x12\x14\n\x0cstatement_id\x18\x02 \x01(\x04\x12\x11\n\tstatement\x18\x03 \x01(\t\x12\x31\n\rbind_variable\x18\x04 \x03(\x0b\x32\x1a.speckle.BindVariableProto\x12\x15\n\rconnection_id\x18\x05 \x02(\x0c\x12%\n\x07options\x18\x06 \x01(\x0b\x32\x14.speckle.ExecOptions\"4\n\x0c\x45xecResponse\x12$\n\x06result\x18\x01 \x01(\x0b\x32\x14.speckle.ResultProto\"V\n\rExecOpRequest\x12\x10\n\x08instance\x18\x01 \x02(\t\x12\x15\n\rconnection_id\x18\x02 \x02(\x0c\x12\x1c\n\x02op\x18\x03 \x02(\x0b\x32\x10.speckle.OpProto\"\x9f\x01\n\x0e\x45xecOpResponse\x12\x12\n\nnative_sql\x18\x01 \x01(\t\x12%\n\tsavepoint\x18\x02 \x01(\x0b\x32\x12.speckle.SavePoint\x12,\n\rsql_exception\x18\x03 \x01(\x0b\x32\x15.speckle.SqlException\x12$\n\x06result\x18\x04 \x01(\x0b\x32\x14.speckle.ResultProto\"\x96\x01\n\x0fMetadataRequest\x12\x10\n\x08instance\x18\x01 \x02(\t\x12\'\n\x08metadata\x18\x03 \x02(\x0e\x32\x15.speckle.MetadataType\x12\x31\n\rbind_variable\x18\x04 \x03(\x0b\x32\x1a.speckle.BindVariableProto\x12\x15\n\rconnection_id\x18\x05 \x02(\x0c\"|\n\x10MetadataResponse\x12$\n\x06result\x18\x01 \x01(\x0b\x32\x14.speckle.ResultProto\x12\x42\n\x16jdbc_database_metadata\x18\x02 \x01(\x0b\x32\".speckle.JdbcDatabaseMetaDataProto\"N\n\x15OpenConnectionRequest\x12\x10\n\x08instance\x18\x01 \x02(\t\x12#\n\x08property\x18\x02 \x03(\x0b\x32\x11.speckle.Property\"]\n\x16OpenConnectionResponse\x12\x15\n\rconnection_id\x18\x01 \x01(\x0c\x12,\n\rsql_exception\x18\x02 \x01(\x0b\x32\x15.speckle.SqlException\"A\n\x16\x43loseConnectionRequest\x12\x10\n\x08instance\x18\x01 \x02(\t\x12\x15\n\rconnection_id\x18\x02 \x02(\x0c\"G\n\x17\x43loseConnectionResponse\x12,\n\rsql_exception\x18\x01 \x01(\x0b\x32\x15.speckle.SqlException2\xa5\x03\n\nSqlService\x12?\n\x04\x45xec\x12\x18.speckle.sql.ExecRequest\x1a\x19.speckle.sql.ExecResponse\"\x02P\x01\x12\x45\n\x06\x45xecOp\x12\x1a.speckle.sql.ExecOpRequest\x1a\x1b.speckle.sql.ExecOpResponse\"\x02P\x01\x12N\n\x0bGetMetadata\x12\x1c.speckle.sql.MetadataRequest\x1a\x1d.speckle.sql.MetadataResponse\"\x02P\x01\x12]\n\x0eOpenConnection\x12\".speckle.sql.OpenConnectionRequest\x1a#.speckle.sql.OpenConnectionResponse\"\x02P\x01\x12`\n\x0f\x43loseConnection\x12#.speckle.sql.CloseConnectionRequest\x1a$.speckle.sql.CloseConnectionResponse\"\x02P\x01\x42\x13\x10\x02 \x02(\x02P\x01xd\x80\x01\x00\x88\x01\x00\x90\x01\x00')




_EXECREQUEST = descriptor.Descriptor(
  name='ExecRequest',
  full_name='speckle.sql.ExecRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='instance', full_name='speckle.sql.ExecRequest.instance', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='statement_id', full_name='speckle.sql.ExecRequest.statement_id', index=1,
      number=2, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='statement', full_name='speckle.sql.ExecRequest.statement', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='bind_variable', full_name='speckle.sql.ExecRequest.bind_variable', index=3,
      number=4, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='connection_id', full_name='speckle.sql.ExecRequest.connection_id', index=4,
      number=5, type=12, cpp_type=9, label=2,
      has_default_value=False, default_value="",
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='options', full_name='speckle.sql.ExecRequest.options', index=5,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=85,
  serialized_end=270,
)


_EXECRESPONSE = descriptor.Descriptor(
  name='ExecResponse',
  full_name='speckle.sql.ExecResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='result', full_name='speckle.sql.ExecResponse.result', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=272,
  serialized_end=324,
)


_EXECOPREQUEST = descriptor.Descriptor(
  name='ExecOpRequest',
  full_name='speckle.sql.ExecOpRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='instance', full_name='speckle.sql.ExecOpRequest.instance', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='connection_id', full_name='speckle.sql.ExecOpRequest.connection_id', index=1,
      number=2, type=12, cpp_type=9, label=2,
      has_default_value=False, default_value="",
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='op', full_name='speckle.sql.ExecOpRequest.op', index=2,
      number=3, type=11, cpp_type=10, label=2,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=326,
  serialized_end=412,
)


_EXECOPRESPONSE = descriptor.Descriptor(
  name='ExecOpResponse',
  full_name='speckle.sql.ExecOpResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='native_sql', full_name='speckle.sql.ExecOpResponse.native_sql', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='savepoint', full_name='speckle.sql.ExecOpResponse.savepoint', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='sql_exception', full_name='speckle.sql.ExecOpResponse.sql_exception', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='result', full_name='speckle.sql.ExecOpResponse.result', index=3,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=415,
  serialized_end=574,
)


_METADATAREQUEST = descriptor.Descriptor(
  name='MetadataRequest',
  full_name='speckle.sql.MetadataRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='instance', full_name='speckle.sql.MetadataRequest.instance', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='metadata', full_name='speckle.sql.MetadataRequest.metadata', index=1,
      number=3, type=14, cpp_type=8, label=2,
      has_default_value=False, default_value=1,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='bind_variable', full_name='speckle.sql.MetadataRequest.bind_variable', index=2,
      number=4, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='connection_id', full_name='speckle.sql.MetadataRequest.connection_id', index=3,
      number=5, type=12, cpp_type=9, label=2,
      has_default_value=False, default_value="",
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=577,
  serialized_end=727,
)


_METADATARESPONSE = descriptor.Descriptor(
  name='MetadataResponse',
  full_name='speckle.sql.MetadataResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='result', full_name='speckle.sql.MetadataResponse.result', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='jdbc_database_metadata', full_name='speckle.sql.MetadataResponse.jdbc_database_metadata', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=729,
  serialized_end=853,
)


_OPENCONNECTIONREQUEST = descriptor.Descriptor(
  name='OpenConnectionRequest',
  full_name='speckle.sql.OpenConnectionRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='instance', full_name='speckle.sql.OpenConnectionRequest.instance', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='property', full_name='speckle.sql.OpenConnectionRequest.property', index=1,
      number=2, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=855,
  serialized_end=933,
)


_OPENCONNECTIONRESPONSE = descriptor.Descriptor(
  name='OpenConnectionResponse',
  full_name='speckle.sql.OpenConnectionResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='connection_id', full_name='speckle.sql.OpenConnectionResponse.connection_id', index=0,
      number=1, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value="",
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='sql_exception', full_name='speckle.sql.OpenConnectionResponse.sql_exception', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=935,
  serialized_end=1028,
)


_CLOSECONNECTIONREQUEST = descriptor.Descriptor(
  name='CloseConnectionRequest',
  full_name='speckle.sql.CloseConnectionRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='instance', full_name='speckle.sql.CloseConnectionRequest.instance', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='connection_id', full_name='speckle.sql.CloseConnectionRequest.connection_id', index=1,
      number=2, type=12, cpp_type=9, label=2,
      has_default_value=False, default_value="",
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=1030,
  serialized_end=1095,
)


_CLOSECONNECTIONRESPONSE = descriptor.Descriptor(
  name='CloseConnectionResponse',
  full_name='speckle.sql.CloseConnectionResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='sql_exception', full_name='speckle.sql.CloseConnectionResponse.sql_exception', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=1097,
  serialized_end=1168,
)

_EXECREQUEST.fields_by_name['bind_variable'].message_type = google.storage.speckle.proto.client_pb2._BINDVARIABLEPROTO
_EXECREQUEST.fields_by_name['options'].message_type = google.storage.speckle.proto.client_pb2._EXECOPTIONS
_EXECRESPONSE.fields_by_name['result'].message_type = google.storage.speckle.proto.client_pb2._RESULTPROTO
_EXECOPREQUEST.fields_by_name['op'].message_type = google.storage.speckle.proto.client_pb2._OPPROTO
_EXECOPRESPONSE.fields_by_name['savepoint'].message_type = google.storage.speckle.proto.client_pb2._SAVEPOINT
_EXECOPRESPONSE.fields_by_name['sql_exception'].message_type = google.storage.speckle.proto.client_pb2._SQLEXCEPTION
_EXECOPRESPONSE.fields_by_name['result'].message_type = google.storage.speckle.proto.client_pb2._RESULTPROTO
_METADATAREQUEST.fields_by_name['metadata'].enum_type = google.storage.speckle.proto.client_pb2._METADATATYPE
_METADATAREQUEST.fields_by_name['bind_variable'].message_type = google.storage.speckle.proto.client_pb2._BINDVARIABLEPROTO
_METADATARESPONSE.fields_by_name['result'].message_type = google.storage.speckle.proto.client_pb2._RESULTPROTO
_METADATARESPONSE.fields_by_name['jdbc_database_metadata'].message_type = google.storage.speckle.proto.client_pb2._JDBCDATABASEMETADATAPROTO
_OPENCONNECTIONREQUEST.fields_by_name['property'].message_type = google.storage.speckle.proto.client_pb2._PROPERTY
_OPENCONNECTIONRESPONSE.fields_by_name['sql_exception'].message_type = google.storage.speckle.proto.client_pb2._SQLEXCEPTION
_CLOSECONNECTIONRESPONSE.fields_by_name['sql_exception'].message_type = google.storage.speckle.proto.client_pb2._SQLEXCEPTION
DESCRIPTOR.message_types_by_name['ExecRequest'] = _EXECREQUEST
DESCRIPTOR.message_types_by_name['ExecResponse'] = _EXECRESPONSE
DESCRIPTOR.message_types_by_name['ExecOpRequest'] = _EXECOPREQUEST
DESCRIPTOR.message_types_by_name['ExecOpResponse'] = _EXECOPRESPONSE
DESCRIPTOR.message_types_by_name['MetadataRequest'] = _METADATAREQUEST
DESCRIPTOR.message_types_by_name['MetadataResponse'] = _METADATARESPONSE
DESCRIPTOR.message_types_by_name['OpenConnectionRequest'] = _OPENCONNECTIONREQUEST
DESCRIPTOR.message_types_by_name['OpenConnectionResponse'] = _OPENCONNECTIONRESPONSE
DESCRIPTOR.message_types_by_name['CloseConnectionRequest'] = _CLOSECONNECTIONREQUEST
DESCRIPTOR.message_types_by_name['CloseConnectionResponse'] = _CLOSECONNECTIONRESPONSE

class ExecRequest(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _EXECREQUEST



class ExecResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _EXECRESPONSE



class ExecOpRequest(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _EXECOPREQUEST



class ExecOpResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _EXECOPRESPONSE



class MetadataRequest(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _METADATAREQUEST



class MetadataResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _METADATARESPONSE



class OpenConnectionRequest(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _OPENCONNECTIONREQUEST



class OpenConnectionResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _OPENCONNECTIONRESPONSE



class CloseConnectionRequest(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CLOSECONNECTIONREQUEST



class CloseConnectionResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CLOSECONNECTIONRESPONSE





class _SqlService_ClientBaseStub(_client_stub_base_class):
  """Makes Stubby RPC calls to a SqlService server."""

  __slots__ = (
      '_protorpc_Exec', '_full_name_Exec',
      '_protorpc_ExecOp', '_full_name_ExecOp',
      '_protorpc_GetMetadata', '_full_name_GetMetadata',
      '_protorpc_OpenConnection', '_full_name_OpenConnection',
      '_protorpc_CloseConnection', '_full_name_CloseConnection',
  )

  def __init__(self, rpc_stub):
    self._stub = rpc_stub

    self._protorpc_Exec = pywraprpc.RPC()
    self._protorpc_Exec.set_fail_fast(True)
    self._full_name_Exec = self._stub.GetFullMethodName(
        'Exec')

    self._protorpc_ExecOp = pywraprpc.RPC()
    self._protorpc_ExecOp.set_fail_fast(True)
    self._full_name_ExecOp = self._stub.GetFullMethodName(
        'ExecOp')

    self._protorpc_GetMetadata = pywraprpc.RPC()
    self._protorpc_GetMetadata.set_fail_fast(True)
    self._full_name_GetMetadata = self._stub.GetFullMethodName(
        'GetMetadata')

    self._protorpc_OpenConnection = pywraprpc.RPC()
    self._protorpc_OpenConnection.set_fail_fast(True)
    self._full_name_OpenConnection = self._stub.GetFullMethodName(
        'OpenConnection')

    self._protorpc_CloseConnection = pywraprpc.RPC()
    self._protorpc_CloseConnection.set_fail_fast(True)
    self._full_name_CloseConnection = self._stub.GetFullMethodName(
        'CloseConnection')

  def Exec(self, request, rpc=None, callback=None, response=None):
    """Make a Exec RPC call.

    Args:
      request: a ExecRequest instance.
      rpc: Optional RPC instance to use for the call.
      callback: Optional final callback. Will be called as
          callback(rpc, result) when the rpc completes. If None, the
          call is synchronous.
      response: Optional ProtocolMessage to be filled in with response.

    Returns:
      The ExecResponse if callback is None. Otherwise, returns None.
    """

    if response is None:
      response = ExecResponse
    return self._MakeCall(rpc,
                          self._full_name_Exec,
                          'Exec',
                          request,
                          response,
                          callback,
                          self._protorpc_Exec)

  def ExecOp(self, request, rpc=None, callback=None, response=None):
    """Make a ExecOp RPC call.

    Args:
      request: a ExecOpRequest instance.
      rpc: Optional RPC instance to use for the call.
      callback: Optional final callback. Will be called as
          callback(rpc, result) when the rpc completes. If None, the
          call is synchronous.
      response: Optional ProtocolMessage to be filled in with response.

    Returns:
      The ExecOpResponse if callback is None. Otherwise, returns None.
    """

    if response is None:
      response = ExecOpResponse
    return self._MakeCall(rpc,
                          self._full_name_ExecOp,
                          'ExecOp',
                          request,
                          response,
                          callback,
                          self._protorpc_ExecOp)

  def GetMetadata(self, request, rpc=None, callback=None, response=None):
    """Make a GetMetadata RPC call.

    Args:
      request: a MetadataRequest instance.
      rpc: Optional RPC instance to use for the call.
      callback: Optional final callback. Will be called as
          callback(rpc, result) when the rpc completes. If None, the
          call is synchronous.
      response: Optional ProtocolMessage to be filled in with response.

    Returns:
      The MetadataResponse if callback is None. Otherwise, returns None.
    """

    if response is None:
      response = MetadataResponse
    return self._MakeCall(rpc,
                          self._full_name_GetMetadata,
                          'GetMetadata',
                          request,
                          response,
                          callback,
                          self._protorpc_GetMetadata)

  def OpenConnection(self, request, rpc=None, callback=None, response=None):
    """Make a OpenConnection RPC call.

    Args:
      request: a OpenConnectionRequest instance.
      rpc: Optional RPC instance to use for the call.
      callback: Optional final callback. Will be called as
          callback(rpc, result) when the rpc completes. If None, the
          call is synchronous.
      response: Optional ProtocolMessage to be filled in with response.

    Returns:
      The OpenConnectionResponse if callback is None. Otherwise, returns None.
    """

    if response is None:
      response = OpenConnectionResponse
    return self._MakeCall(rpc,
                          self._full_name_OpenConnection,
                          'OpenConnection',
                          request,
                          response,
                          callback,
                          self._protorpc_OpenConnection)

  def CloseConnection(self, request, rpc=None, callback=None, response=None):
    """Make a CloseConnection RPC call.

    Args:
      request: a CloseConnectionRequest instance.
      rpc: Optional RPC instance to use for the call.
      callback: Optional final callback. Will be called as
          callback(rpc, result) when the rpc completes. If None, the
          call is synchronous.
      response: Optional ProtocolMessage to be filled in with response.

    Returns:
      The CloseConnectionResponse if callback is None. Otherwise, returns None.
    """

    if response is None:
      response = CloseConnectionResponse
    return self._MakeCall(rpc,
                          self._full_name_CloseConnection,
                          'CloseConnection',
                          request,
                          response,
                          callback,
                          self._protorpc_CloseConnection)


class _SqlService_ClientStub(_SqlService_ClientBaseStub):
  def __init__(self, rpc_stub_parameters, service_name):
    if service_name is None:
      service_name = 'SqlService'
    _SqlService_ClientBaseStub.__init__(self, pywraprpc.RPC_GenericStub(service_name, rpc_stub_parameters))
    self._params = rpc_stub_parameters


class _SqlService_RPC2ClientStub(_SqlService_ClientBaseStub):
  def __init__(self, server, channel, service_name):
    if service_name is None:
      service_name = 'SqlService'
    if channel is not None:
      if channel.version() == 1:
        raise RuntimeError('Expecting an RPC2 channel to create the stub')
      _SqlService_ClientBaseStub.__init__(self, pywraprpc.RPC_GenericStub(service_name, channel))
    elif server is not None:
      _SqlService_ClientBaseStub.__init__(self, pywraprpc.RPC_GenericStub(service_name, pywraprpc.NewClientChannel(server)))
    else:
      raise RuntimeError('Invalid argument combination to create a stub')


class SqlService(_server_stub_base_class):
  """Base class for SqlService Stubby servers."""

  def __init__(self, *args, **kwargs):
    """Creates a Stubby RPC server.

    See BaseRpcServer.__init__ in rpcserver.py for detail on arguments.
    """
    if _server_stub_base_class is object:
      raise NotImplementedError('Add //net/rpc/python:rpcserver as a '
                                'dependency for Stubby server support.')
    _server_stub_base_class.__init__(self, 'speckle.sql.SqlService', *args, **kwargs)

  @staticmethod
  def NewStub(rpc_stub_parameters, service_name=None):
    """Creates a new SqlService Stubby client stub.

    Args:
      rpc_stub_parameters: an RPC_StubParameter instance.
      service_name: the service name used by the Stubby server.
    """

    if _client_stub_base_class is object:
      raise RuntimeError('Add //net/rpc/python as a dependency to use Stubby')
    return _SqlService_ClientStub(rpc_stub_parameters, service_name)

  @staticmethod
  def NewRPC2Stub(server=None, channel=None, service_name=None):
    """Creates a new SqlService Stubby2 client stub.

    Args:
      server: host:port or bns address.
      channel: directly use a channel to create a stub. Will ignore server
          argument if this is specified.
      service_name: the service name used by the Stubby server.
    """

    if _client_stub_base_class is object:
      raise RuntimeError('Add //net/rpc/python as a dependency to use Stubby')
    return _SqlService_RPC2ClientStub(server, channel, service_name)

  def Exec(self, rpc, request, response):
    """Handles a Exec RPC call. You should override this.

    Args:
      rpc: a Stubby RPC object
      request: a ExecRequest that contains the client request
      response: a ExecResponse that should be modified to send the response
    """
    raise NotImplementedError


  def ExecOp(self, rpc, request, response):
    """Handles a ExecOp RPC call. You should override this.

    Args:
      rpc: a Stubby RPC object
      request: a ExecOpRequest that contains the client request
      response: a ExecOpResponse that should be modified to send the response
    """
    raise NotImplementedError


  def GetMetadata(self, rpc, request, response):
    """Handles a GetMetadata RPC call. You should override this.

    Args:
      rpc: a Stubby RPC object
      request: a MetadataRequest that contains the client request
      response: a MetadataResponse that should be modified to send the response
    """
    raise NotImplementedError


  def OpenConnection(self, rpc, request, response):
    """Handles a OpenConnection RPC call. You should override this.

    Args:
      rpc: a Stubby RPC object
      request: a OpenConnectionRequest that contains the client request
      response: a OpenConnectionResponse that should be modified to send the response
    """
    raise NotImplementedError


  def CloseConnection(self, rpc, request, response):
    """Handles a CloseConnection RPC call. You should override this.

    Args:
      rpc: a Stubby RPC object
      request: a CloseConnectionRequest that contains the client request
      response: a CloseConnectionResponse that should be modified to send the response
    """
    raise NotImplementedError

  def _AddMethodAttributes(self):
    """Sets attributes on Python RPC handlers.

    See BaseRpcServer in rpcserver.py for details.
    """
    rpcserver._GetHandlerDecorator(
        self.Exec.im_func,
        ExecRequest,
        ExecResponse,
        None,
        'none')
    rpcserver._GetHandlerDecorator(
        self.ExecOp.im_func,
        ExecOpRequest,
        ExecOpResponse,
        None,
        'none')
    rpcserver._GetHandlerDecorator(
        self.GetMetadata.im_func,
        MetadataRequest,
        MetadataResponse,
        None,
        'none')
    rpcserver._GetHandlerDecorator(
        self.OpenConnection.im_func,
        OpenConnectionRequest,
        OpenConnectionResponse,
        None,
        'none')
    rpcserver._GetHandlerDecorator(
        self.CloseConnection.im_func,
        CloseConnectionRequest,
        CloseConnectionResponse,
        None,
        'none')


