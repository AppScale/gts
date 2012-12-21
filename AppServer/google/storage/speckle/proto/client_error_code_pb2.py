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



from google.net.proto2.python.public import descriptor as _descriptor
from google.net.proto2.python.public import message as _message
from google.net.proto2.python.public import reflection as _reflection
from google.net.proto2.proto import descriptor_pb2





DESCRIPTOR = _descriptor.FileDescriptor(
  name='storage/speckle/proto/client_error_code.proto',
  package='speckle.sql',
  serialized_pb='\n-storage/speckle/proto/client_error_code.proto\x12\x0bspeckle.sql\"\x91\x07\n\x15SqlServiceClientError\"\xf7\x06\n\x0f\x43lientErrorCode\x12\x06\n\x02OK\x10\x00\x12\x13\n\x0fTRANSIENT_ERROR\x10\x01\x12\x12\n\x0eINTERNAL_ERROR\x10\x02\x12\x13\n\x0fINVALID_REQUEST\x10\x03\x12\x16\n\x12\x44\x45PRECATED_TIMEOUT\x10\x04\x12\x1d\n\x19\x44\x45PRECATED_NOT_AUTHORIZED\x10\x05\x12\x1a\n\x16\x44\x45PRECATED_RDBMS_ERROR\x10\x06\x12\"\n\x1d\x45RROR_PUBLIC_ERROR_CODE_START\x10\xe8\x07\x12\x10\n\x0b\x45RROR_RDBMS\x10\xe9\x07\x12\x12\n\rERROR_TIMEOUT\x10\xea\x07\x12\x19\n\x14\x45RROR_NOT_AUTHORIZED\x10\xeb\x07\x12\x1d\n\x18\x45RROR_INSTANCE_SUSPENDED\x10\xec\x07\x12\x1c\n\x17\x45RROR_INVALID_PARAMETER\x10\xed\x07\x12\"\n\x1d\x45RROR_NOT_ALL_VARIABLES_BOUND\x10\xee\x07\x12\x1d\n\x18\x45RROR_UNKNOWN_CONNECTION\x10\xef\x07\x12\x1c\n\x17\x45RROR_UNKNOWN_STATEMENT\x10\xf0\x07\x12\x1a\n\x15\x45RROR_UNKNOWN_CATALOG\x10\xf1\x07\x12\x19\n\x14\x45RROR_UNKNOWN_CURSOR\x10\xf2\x07\x12\x1b\n\x16\x45RROR_CURSOR_EXHAUSTED\x10\xfc\x07\x12\x1e\n\x19\x45RROR_NOT_YET_IMPLEMENTED\x10\x86\x08\x12\x1a\n\x15\x45RROR_NOT_IMPLEMENTED\x10\x87\x08\x12\x1f\n\x1a\x45RROR_INSTANCE_MAINTENANCE\x10\x88\x08\x12\'\n\"ERROR_TOO_MANY_CONCURRENT_REQUESTS\x10\x89\x08\x12\"\n\x1d\x45RROR_RESOURCE_DOES_NOT_EXIST\x10\x8a\x08\x12\"\n\x1d\x45RROR_RESOURCE_ALREADY_EXISTS\x10\x8b\x08\x12\x1c\n\x17\x45RROR_CONNECTION_IN_USE\x10\x8c\x08\x12!\n\x1c\x45RROR_CLIENT_VERSION_TOO_OLD\x10\x8d\x08\x12\x1b\n\x16\x45RROR_RESPONSE_PENDING\x10\x8e\x08\x12(\n#ERROR_INSTANCE_SUSPENDED_BY_BILLING\x10\x8f\x08\x12\x1e\n\x19\x45RROR_RESULTSET_TOO_LARGE\x10\x90\x08\x42%\n\x1b\x63om.google.protos.cloud.sql\x10\x02 \x02(\x02P\x01')



_SQLSERVICECLIENTERROR_CLIENTERRORCODE = _descriptor.EnumDescriptor(
  name='ClientErrorCode',
  full_name='speckle.sql.SqlServiceClientError.ClientErrorCode',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='OK', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TRANSIENT_ERROR', index=1, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='INTERNAL_ERROR', index=2, number=2,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='INVALID_REQUEST', index=3, number=3,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='DEPRECATED_TIMEOUT', index=4, number=4,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='DEPRECATED_NOT_AUTHORIZED', index=5, number=5,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='DEPRECATED_RDBMS_ERROR', index=6, number=6,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_PUBLIC_ERROR_CODE_START', index=7, number=1000,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_RDBMS', index=8, number=1001,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_TIMEOUT', index=9, number=1002,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_NOT_AUTHORIZED', index=10, number=1003,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_INSTANCE_SUSPENDED', index=11, number=1004,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_INVALID_PARAMETER', index=12, number=1005,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_NOT_ALL_VARIABLES_BOUND', index=13, number=1006,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_UNKNOWN_CONNECTION', index=14, number=1007,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_UNKNOWN_STATEMENT', index=15, number=1008,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_UNKNOWN_CATALOG', index=16, number=1009,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_UNKNOWN_CURSOR', index=17, number=1010,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_CURSOR_EXHAUSTED', index=18, number=1020,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_NOT_YET_IMPLEMENTED', index=19, number=1030,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_NOT_IMPLEMENTED', index=20, number=1031,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_INSTANCE_MAINTENANCE', index=21, number=1032,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_TOO_MANY_CONCURRENT_REQUESTS', index=22, number=1033,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_RESOURCE_DOES_NOT_EXIST', index=23, number=1034,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_RESOURCE_ALREADY_EXISTS', index=24, number=1035,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_CONNECTION_IN_USE', index=25, number=1036,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_CLIENT_VERSION_TOO_OLD', index=26, number=1037,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_RESPONSE_PENDING', index=27, number=1038,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_INSTANCE_SUSPENDED_BY_BILLING', index=28, number=1039,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ERROR_RESULTSET_TOO_LARGE', index=29, number=1040,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=89,
  serialized_end=976,
)


_SQLSERVICECLIENTERROR = _descriptor.Descriptor(
  name='SqlServiceClientError',
  full_name='speckle.sql.SqlServiceClientError',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
    _SQLSERVICECLIENTERROR_CLIENTERRORCODE,
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=63,
  serialized_end=976,
)

_SQLSERVICECLIENTERROR_CLIENTERRORCODE.containing_type = _SQLSERVICECLIENTERROR;
DESCRIPTOR.message_types_by_name['SqlServiceClientError'] = _SQLSERVICECLIENTERROR

class SqlServiceClientError(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _SQLSERVICECLIENTERROR




DESCRIPTOR.has_options = True
DESCRIPTOR._options = _descriptor._ParseOptions(descriptor_pb2.FileOptions(), '\n\033com.google.protos.cloud.sql\020\002 \002(\002P\001')

