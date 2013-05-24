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
  name='apphosting/ext/datastore_admin/backup.proto',
  package='apphosting.ext.datastore_admin',
  serialized_pb='\n+apphosting/ext/datastore_admin/backup.proto\x12\x1e\x61pphosting.ext.datastore_admin\"\x8c\x01\n\x06\x42\x61\x63kup\x12?\n\x0b\x62\x61\x63kup_info\x18\x01 \x01(\x0b\x32*.apphosting.ext.datastore_admin.BackupInfo\x12\x41\n\tkind_info\x18\x02 \x03(\x0b\x32..apphosting.ext.datastore_admin.KindBackupInfo\"Q\n\nBackupInfo\x12\x13\n\x0b\x62\x61\x63kup_name\x18\x01 \x01(\t\x12\x17\n\x0fstart_timestamp\x18\x02 \x01(\x03\x12\x15\n\rend_timestamp\x18\x03 \x01(\x03\"\x8c\x01\n\x0eKindBackupInfo\x12\x0c\n\x04kind\x18\x01 \x02(\t\x12\x0c\n\x04\x66ile\x18\x02 \x03(\t\x12\x43\n\rentity_schema\x18\x03 \x01(\x0b\x32,.apphosting.ext.datastore_admin.EntitySchema\x12\x19\n\nis_partial\x18\x04 \x01(\x08:\x05\x66\x61lse\"\xfc\x04\n\x0c\x45ntitySchema\x12\x0c\n\x04kind\x18\x01 \x01(\t\x12\x41\n\x05\x66ield\x18\x02 \x03(\x0b\x32\x32.apphosting.ext.datastore_admin.EntitySchema.Field\x1a\xb2\x01\n\x04Type\x12\x0f\n\x07is_list\x18\x01 \x01(\x08\x12R\n\x0eprimitive_type\x18\x02 \x03(\x0e\x32:.apphosting.ext.datastore_admin.EntitySchema.PrimitiveType\x12\x45\n\x0f\x65mbedded_schema\x18\x03 \x03(\x0b\x32,.apphosting.ext.datastore_admin.EntitySchema\x1aV\n\x05\x46ield\x12\x0c\n\x04name\x18\x01 \x02(\t\x12?\n\x04type\x18\x02 \x03(\x0b\x32\x31.apphosting.ext.datastore_admin.EntitySchema.Type\"\x8d\x02\n\rPrimitiveType\x12\t\n\x05\x46LOAT\x10\x00\x12\x0b\n\x07INTEGER\x10\x01\x12\x0b\n\x07\x42OOLEAN\x10\x02\x12\n\n\x06STRING\x10\x03\x12\r\n\tDATE_TIME\x10\x04\x12\n\n\x06RATING\x10\x05\x12\x08\n\x04LINK\x10\x06\x12\x0c\n\x08\x43\x41TEGORY\x10\x07\x12\x10\n\x0cPHONE_NUMBER\x10\x08\x12\x12\n\x0ePOSTAL_ADDRESS\x10\t\x12\t\n\x05\x45MAIL\x10\n\x12\r\n\tIM_HANDLE\x10\x0b\x12\x0c\n\x08\x42LOB_KEY\x10\x0c\x12\x08\n\x04TEXT\x10\r\x12\x08\n\x04\x42LOB\x10\x0e\x12\x0e\n\nSHORT_BLOB\x10\x0f\x12\x08\n\x04USER\x10\x10\x12\r\n\tGEO_POINT\x10\x11\x12\r\n\tREFERENCE\x10\x12\x42\x14\x10\x02 \x02(\x02\x42\x0c\x42\x61\x63kupProtos')



_ENTITYSCHEMA_PRIMITIVETYPE = _descriptor.EnumDescriptor(
  name='PrimitiveType',
  full_name='apphosting.ext.datastore_admin.EntitySchema.PrimitiveType',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='FLOAT', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='INTEGER', index=1, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='BOOLEAN', index=2, number=2,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='STRING', index=3, number=3,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='DATE_TIME', index=4, number=4,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='RATING', index=5, number=5,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='LINK', index=6, number=6,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CATEGORY', index=7, number=7,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='PHONE_NUMBER', index=8, number=8,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='POSTAL_ADDRESS', index=9, number=9,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='EMAIL', index=10, number=10,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='IM_HANDLE', index=11, number=11,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='BLOB_KEY', index=12, number=12,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TEXT', index=13, number=13,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='BLOB', index=14, number=14,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SHORT_BLOB', index=15, number=15,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='USER', index=16, number=16,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='GEO_POINT', index=17, number=17,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='REFERENCE', index=18, number=18,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=816,
  serialized_end=1085,
)


_BACKUP = _descriptor.Descriptor(
  name='Backup',
  full_name='apphosting.ext.datastore_admin.Backup',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='backup_info', full_name='apphosting.ext.datastore_admin.Backup.backup_info', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='kind_info', full_name='apphosting.ext.datastore_admin.Backup.kind_info', index=1,
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
  serialized_start=80,
  serialized_end=220,
)


_BACKUPINFO = _descriptor.Descriptor(
  name='BackupInfo',
  full_name='apphosting.ext.datastore_admin.BackupInfo',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='backup_name', full_name='apphosting.ext.datastore_admin.BackupInfo.backup_name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='start_timestamp', full_name='apphosting.ext.datastore_admin.BackupInfo.start_timestamp', index=1,
      number=2, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='end_timestamp', full_name='apphosting.ext.datastore_admin.BackupInfo.end_timestamp', index=2,
      number=3, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
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
  serialized_start=222,
  serialized_end=303,
)


_KINDBACKUPINFO = _descriptor.Descriptor(
  name='KindBackupInfo',
  full_name='apphosting.ext.datastore_admin.KindBackupInfo',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='kind', full_name='apphosting.ext.datastore_admin.KindBackupInfo.kind', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='file', full_name='apphosting.ext.datastore_admin.KindBackupInfo.file', index=1,
      number=2, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='entity_schema', full_name='apphosting.ext.datastore_admin.KindBackupInfo.entity_schema', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='is_partial', full_name='apphosting.ext.datastore_admin.KindBackupInfo.is_partial', index=3,
      number=4, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
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
  serialized_start=306,
  serialized_end=446,
)


_ENTITYSCHEMA_TYPE = _descriptor.Descriptor(
  name='Type',
  full_name='apphosting.ext.datastore_admin.EntitySchema.Type',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='is_list', full_name='apphosting.ext.datastore_admin.EntitySchema.Type.is_list', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='primitive_type', full_name='apphosting.ext.datastore_admin.EntitySchema.Type.primitive_type', index=1,
      number=2, type=14, cpp_type=8, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='embedded_schema', full_name='apphosting.ext.datastore_admin.EntitySchema.Type.embedded_schema', index=2,
      number=3, type=11, cpp_type=10, label=3,
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
  serialized_start=547,
  serialized_end=725,
)

_ENTITYSCHEMA_FIELD = _descriptor.Descriptor(
  name='Field',
  full_name='apphosting.ext.datastore_admin.EntitySchema.Field',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='apphosting.ext.datastore_admin.EntitySchema.Field.name', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='type', full_name='apphosting.ext.datastore_admin.EntitySchema.Field.type', index=1,
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
  serialized_start=727,
  serialized_end=813,
)

_ENTITYSCHEMA = _descriptor.Descriptor(
  name='EntitySchema',
  full_name='apphosting.ext.datastore_admin.EntitySchema',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='kind', full_name='apphosting.ext.datastore_admin.EntitySchema.kind', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='field', full_name='apphosting.ext.datastore_admin.EntitySchema.field', index=1,
      number=2, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_ENTITYSCHEMA_TYPE, _ENTITYSCHEMA_FIELD, ],
  enum_types=[
    _ENTITYSCHEMA_PRIMITIVETYPE,
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=449,
  serialized_end=1085,
)

_BACKUP.fields_by_name['backup_info'].message_type = _BACKUPINFO
_BACKUP.fields_by_name['kind_info'].message_type = _KINDBACKUPINFO
_KINDBACKUPINFO.fields_by_name['entity_schema'].message_type = _ENTITYSCHEMA
_ENTITYSCHEMA_TYPE.fields_by_name['primitive_type'].enum_type = _ENTITYSCHEMA_PRIMITIVETYPE
_ENTITYSCHEMA_TYPE.fields_by_name['embedded_schema'].message_type = _ENTITYSCHEMA
_ENTITYSCHEMA_TYPE.containing_type = _ENTITYSCHEMA;
_ENTITYSCHEMA_FIELD.fields_by_name['type'].message_type = _ENTITYSCHEMA_TYPE
_ENTITYSCHEMA_FIELD.containing_type = _ENTITYSCHEMA;
_ENTITYSCHEMA.fields_by_name['field'].message_type = _ENTITYSCHEMA_FIELD
_ENTITYSCHEMA_PRIMITIVETYPE.containing_type = _ENTITYSCHEMA;
DESCRIPTOR.message_types_by_name['Backup'] = _BACKUP
DESCRIPTOR.message_types_by_name['BackupInfo'] = _BACKUPINFO
DESCRIPTOR.message_types_by_name['KindBackupInfo'] = _KINDBACKUPINFO
DESCRIPTOR.message_types_by_name['EntitySchema'] = _ENTITYSCHEMA

class Backup(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _BACKUP



class BackupInfo(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _BACKUPINFO



class KindBackupInfo(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _KINDBACKUPINFO



class EntitySchema(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType

  class Type(_message.Message):
    __metaclass__ = _reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _ENTITYSCHEMA_TYPE



  class Field(_message.Message):
    __metaclass__ = _reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _ENTITYSCHEMA_FIELD


  DESCRIPTOR = _ENTITYSCHEMA




DESCRIPTOR.has_options = True
DESCRIPTOR._options = _descriptor._ParseOptions(descriptor_pb2.FileOptions(), '\020\002 \002(\002B\014BackupProtos')

