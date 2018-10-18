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





DESCRIPTOR = _descriptor.FileDescriptor(
  name='net/proto2/proto/descriptor.proto',
  package='proto2',
  serialized_pb='\n!net/proto2/proto/descriptor.proto\x12\x06proto2\">\n\x11\x46ileDescriptorSet\x12)\n\x04\x66ile\x18\x01 \x03(\x0b\x32\x1b.proto2.FileDescriptorProto\"\x95\x03\n\x13\x46ileDescriptorProto\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x0f\n\x07package\x18\x02 \x01(\t\x12\x12\n\ndependency\x18\x03 \x03(\t\x12\x19\n\x11public_dependency\x18\n \x03(\x05\x12\x17\n\x0fweak_dependency\x18\x0b \x03(\x05\x12-\n\x0cmessage_type\x18\x04 \x03(\x0b\x32\x17.proto2.DescriptorProto\x12.\n\tenum_type\x18\x05 \x03(\x0b\x32\x1b.proto2.EnumDescriptorProto\x12/\n\x07service\x18\x06 \x03(\x0b\x32\x1e.proto2.ServiceDescriptorProto\x12/\n\textension\x18\x07 \x03(\x0b\x32\x1c.proto2.FieldDescriptorProto\x12$\n\x07options\x18\x08 \x01(\x0b\x32\x13.proto2.FileOptions\x12\x30\n\x10source_code_info\x18\t \x01(\x0b\x32\x16.proto2.SourceCodeInfo\"\xa5\x03\n\x0f\x44\x65scriptorProto\x12\x0c\n\x04name\x18\x01 \x01(\t\x12+\n\x05\x66ield\x18\x02 \x03(\x0b\x32\x1c.proto2.FieldDescriptorProto\x12/\n\textension\x18\x06 \x03(\x0b\x32\x1c.proto2.FieldDescriptorProto\x12,\n\x0bnested_type\x18\x03 \x03(\x0b\x32\x17.proto2.DescriptorProto\x12.\n\tenum_type\x18\x04 \x03(\x0b\x32\x1b.proto2.EnumDescriptorProto\x12?\n\x0f\x65xtension_range\x18\x05 \x03(\x0b\x32&.proto2.DescriptorProto.ExtensionRange\x12\x30\n\noneof_decl\x18\x08 \x03(\x0b\x32\x1c.proto2.OneofDescriptorProto\x12\'\n\x07options\x18\x07 \x01(\x0b\x32\x16.proto2.MessageOptions\x1a,\n\x0e\x45xtensionRange\x12\r\n\x05start\x18\x01 \x01(\x05\x12\x0b\n\x03\x65nd\x18\x02 \x01(\x05\"\x8e\x05\n\x14\x46ieldDescriptorProto\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x0e\n\x06number\x18\x03 \x01(\x05\x12\x31\n\x05label\x18\x04 \x01(\x0e\x32\".proto2.FieldDescriptorProto.Label\x12/\n\x04type\x18\x05 \x01(\x0e\x32!.proto2.FieldDescriptorProto.Type\x12\x11\n\ttype_name\x18\x06 \x01(\t\x12\x10\n\x08\x65xtendee\x18\x02 \x01(\t\x12\x15\n\rdefault_value\x18\x07 \x01(\t\x12\x13\n\x0boneof_index\x18\t \x01(\x05\x12%\n\x07options\x18\x08 \x01(\x0b\x32\x14.proto2.FieldOptions\"\xb6\x02\n\x04Type\x12\x0f\n\x0bTYPE_DOUBLE\x10\x01\x12\x0e\n\nTYPE_FLOAT\x10\x02\x12\x0e\n\nTYPE_INT64\x10\x03\x12\x0f\n\x0bTYPE_UINT64\x10\x04\x12\x0e\n\nTYPE_INT32\x10\x05\x12\x10\n\x0cTYPE_FIXED64\x10\x06\x12\x10\n\x0cTYPE_FIXED32\x10\x07\x12\r\n\tTYPE_BOOL\x10\x08\x12\x0f\n\x0bTYPE_STRING\x10\t\x12\x0e\n\nTYPE_GROUP\x10\n\x12\x10\n\x0cTYPE_MESSAGE\x10\x0b\x12\x0e\n\nTYPE_BYTES\x10\x0c\x12\x0f\n\x0bTYPE_UINT32\x10\r\x12\r\n\tTYPE_ENUM\x10\x0e\x12\x11\n\rTYPE_SFIXED32\x10\x0f\x12\x11\n\rTYPE_SFIXED64\x10\x10\x12\x0f\n\x0bTYPE_SINT32\x10\x11\x12\x0f\n\x0bTYPE_SINT64\x10\x12\"C\n\x05Label\x12\x12\n\x0eLABEL_OPTIONAL\x10\x01\x12\x12\n\x0eLABEL_REQUIRED\x10\x02\x12\x12\n\x0eLABEL_REPEATED\x10\x03\"$\n\x14OneofDescriptorProto\x12\x0c\n\x04name\x18\x01 \x01(\t\"z\n\x13\x45numDescriptorProto\x12\x0c\n\x04name\x18\x01 \x01(\t\x12/\n\x05value\x18\x02 \x03(\x0b\x32 .proto2.EnumValueDescriptorProto\x12$\n\x07options\x18\x03 \x01(\x0b\x32\x13.proto2.EnumOptions\"c\n\x18\x45numValueDescriptorProto\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x0e\n\x06number\x18\x02 \x01(\x05\x12)\n\x07options\x18\x03 \x01(\x0b\x32\x18.proto2.EnumValueOptions\"\xad\x01\n\x16ServiceDescriptorProto\x12\x0c\n\x04name\x18\x01 \x01(\t\x12-\n\x06method\x18\x02 \x03(\x0b\x32\x1d.proto2.MethodDescriptorProto\x12-\n\x06stream\x18\x04 \x03(\x0b\x32\x1d.proto2.StreamDescriptorProto\x12\'\n\x07options\x18\x03 \x01(\x0b\x32\x16.proto2.ServiceOptions\"v\n\x15MethodDescriptorProto\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x12\n\ninput_type\x18\x02 \x01(\t\x12\x13\n\x0boutput_type\x18\x03 \x01(\t\x12&\n\x07options\x18\x04 \x01(\x0b\x32\x15.proto2.MethodOptions\"\x87\x01\n\x15StreamDescriptorProto\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x1b\n\x13\x63lient_message_type\x18\x02 \x01(\t\x12\x1b\n\x13server_message_type\x18\x03 \x01(\t\x12&\n\x07options\x18\x04 \x01(\x0b\x32\x15.proto2.StreamOptions\"\xba\t\n\x0b\x46ileOptions\x12\x19\n\x0e\x63\x63_api_version\x18\x02 \x01(\x05:\x01\x32\x12V\n\x14\x63\x63_api_compatibility\x18\x0f \x01(\x0e\x32&.proto2.FileOptions.CompatibilityLevel:\x10NO_COMPATIBILITY\x12\'\n\x19\x63\x63_proto_array_compatible\x18\x16 \x01(\x08:\x04true\x12\"\n\x14\x63\x63_utf8_verification\x18\x18 \x01(\x08:\x04true\x12$\n\x15\x63\x63_proto1_text_format\x18\x19 \x01(\x08:\x05\x66\x61lse\x12\x14\n\x0cjava_package\x18\x01 \x01(\t\x12\x19\n\x0epy_api_version\x18\x04 \x01(\x05:\x01\x32\x12\x1b\n\x10java_api_version\x18\x05 \x01(\x05:\x01\x32\x12!\n\x13java_use_javaproto2\x18\x06 \x01(\x08:\x04true\x12\x1e\n\x10java_java5_enums\x18\x07 \x01(\x08:\x04true\x12)\n\x1ajava_generate_rpc_baseimpl\x18\r \x01(\x08:\x05\x66\x61lse\x12#\n\x14java_use_javastrings\x18\x15 \x01(\x08:\x05\x66\x61lse\x12\x1c\n\x14java_alt_api_package\x18\x13 \x01(\t\x12\x33\n%java_enable_dual_generate_mutable_api\x18\x1a \x01(\x08:\x04true\x12\x1c\n\x14java_outer_classname\x18\x08 \x01(\t\x12\"\n\x13java_multiple_files\x18\n \x01(\x08:\x05\x66\x61lse\x12,\n\x1djava_generate_equals_and_hash\x18\x14 \x01(\x08:\x05\x66\x61lse\x12%\n\x16java_string_check_utf8\x18\x1b \x01(\x08:\x05\x66\x61lse\x12=\n\x0coptimize_for\x18\t \x01(\x0e\x32 .proto2.FileOptions.OptimizeMode:\x05SPEED\x12\x12\n\ngo_package\x18\x0b \x01(\t\x12\x1a\n\x12javascript_package\x18\x0c \x01(\t\x12\x1a\n\x0fszl_api_version\x18\x0e \x01(\x05:\x01\x31\x12\"\n\x13\x63\x63_generic_services\x18\x10 \x01(\x08:\x05\x66\x61lse\x12$\n\x15java_generic_services\x18\x11 \x01(\x08:\x05\x66\x61lse\x12\"\n\x13py_generic_services\x18\x12 \x01(\x08:\x05\x66\x61lse\x12\x19\n\ndeprecated\x18\x17 \x01(\x08:\x05\x66\x61lse\x12:\n\x14uninterpreted_option\x18\xe7\x07 \x03(\x0b\x32\x1b.proto2.UninterpretedOption\"c\n\x12\x43ompatibilityLevel\x12\x14\n\x10NO_COMPATIBILITY\x10\x00\x12\x15\n\x11PROTO1_COMPATIBLE\x10\x64\x12 \n\x1c\x44\x45PRECATED_PROTO1_COMPATIBLE\x10\x32\":\n\x0cOptimizeMode\x12\t\n\x05SPEED\x10\x01\x12\r\n\tCODE_SIZE\x10\x02\x12\x10\n\x0cLITE_RUNTIME\x10\x03*\t\x08\xe8\x07\x10\x80\x80\x80\x80\x02\"\xca\x01\n\x0eMessageOptions\x12&\n\x17message_set_wire_format\x18\x01 \x01(\x08:\x05\x66\x61lse\x12.\n\x1fno_standard_descriptor_accessor\x18\x02 \x01(\x08:\x05\x66\x61lse\x12\x19\n\ndeprecated\x18\x03 \x01(\x08:\x05\x66\x61lse\x12:\n\x14uninterpreted_option\x18\xe7\x07 \x03(\x0b\x32\x1b.proto2.UninterpretedOption*\t\x08\xe8\x07\x10\x80\x80\x80\x80\x02\"\xec\x04\n\x0c\x46ieldOptions\x12\x31\n\x05\x63type\x18\x01 \x01(\x0e\x32\x1a.proto2.FieldOptions.CType:\x06STRING\x12\x0e\n\x06packed\x18\x02 \x01(\x08\x12\x31\n\x05jtype\x18\x04 \x01(\x0e\x32\x1a.proto2.FieldOptions.JType:\x06NORMAL\x12\x36\n\x06jstype\x18\x06 \x01(\x0e\x32\x1b.proto2.FieldOptions.JSType:\tJS_NORMAL\x12\x13\n\x04lazy\x18\x05 \x01(\x08:\x05\x66\x61lse\x12\x19\n\ndeprecated\x18\x03 \x01(\x08:\x05\x66\x61lse\x12\x1c\n\x14\x65xperimental_map_key\x18\t \x01(\t\x12\x13\n\x04weak\x18\n \x01(\x08:\x05\x66\x61lse\x12<\n\x0fupgraded_option\x18\x0b \x03(\x0b\x32#.proto2.FieldOptions.UpgradedOption\x12:\n\x14uninterpreted_option\x18\xe7\x07 \x03(\x0b\x32\x1b.proto2.UninterpretedOption\x1a-\n\x0eUpgradedOption\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\t\"/\n\x05\x43Type\x12\n\n\x06STRING\x10\x00\x12\x08\n\x04\x43ORD\x10\x01\x12\x10\n\x0cSTRING_PIECE\x10\x02\"/\n\x05JType\x12\n\n\x06NORMAL\x10\x00\x12\t\n\x05\x42YTES\x10\x01\x12\x0f\n\x0b\x42YTE_BUFFER\x10\x02\"5\n\x06JSType\x12\r\n\tJS_NORMAL\x10\x00\x12\r\n\tJS_STRING\x10\x01\x12\r\n\tJS_NUMBER\x10\x02*\t\x08\xe8\x07\x10\x80\x80\x80\x80\x02\"\x99\x01\n\x0b\x45numOptions\x12\x13\n\x0bproto1_name\x18\x01 \x01(\t\x12\x13\n\x0b\x61llow_alias\x18\x02 \x01(\x08\x12\x19\n\ndeprecated\x18\x03 \x01(\x08:\x05\x66\x61lse\x12:\n\x14uninterpreted_option\x18\xe7\x07 \x03(\x0b\x32\x1b.proto2.UninterpretedOption*\t\x08\xe8\x07\x10\x80\x80\x80\x80\x02\"t\n\x10\x45numValueOptions\x12\x19\n\ndeprecated\x18\x01 \x01(\x08:\x05\x66\x61lse\x12:\n\x14uninterpreted_option\x18\xe7\x07 \x03(\x0b\x32\x1b.proto2.UninterpretedOption*\t\x08\xe8\x07\x10\x80\x80\x80\x80\x02\"\xb6\x01\n\x0eServiceOptions\x12\x1d\n\x0emulticast_stub\x18\x14 \x01(\x08:\x05\x66\x61lse\x12#\n\x17\x66\x61ilure_detection_delay\x18\x10 \x01(\x01:\x02-1\x12\x19\n\ndeprecated\x18! \x01(\x08:\x05\x66\x61lse\x12:\n\x14uninterpreted_option\x18\xe7\x07 \x03(\x0b\x32\x1b.proto2.UninterpretedOption*\t\x08\xe8\x07\x10\x80\x80\x80\x80\x02\"\x9c\x06\n\rMethodOptions\x12\x35\n\x08protocol\x18\x07 \x01(\x0e\x32\x1e.proto2.MethodOptions.Protocol:\x03TCP\x12\x14\n\x08\x64\x65\x61\x64line\x18\x08 \x01(\x01:\x02-1\x12$\n\x15\x64uplicate_suppression\x18\t \x01(\x08:\x05\x66\x61lse\x12\x18\n\tfail_fast\x18\n \x01(\x08:\x05\x66\x61lse\x12\x1b\n\x0e\x63lient_logging\x18\x0b \x01(\x11:\x03\x32\x35\x36\x12\x1b\n\x0eserver_logging\x18\x0c \x01(\x11:\x03\x32\x35\x36\x12\x41\n\x0esecurity_level\x18\r \x01(\x0e\x32#.proto2.MethodOptions.SecurityLevel:\x04NONE\x12\x43\n\x0fresponse_format\x18\x0f \x01(\x0e\x32\x1c.proto2.MethodOptions.Format:\x0cUNCOMPRESSED\x12\x42\n\x0erequest_format\x18\x11 \x01(\x0e\x32\x1c.proto2.MethodOptions.Format:\x0cUNCOMPRESSED\x12\x13\n\x0bstream_type\x18\x12 \x01(\t\x12\x16\n\x0esecurity_label\x18\x13 \x01(\t\x12\x18\n\x10\x63lient_streaming\x18\x14 \x01(\x08\x12\x18\n\x10server_streaming\x18\x15 \x01(\x08\x12\x19\n\ndeprecated\x18! \x01(\x08:\x05\x66\x61lse\x12:\n\x14uninterpreted_option\x18\xe7\x07 \x03(\x0b\x32\x1b.proto2.UninterpretedOption\"\x1c\n\x08Protocol\x12\x07\n\x03TCP\x10\x00\x12\x07\n\x03UDP\x10\x01\"e\n\rSecurityLevel\x12\x08\n\x04NONE\x10\x00\x12\r\n\tINTEGRITY\x10\x01\x12\x19\n\x15PRIVACY_AND_INTEGRITY\x10\x02\x12 \n\x1cSTRONG_PRIVACY_AND_INTEGRITY\x10\x03\"0\n\x06\x46ormat\x12\x10\n\x0cUNCOMPRESSED\x10\x00\x12\x14\n\x10ZIPPY_COMPRESSED\x10\x01*\t\x08\xe8\x07\x10\x80\x80\x80\x80\x02\"\xde\x03\n\rStreamOptions\x12!\n\x15\x63lient_initial_tokens\x18\x01 \x01(\x03:\x02-1\x12!\n\x15server_initial_tokens\x18\x02 \x01(\x03:\x02-1\x12<\n\ntoken_unit\x18\x03 \x01(\x0e\x32\x1f.proto2.StreamOptions.TokenUnit:\x07MESSAGE\x12\x41\n\x0esecurity_level\x18\x04 \x01(\x0e\x32#.proto2.MethodOptions.SecurityLevel:\x04NONE\x12\x16\n\x0esecurity_label\x18\x05 \x01(\t\x12\x1b\n\x0e\x63lient_logging\x18\x06 \x01(\x05:\x03\x32\x35\x36\x12\x1b\n\x0eserver_logging\x18\x07 \x01(\x05:\x03\x32\x35\x36\x12\x14\n\x08\x64\x65\x61\x64line\x18\x08 \x01(\x01:\x02-1\x12\x18\n\tfail_fast\x18\t \x01(\x08:\x05\x66\x61lse\x12\x19\n\ndeprecated\x18! \x01(\x08:\x05\x66\x61lse\x12:\n\x14uninterpreted_option\x18\xe7\x07 \x03(\x0b\x32\x1b.proto2.UninterpretedOption\"\"\n\tTokenUnit\x12\x0b\n\x07MESSAGE\x10\x00\x12\x08\n\x04\x42YTE\x10\x01*\t\x08\xe8\x07\x10\x80\x80\x80\x80\x02\"\x95\x02\n\x13UninterpretedOption\x12\x32\n\x04name\x18\x02 \x03(\x0b\x32$.proto2.UninterpretedOption.NamePart\x12\x18\n\x10identifier_value\x18\x03 \x01(\t\x12\x1a\n\x12positive_int_value\x18\x04 \x01(\x04\x12\x1a\n\x12negative_int_value\x18\x05 \x01(\x03\x12\x14\n\x0c\x64ouble_value\x18\x06 \x01(\x01\x12\x14\n\x0cstring_value\x18\x07 \x01(\x0c\x12\x17\n\x0f\x61ggregate_value\x18\x08 \x01(\t\x1a\x33\n\x08NamePart\x12\x11\n\tname_part\x18\x01 \x02(\t\x12\x14\n\x0cis_extension\x18\x02 \x02(\x08\"\xa8\x01\n\x0eSourceCodeInfo\x12\x31\n\x08location\x18\x01 \x03(\x0b\x32\x1f.proto2.SourceCodeInfo.Location\x1a\x63\n\x08Location\x12\x10\n\x04path\x18\x01 \x03(\x05\x42\x02\x10\x01\x12\x10\n\x04span\x18\x02 \x03(\x05\x42\x02\x10\x01\x12\x18\n\x10leading_comments\x18\x03 \x01(\t\x12\x19\n\x11trailing_comments\x18\x04 \x01(\tB)\n\x13\x63om.google.protobufB\x10\x44\x65scriptorProtosH\x01')



_FIELDDESCRIPTORPROTO_TYPE = _descriptor.EnumDescriptor(
  name='Type',
  full_name='proto2.FieldDescriptorProto.Type',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='TYPE_DOUBLE', index=0, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TYPE_FLOAT', index=1, number=2,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TYPE_INT64', index=2, number=3,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TYPE_UINT64', index=3, number=4,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TYPE_INT32', index=4, number=5,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TYPE_FIXED64', index=5, number=6,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TYPE_FIXED32', index=6, number=7,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TYPE_BOOL', index=7, number=8,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TYPE_STRING', index=8, number=9,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TYPE_GROUP', index=9, number=10,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TYPE_MESSAGE', index=10, number=11,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TYPE_BYTES', index=11, number=12,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TYPE_UINT32', index=12, number=13,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TYPE_ENUM', index=13, number=14,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TYPE_SFIXED32', index=14, number=15,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TYPE_SFIXED64', index=15, number=16,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TYPE_SINT32', index=16, number=17,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TYPE_SINT64', index=17, number=18,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=1217,
  serialized_end=1527,
)

_FIELDDESCRIPTORPROTO_LABEL = _descriptor.EnumDescriptor(
  name='Label',
  full_name='proto2.FieldDescriptorProto.Label',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='LABEL_OPTIONAL', index=0, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='LABEL_REQUIRED', index=1, number=2,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='LABEL_REPEATED', index=2, number=3,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=1529,
  serialized_end=1596,
)

_FILEOPTIONS_COMPATIBILITYLEVEL = _descriptor.EnumDescriptor(
  name='CompatibilityLevel',
  full_name='proto2.FileOptions.CompatibilityLevel',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='NO_COMPATIBILITY', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='PROTO1_COMPATIBLE', index=1, number=100,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='DEPRECATED_PROTO1_COMPATIBLE', index=2, number=50,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=3336,
  serialized_end=3435,
)

_FILEOPTIONS_OPTIMIZEMODE = _descriptor.EnumDescriptor(
  name='OptimizeMode',
  full_name='proto2.FileOptions.OptimizeMode',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='SPEED', index=0, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CODE_SIZE', index=1, number=2,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='LITE_RUNTIME', index=2, number=3,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=3437,
  serialized_end=3495,
)

_FIELDOPTIONS_CTYPE = _descriptor.EnumDescriptor(
  name='CType',
  full_name='proto2.FieldOptions.CType',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='STRING', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CORD', index=1, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='STRING_PIECE', index=2, number=2,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=4172,
  serialized_end=4219,
)

_FIELDOPTIONS_JTYPE = _descriptor.EnumDescriptor(
  name='JType',
  full_name='proto2.FieldOptions.JType',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='NORMAL', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='BYTES', index=1, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='BYTE_BUFFER', index=2, number=2,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=4221,
  serialized_end=4268,
)

_FIELDOPTIONS_JSTYPE = _descriptor.EnumDescriptor(
  name='JSType',
  full_name='proto2.FieldOptions.JSType',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='JS_NORMAL', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='JS_STRING', index=1, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='JS_NUMBER', index=2, number=2,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=4270,
  serialized_end=4323,
)

_METHODOPTIONS_PROTOCOL = _descriptor.EnumDescriptor(
  name='Protocol',
  full_name='proto2.MethodOptions.Protocol',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='TCP', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='UDP', index=1, number=1,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=5400,
  serialized_end=5428,
)

_METHODOPTIONS_SECURITYLEVEL = _descriptor.EnumDescriptor(
  name='SecurityLevel',
  full_name='proto2.MethodOptions.SecurityLevel',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='NONE', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='INTEGRITY', index=1, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='PRIVACY_AND_INTEGRITY', index=2, number=2,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='STRONG_PRIVACY_AND_INTEGRITY', index=3, number=3,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=5430,
  serialized_end=5531,
)

_METHODOPTIONS_FORMAT = _descriptor.EnumDescriptor(
  name='Format',
  full_name='proto2.MethodOptions.Format',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='UNCOMPRESSED', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ZIPPY_COMPRESSED', index=1, number=1,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=5533,
  serialized_end=5581,
)

_STREAMOPTIONS_TOKENUNIT = _descriptor.EnumDescriptor(
  name='TokenUnit',
  full_name='proto2.StreamOptions.TokenUnit',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='MESSAGE', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='BYTE', index=1, number=1,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=6028,
  serialized_end=6062,
)


_FILEDESCRIPTORSET = _descriptor.Descriptor(
  name='FileDescriptorSet',
  full_name='proto2.FileDescriptorSet',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='file', full_name='proto2.FileDescriptorSet.file', index=0,
      number=1, type=11, cpp_type=10, label=3,
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
  serialized_start=45,
  serialized_end=107,
)


_FILEDESCRIPTORPROTO = _descriptor.Descriptor(
  name='FileDescriptorProto',
  full_name='proto2.FileDescriptorProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='proto2.FileDescriptorProto.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='package', full_name='proto2.FileDescriptorProto.package', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='dependency', full_name='proto2.FileDescriptorProto.dependency', index=2,
      number=3, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='public_dependency', full_name='proto2.FileDescriptorProto.public_dependency', index=3,
      number=10, type=5, cpp_type=1, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='weak_dependency', full_name='proto2.FileDescriptorProto.weak_dependency', index=4,
      number=11, type=5, cpp_type=1, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='message_type', full_name='proto2.FileDescriptorProto.message_type', index=5,
      number=4, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='enum_type', full_name='proto2.FileDescriptorProto.enum_type', index=6,
      number=5, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='service', full_name='proto2.FileDescriptorProto.service', index=7,
      number=6, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='extension', full_name='proto2.FileDescriptorProto.extension', index=8,
      number=7, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='options', full_name='proto2.FileDescriptorProto.options', index=9,
      number=8, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='source_code_info', full_name='proto2.FileDescriptorProto.source_code_info', index=10,
      number=9, type=11, cpp_type=10, label=1,
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
  serialized_start=110,
  serialized_end=515,
)


_DESCRIPTORPROTO_EXTENSIONRANGE = _descriptor.Descriptor(
  name='ExtensionRange',
  full_name='proto2.DescriptorProto.ExtensionRange',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='start', full_name='proto2.DescriptorProto.ExtensionRange.start', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='end', full_name='proto2.DescriptorProto.ExtensionRange.end', index=1,
      number=2, type=5, cpp_type=1, label=1,
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
  serialized_start=895,
  serialized_end=939,
)

_DESCRIPTORPROTO = _descriptor.Descriptor(
  name='DescriptorProto',
  full_name='proto2.DescriptorProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='proto2.DescriptorProto.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='field', full_name='proto2.DescriptorProto.field', index=1,
      number=2, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='extension', full_name='proto2.DescriptorProto.extension', index=2,
      number=6, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='nested_type', full_name='proto2.DescriptorProto.nested_type', index=3,
      number=3, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='enum_type', full_name='proto2.DescriptorProto.enum_type', index=4,
      number=4, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='extension_range', full_name='proto2.DescriptorProto.extension_range', index=5,
      number=5, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='oneof_decl', full_name='proto2.DescriptorProto.oneof_decl', index=6,
      number=8, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='options', full_name='proto2.DescriptorProto.options', index=7,
      number=7, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_DESCRIPTORPROTO_EXTENSIONRANGE, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=518,
  serialized_end=939,
)


_FIELDDESCRIPTORPROTO = _descriptor.Descriptor(
  name='FieldDescriptorProto',
  full_name='proto2.FieldDescriptorProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='proto2.FieldDescriptorProto.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='number', full_name='proto2.FieldDescriptorProto.number', index=1,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='label', full_name='proto2.FieldDescriptorProto.label', index=2,
      number=4, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=1,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='type', full_name='proto2.FieldDescriptorProto.type', index=3,
      number=5, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=1,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='type_name', full_name='proto2.FieldDescriptorProto.type_name', index=4,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='extendee', full_name='proto2.FieldDescriptorProto.extendee', index=5,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='default_value', full_name='proto2.FieldDescriptorProto.default_value', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='oneof_index', full_name='proto2.FieldDescriptorProto.oneof_index', index=7,
      number=9, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='options', full_name='proto2.FieldDescriptorProto.options', index=8,
      number=8, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
    _FIELDDESCRIPTORPROTO_TYPE,
    _FIELDDESCRIPTORPROTO_LABEL,
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=942,
  serialized_end=1596,
)


_ONEOFDESCRIPTORPROTO = _descriptor.Descriptor(
  name='OneofDescriptorProto',
  full_name='proto2.OneofDescriptorProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='proto2.OneofDescriptorProto.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
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
  serialized_start=1598,
  serialized_end=1634,
)


_ENUMDESCRIPTORPROTO = _descriptor.Descriptor(
  name='EnumDescriptorProto',
  full_name='proto2.EnumDescriptorProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='proto2.EnumDescriptorProto.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='value', full_name='proto2.EnumDescriptorProto.value', index=1,
      number=2, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='options', full_name='proto2.EnumDescriptorProto.options', index=2,
      number=3, type=11, cpp_type=10, label=1,
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
  serialized_start=1636,
  serialized_end=1758,
)


_ENUMVALUEDESCRIPTORPROTO = _descriptor.Descriptor(
  name='EnumValueDescriptorProto',
  full_name='proto2.EnumValueDescriptorProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='proto2.EnumValueDescriptorProto.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='number', full_name='proto2.EnumValueDescriptorProto.number', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='options', full_name='proto2.EnumValueDescriptorProto.options', index=2,
      number=3, type=11, cpp_type=10, label=1,
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
  serialized_start=1760,
  serialized_end=1859,
)


_SERVICEDESCRIPTORPROTO = _descriptor.Descriptor(
  name='ServiceDescriptorProto',
  full_name='proto2.ServiceDescriptorProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='proto2.ServiceDescriptorProto.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='method', full_name='proto2.ServiceDescriptorProto.method', index=1,
      number=2, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='stream', full_name='proto2.ServiceDescriptorProto.stream', index=2,
      number=4, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='options', full_name='proto2.ServiceDescriptorProto.options', index=3,
      number=3, type=11, cpp_type=10, label=1,
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
  serialized_start=1862,
  serialized_end=2035,
)


_METHODDESCRIPTORPROTO = _descriptor.Descriptor(
  name='MethodDescriptorProto',
  full_name='proto2.MethodDescriptorProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='proto2.MethodDescriptorProto.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='input_type', full_name='proto2.MethodDescriptorProto.input_type', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='output_type', full_name='proto2.MethodDescriptorProto.output_type', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='options', full_name='proto2.MethodDescriptorProto.options', index=3,
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
  serialized_start=2037,
  serialized_end=2155,
)


_STREAMDESCRIPTORPROTO = _descriptor.Descriptor(
  name='StreamDescriptorProto',
  full_name='proto2.StreamDescriptorProto',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='proto2.StreamDescriptorProto.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='client_message_type', full_name='proto2.StreamDescriptorProto.client_message_type', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='server_message_type', full_name='proto2.StreamDescriptorProto.server_message_type', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='options', full_name='proto2.StreamDescriptorProto.options', index=3,
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
  serialized_start=2158,
  serialized_end=2293,
)


_FILEOPTIONS = _descriptor.Descriptor(
  name='FileOptions',
  full_name='proto2.FileOptions',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='cc_api_version', full_name='proto2.FileOptions.cc_api_version', index=0,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=2,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='cc_api_compatibility', full_name='proto2.FileOptions.cc_api_compatibility', index=1,
      number=15, type=14, cpp_type=8, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='cc_proto_array_compatible', full_name='proto2.FileOptions.cc_proto_array_compatible', index=2,
      number=22, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=True,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='cc_utf8_verification', full_name='proto2.FileOptions.cc_utf8_verification', index=3,
      number=24, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=True,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='cc_proto1_text_format', full_name='proto2.FileOptions.cc_proto1_text_format', index=4,
      number=25, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='java_package', full_name='proto2.FileOptions.java_package', index=5,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='py_api_version', full_name='proto2.FileOptions.py_api_version', index=6,
      number=4, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=2,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='java_api_version', full_name='proto2.FileOptions.java_api_version', index=7,
      number=5, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=2,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='java_use_javaproto2', full_name='proto2.FileOptions.java_use_javaproto2', index=8,
      number=6, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=True,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='java_java5_enums', full_name='proto2.FileOptions.java_java5_enums', index=9,
      number=7, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=True,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='java_generate_rpc_baseimpl', full_name='proto2.FileOptions.java_generate_rpc_baseimpl', index=10,
      number=13, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='java_use_javastrings', full_name='proto2.FileOptions.java_use_javastrings', index=11,
      number=21, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='java_alt_api_package', full_name='proto2.FileOptions.java_alt_api_package', index=12,
      number=19, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='java_enable_dual_generate_mutable_api', full_name='proto2.FileOptions.java_enable_dual_generate_mutable_api', index=13,
      number=26, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=True,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='java_outer_classname', full_name='proto2.FileOptions.java_outer_classname', index=14,
      number=8, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='java_multiple_files', full_name='proto2.FileOptions.java_multiple_files', index=15,
      number=10, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='java_generate_equals_and_hash', full_name='proto2.FileOptions.java_generate_equals_and_hash', index=16,
      number=20, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='java_string_check_utf8', full_name='proto2.FileOptions.java_string_check_utf8', index=17,
      number=27, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='optimize_for', full_name='proto2.FileOptions.optimize_for', index=18,
      number=9, type=14, cpp_type=8, label=1,
      has_default_value=True, default_value=1,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='go_package', full_name='proto2.FileOptions.go_package', index=19,
      number=11, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='javascript_package', full_name='proto2.FileOptions.javascript_package', index=20,
      number=12, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='szl_api_version', full_name='proto2.FileOptions.szl_api_version', index=21,
      number=14, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=1,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='cc_generic_services', full_name='proto2.FileOptions.cc_generic_services', index=22,
      number=16, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='java_generic_services', full_name='proto2.FileOptions.java_generic_services', index=23,
      number=17, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='py_generic_services', full_name='proto2.FileOptions.py_generic_services', index=24,
      number=18, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='deprecated', full_name='proto2.FileOptions.deprecated', index=25,
      number=23, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='uninterpreted_option', full_name='proto2.FileOptions.uninterpreted_option', index=26,
      number=999, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
    _FILEOPTIONS_COMPATIBILITYLEVEL,
    _FILEOPTIONS_OPTIMIZEMODE,
  ],
  options=None,
  is_extendable=True,
  extension_ranges=[(1000, 536870912), ],
  serialized_start=2296,
  serialized_end=3506,
)


_MESSAGEOPTIONS = _descriptor.Descriptor(
  name='MessageOptions',
  full_name='proto2.MessageOptions',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='message_set_wire_format', full_name='proto2.MessageOptions.message_set_wire_format', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='no_standard_descriptor_accessor', full_name='proto2.MessageOptions.no_standard_descriptor_accessor', index=1,
      number=2, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='deprecated', full_name='proto2.MessageOptions.deprecated', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='uninterpreted_option', full_name='proto2.MessageOptions.uninterpreted_option', index=3,
      number=999, type=11, cpp_type=10, label=3,
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
  is_extendable=True,
  extension_ranges=[(1000, 536870912), ],
  serialized_start=3509,
  serialized_end=3711,
)


_FIELDOPTIONS_UPGRADEDOPTION = _descriptor.Descriptor(
  name='UpgradedOption',
  full_name='proto2.FieldOptions.UpgradedOption',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='proto2.FieldOptions.UpgradedOption.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='value', full_name='proto2.FieldOptions.UpgradedOption.value', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
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
  serialized_start=4125,
  serialized_end=4170,
)

_FIELDOPTIONS = _descriptor.Descriptor(
  name='FieldOptions',
  full_name='proto2.FieldOptions',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='ctype', full_name='proto2.FieldOptions.ctype', index=0,
      number=1, type=14, cpp_type=8, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='packed', full_name='proto2.FieldOptions.packed', index=1,
      number=2, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='jtype', full_name='proto2.FieldOptions.jtype', index=2,
      number=4, type=14, cpp_type=8, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='jstype', full_name='proto2.FieldOptions.jstype', index=3,
      number=6, type=14, cpp_type=8, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='lazy', full_name='proto2.FieldOptions.lazy', index=4,
      number=5, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='deprecated', full_name='proto2.FieldOptions.deprecated', index=5,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='experimental_map_key', full_name='proto2.FieldOptions.experimental_map_key', index=6,
      number=9, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='weak', full_name='proto2.FieldOptions.weak', index=7,
      number=10, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='upgraded_option', full_name='proto2.FieldOptions.upgraded_option', index=8,
      number=11, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='uninterpreted_option', full_name='proto2.FieldOptions.uninterpreted_option', index=9,
      number=999, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_FIELDOPTIONS_UPGRADEDOPTION, ],
  enum_types=[
    _FIELDOPTIONS_CTYPE,
    _FIELDOPTIONS_JTYPE,
    _FIELDOPTIONS_JSTYPE,
  ],
  options=None,
  is_extendable=True,
  extension_ranges=[(1000, 536870912), ],
  serialized_start=3714,
  serialized_end=4334,
)


_ENUMOPTIONS = _descriptor.Descriptor(
  name='EnumOptions',
  full_name='proto2.EnumOptions',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='proto1_name', full_name='proto2.EnumOptions.proto1_name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='allow_alias', full_name='proto2.EnumOptions.allow_alias', index=1,
      number=2, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='deprecated', full_name='proto2.EnumOptions.deprecated', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='uninterpreted_option', full_name='proto2.EnumOptions.uninterpreted_option', index=3,
      number=999, type=11, cpp_type=10, label=3,
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
  is_extendable=True,
  extension_ranges=[(1000, 536870912), ],
  serialized_start=4337,
  serialized_end=4490,
)


_ENUMVALUEOPTIONS = _descriptor.Descriptor(
  name='EnumValueOptions',
  full_name='proto2.EnumValueOptions',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='deprecated', full_name='proto2.EnumValueOptions.deprecated', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='uninterpreted_option', full_name='proto2.EnumValueOptions.uninterpreted_option', index=1,
      number=999, type=11, cpp_type=10, label=3,
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
  is_extendable=True,
  extension_ranges=[(1000, 536870912), ],
  serialized_start=4492,
  serialized_end=4608,
)


_SERVICEOPTIONS = _descriptor.Descriptor(
  name='ServiceOptions',
  full_name='proto2.ServiceOptions',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='multicast_stub', full_name='proto2.ServiceOptions.multicast_stub', index=0,
      number=20, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='failure_detection_delay', full_name='proto2.ServiceOptions.failure_detection_delay', index=1,
      number=16, type=1, cpp_type=5, label=1,
      has_default_value=True, default_value=-1,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='deprecated', full_name='proto2.ServiceOptions.deprecated', index=2,
      number=33, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='uninterpreted_option', full_name='proto2.ServiceOptions.uninterpreted_option', index=3,
      number=999, type=11, cpp_type=10, label=3,
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
  is_extendable=True,
  extension_ranges=[(1000, 536870912), ],
  serialized_start=4611,
  serialized_end=4793,
)


_METHODOPTIONS = _descriptor.Descriptor(
  name='MethodOptions',
  full_name='proto2.MethodOptions',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='protocol', full_name='proto2.MethodOptions.protocol', index=0,
      number=7, type=14, cpp_type=8, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='deadline', full_name='proto2.MethodOptions.deadline', index=1,
      number=8, type=1, cpp_type=5, label=1,
      has_default_value=True, default_value=-1,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='duplicate_suppression', full_name='proto2.MethodOptions.duplicate_suppression', index=2,
      number=9, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='fail_fast', full_name='proto2.MethodOptions.fail_fast', index=3,
      number=10, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='client_logging', full_name='proto2.MethodOptions.client_logging', index=4,
      number=11, type=17, cpp_type=1, label=1,
      has_default_value=True, default_value=256,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='server_logging', full_name='proto2.MethodOptions.server_logging', index=5,
      number=12, type=17, cpp_type=1, label=1,
      has_default_value=True, default_value=256,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='security_level', full_name='proto2.MethodOptions.security_level', index=6,
      number=13, type=14, cpp_type=8, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='response_format', full_name='proto2.MethodOptions.response_format', index=7,
      number=15, type=14, cpp_type=8, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='request_format', full_name='proto2.MethodOptions.request_format', index=8,
      number=17, type=14, cpp_type=8, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='stream_type', full_name='proto2.MethodOptions.stream_type', index=9,
      number=18, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='security_label', full_name='proto2.MethodOptions.security_label', index=10,
      number=19, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='client_streaming', full_name='proto2.MethodOptions.client_streaming', index=11,
      number=20, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='server_streaming', full_name='proto2.MethodOptions.server_streaming', index=12,
      number=21, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='deprecated', full_name='proto2.MethodOptions.deprecated', index=13,
      number=33, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='uninterpreted_option', full_name='proto2.MethodOptions.uninterpreted_option', index=14,
      number=999, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
    _METHODOPTIONS_PROTOCOL,
    _METHODOPTIONS_SECURITYLEVEL,
    _METHODOPTIONS_FORMAT,
  ],
  options=None,
  is_extendable=True,
  extension_ranges=[(1000, 536870912), ],
  serialized_start=4796,
  serialized_end=5592,
)


_STREAMOPTIONS = _descriptor.Descriptor(
  name='StreamOptions',
  full_name='proto2.StreamOptions',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='client_initial_tokens', full_name='proto2.StreamOptions.client_initial_tokens', index=0,
      number=1, type=3, cpp_type=2, label=1,
      has_default_value=True, default_value=-1,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='server_initial_tokens', full_name='proto2.StreamOptions.server_initial_tokens', index=1,
      number=2, type=3, cpp_type=2, label=1,
      has_default_value=True, default_value=-1,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='token_unit', full_name='proto2.StreamOptions.token_unit', index=2,
      number=3, type=14, cpp_type=8, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='security_level', full_name='proto2.StreamOptions.security_level', index=3,
      number=4, type=14, cpp_type=8, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='security_label', full_name='proto2.StreamOptions.security_label', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='client_logging', full_name='proto2.StreamOptions.client_logging', index=5,
      number=6, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=256,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='server_logging', full_name='proto2.StreamOptions.server_logging', index=6,
      number=7, type=5, cpp_type=1, label=1,
      has_default_value=True, default_value=256,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='deadline', full_name='proto2.StreamOptions.deadline', index=7,
      number=8, type=1, cpp_type=5, label=1,
      has_default_value=True, default_value=-1,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='fail_fast', full_name='proto2.StreamOptions.fail_fast', index=8,
      number=9, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='deprecated', full_name='proto2.StreamOptions.deprecated', index=9,
      number=33, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='uninterpreted_option', full_name='proto2.StreamOptions.uninterpreted_option', index=10,
      number=999, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
    _STREAMOPTIONS_TOKENUNIT,
  ],
  options=None,
  is_extendable=True,
  extension_ranges=[(1000, 536870912), ],
  serialized_start=5595,
  serialized_end=6073,
)


_UNINTERPRETEDOPTION_NAMEPART = _descriptor.Descriptor(
  name='NamePart',
  full_name='proto2.UninterpretedOption.NamePart',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name_part', full_name='proto2.UninterpretedOption.NamePart.name_part', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='is_extension', full_name='proto2.UninterpretedOption.NamePart.is_extension', index=1,
      number=2, type=8, cpp_type=7, label=2,
      has_default_value=False, default_value=False,
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
  serialized_start=6302,
  serialized_end=6353,
)

_UNINTERPRETEDOPTION = _descriptor.Descriptor(
  name='UninterpretedOption',
  full_name='proto2.UninterpretedOption',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='proto2.UninterpretedOption.name', index=0,
      number=2, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='identifier_value', full_name='proto2.UninterpretedOption.identifier_value', index=1,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='positive_int_value', full_name='proto2.UninterpretedOption.positive_int_value', index=2,
      number=4, type=4, cpp_type=4, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='negative_int_value', full_name='proto2.UninterpretedOption.negative_int_value', index=3,
      number=5, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='double_value', full_name='proto2.UninterpretedOption.double_value', index=4,
      number=6, type=1, cpp_type=5, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='string_value', full_name='proto2.UninterpretedOption.string_value', index=5,
      number=7, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value="",
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='aggregate_value', full_name='proto2.UninterpretedOption.aggregate_value', index=6,
      number=8, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_UNINTERPRETEDOPTION_NAMEPART, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=6076,
  serialized_end=6353,
)


_SOURCECODEINFO_LOCATION = _descriptor.Descriptor(
  name='Location',
  full_name='proto2.SourceCodeInfo.Location',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='path', full_name='proto2.SourceCodeInfo.Location.path', index=0,
      number=1, type=5, cpp_type=1, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='span', full_name='proto2.SourceCodeInfo.Location.span', index=1,
      number=2, type=5, cpp_type=1, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='leading_comments', full_name='proto2.SourceCodeInfo.Location.leading_comments', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='trailing_comments', full_name='proto2.SourceCodeInfo.Location.trailing_comments', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
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
  serialized_start=6425,
  serialized_end=6524,
)

_SOURCECODEINFO = _descriptor.Descriptor(
  name='SourceCodeInfo',
  full_name='proto2.SourceCodeInfo',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='location', full_name='proto2.SourceCodeInfo.location', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_SOURCECODEINFO_LOCATION, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=6356,
  serialized_end=6524,
)

_FILEDESCRIPTORSET.fields_by_name['file'].message_type = _FILEDESCRIPTORPROTO
_FILEDESCRIPTORPROTO.fields_by_name['message_type'].message_type = _DESCRIPTORPROTO
_FILEDESCRIPTORPROTO.fields_by_name['enum_type'].message_type = _ENUMDESCRIPTORPROTO
_FILEDESCRIPTORPROTO.fields_by_name['service'].message_type = _SERVICEDESCRIPTORPROTO
_FILEDESCRIPTORPROTO.fields_by_name['extension'].message_type = _FIELDDESCRIPTORPROTO
_FILEDESCRIPTORPROTO.fields_by_name['options'].message_type = _FILEOPTIONS
_FILEDESCRIPTORPROTO.fields_by_name['source_code_info'].message_type = _SOURCECODEINFO
_DESCRIPTORPROTO_EXTENSIONRANGE.containing_type = _DESCRIPTORPROTO;
_DESCRIPTORPROTO.fields_by_name['field'].message_type = _FIELDDESCRIPTORPROTO
_DESCRIPTORPROTO.fields_by_name['extension'].message_type = _FIELDDESCRIPTORPROTO
_DESCRIPTORPROTO.fields_by_name['nested_type'].message_type = _DESCRIPTORPROTO
_DESCRIPTORPROTO.fields_by_name['enum_type'].message_type = _ENUMDESCRIPTORPROTO
_DESCRIPTORPROTO.fields_by_name['extension_range'].message_type = _DESCRIPTORPROTO_EXTENSIONRANGE
_DESCRIPTORPROTO.fields_by_name['oneof_decl'].message_type = _ONEOFDESCRIPTORPROTO
_DESCRIPTORPROTO.fields_by_name['options'].message_type = _MESSAGEOPTIONS
_FIELDDESCRIPTORPROTO.fields_by_name['label'].enum_type = _FIELDDESCRIPTORPROTO_LABEL
_FIELDDESCRIPTORPROTO.fields_by_name['type'].enum_type = _FIELDDESCRIPTORPROTO_TYPE
_FIELDDESCRIPTORPROTO.fields_by_name['options'].message_type = _FIELDOPTIONS
_FIELDDESCRIPTORPROTO_TYPE.containing_type = _FIELDDESCRIPTORPROTO;
_FIELDDESCRIPTORPROTO_LABEL.containing_type = _FIELDDESCRIPTORPROTO;
_ENUMDESCRIPTORPROTO.fields_by_name['value'].message_type = _ENUMVALUEDESCRIPTORPROTO
_ENUMDESCRIPTORPROTO.fields_by_name['options'].message_type = _ENUMOPTIONS
_ENUMVALUEDESCRIPTORPROTO.fields_by_name['options'].message_type = _ENUMVALUEOPTIONS
_SERVICEDESCRIPTORPROTO.fields_by_name['method'].message_type = _METHODDESCRIPTORPROTO
_SERVICEDESCRIPTORPROTO.fields_by_name['stream'].message_type = _STREAMDESCRIPTORPROTO
_SERVICEDESCRIPTORPROTO.fields_by_name['options'].message_type = _SERVICEOPTIONS
_METHODDESCRIPTORPROTO.fields_by_name['options'].message_type = _METHODOPTIONS
_STREAMDESCRIPTORPROTO.fields_by_name['options'].message_type = _STREAMOPTIONS
_FILEOPTIONS.fields_by_name['cc_api_compatibility'].enum_type = _FILEOPTIONS_COMPATIBILITYLEVEL
_FILEOPTIONS.fields_by_name['optimize_for'].enum_type = _FILEOPTIONS_OPTIMIZEMODE
_FILEOPTIONS.fields_by_name['uninterpreted_option'].message_type = _UNINTERPRETEDOPTION
_FILEOPTIONS_COMPATIBILITYLEVEL.containing_type = _FILEOPTIONS;
_FILEOPTIONS_OPTIMIZEMODE.containing_type = _FILEOPTIONS;
_MESSAGEOPTIONS.fields_by_name['uninterpreted_option'].message_type = _UNINTERPRETEDOPTION
_FIELDOPTIONS_UPGRADEDOPTION.containing_type = _FIELDOPTIONS;
_FIELDOPTIONS.fields_by_name['ctype'].enum_type = _FIELDOPTIONS_CTYPE
_FIELDOPTIONS.fields_by_name['jtype'].enum_type = _FIELDOPTIONS_JTYPE
_FIELDOPTIONS.fields_by_name['jstype'].enum_type = _FIELDOPTIONS_JSTYPE
_FIELDOPTIONS.fields_by_name['upgraded_option'].message_type = _FIELDOPTIONS_UPGRADEDOPTION
_FIELDOPTIONS.fields_by_name['uninterpreted_option'].message_type = _UNINTERPRETEDOPTION
_FIELDOPTIONS_CTYPE.containing_type = _FIELDOPTIONS;
_FIELDOPTIONS_JTYPE.containing_type = _FIELDOPTIONS;
_FIELDOPTIONS_JSTYPE.containing_type = _FIELDOPTIONS;
_ENUMOPTIONS.fields_by_name['uninterpreted_option'].message_type = _UNINTERPRETEDOPTION
_ENUMVALUEOPTIONS.fields_by_name['uninterpreted_option'].message_type = _UNINTERPRETEDOPTION
_SERVICEOPTIONS.fields_by_name['uninterpreted_option'].message_type = _UNINTERPRETEDOPTION
_METHODOPTIONS.fields_by_name['protocol'].enum_type = _METHODOPTIONS_PROTOCOL
_METHODOPTIONS.fields_by_name['security_level'].enum_type = _METHODOPTIONS_SECURITYLEVEL
_METHODOPTIONS.fields_by_name['response_format'].enum_type = _METHODOPTIONS_FORMAT
_METHODOPTIONS.fields_by_name['request_format'].enum_type = _METHODOPTIONS_FORMAT
_METHODOPTIONS.fields_by_name['uninterpreted_option'].message_type = _UNINTERPRETEDOPTION
_METHODOPTIONS_PROTOCOL.containing_type = _METHODOPTIONS;
_METHODOPTIONS_SECURITYLEVEL.containing_type = _METHODOPTIONS;
_METHODOPTIONS_FORMAT.containing_type = _METHODOPTIONS;
_STREAMOPTIONS.fields_by_name['token_unit'].enum_type = _STREAMOPTIONS_TOKENUNIT
_STREAMOPTIONS.fields_by_name['security_level'].enum_type = _METHODOPTIONS_SECURITYLEVEL
_STREAMOPTIONS.fields_by_name['uninterpreted_option'].message_type = _UNINTERPRETEDOPTION
_STREAMOPTIONS_TOKENUNIT.containing_type = _STREAMOPTIONS;
_UNINTERPRETEDOPTION_NAMEPART.containing_type = _UNINTERPRETEDOPTION;
_UNINTERPRETEDOPTION.fields_by_name['name'].message_type = _UNINTERPRETEDOPTION_NAMEPART
_SOURCECODEINFO_LOCATION.containing_type = _SOURCECODEINFO;
_SOURCECODEINFO.fields_by_name['location'].message_type = _SOURCECODEINFO_LOCATION
DESCRIPTOR.message_types_by_name['FileDescriptorSet'] = _FILEDESCRIPTORSET
DESCRIPTOR.message_types_by_name['FileDescriptorProto'] = _FILEDESCRIPTORPROTO
DESCRIPTOR.message_types_by_name['DescriptorProto'] = _DESCRIPTORPROTO
DESCRIPTOR.message_types_by_name['FieldDescriptorProto'] = _FIELDDESCRIPTORPROTO
DESCRIPTOR.message_types_by_name['OneofDescriptorProto'] = _ONEOFDESCRIPTORPROTO
DESCRIPTOR.message_types_by_name['EnumDescriptorProto'] = _ENUMDESCRIPTORPROTO
DESCRIPTOR.message_types_by_name['EnumValueDescriptorProto'] = _ENUMVALUEDESCRIPTORPROTO
DESCRIPTOR.message_types_by_name['ServiceDescriptorProto'] = _SERVICEDESCRIPTORPROTO
DESCRIPTOR.message_types_by_name['MethodDescriptorProto'] = _METHODDESCRIPTORPROTO
DESCRIPTOR.message_types_by_name['StreamDescriptorProto'] = _STREAMDESCRIPTORPROTO
DESCRIPTOR.message_types_by_name['FileOptions'] = _FILEOPTIONS
DESCRIPTOR.message_types_by_name['MessageOptions'] = _MESSAGEOPTIONS
DESCRIPTOR.message_types_by_name['FieldOptions'] = _FIELDOPTIONS
DESCRIPTOR.message_types_by_name['EnumOptions'] = _ENUMOPTIONS
DESCRIPTOR.message_types_by_name['EnumValueOptions'] = _ENUMVALUEOPTIONS
DESCRIPTOR.message_types_by_name['ServiceOptions'] = _SERVICEOPTIONS
DESCRIPTOR.message_types_by_name['MethodOptions'] = _METHODOPTIONS
DESCRIPTOR.message_types_by_name['StreamOptions'] = _STREAMOPTIONS
DESCRIPTOR.message_types_by_name['UninterpretedOption'] = _UNINTERPRETEDOPTION
DESCRIPTOR.message_types_by_name['SourceCodeInfo'] = _SOURCECODEINFO

class FileDescriptorSet(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _FILEDESCRIPTORSET



class FileDescriptorProto(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _FILEDESCRIPTORPROTO



class DescriptorProto(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType

  class ExtensionRange(_message.Message):
    __metaclass__ = _reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _DESCRIPTORPROTO_EXTENSIONRANGE


  DESCRIPTOR = _DESCRIPTORPROTO



class FieldDescriptorProto(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _FIELDDESCRIPTORPROTO



class OneofDescriptorProto(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ONEOFDESCRIPTORPROTO



class EnumDescriptorProto(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ENUMDESCRIPTORPROTO



class EnumValueDescriptorProto(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ENUMVALUEDESCRIPTORPROTO



class ServiceDescriptorProto(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _SERVICEDESCRIPTORPROTO



class MethodDescriptorProto(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _METHODDESCRIPTORPROTO



class StreamDescriptorProto(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _STREAMDESCRIPTORPROTO



class FileOptions(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _FILEOPTIONS



class MessageOptions(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _MESSAGEOPTIONS



class FieldOptions(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType

  class UpgradedOption(_message.Message):
    __metaclass__ = _reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _FIELDOPTIONS_UPGRADEDOPTION


  DESCRIPTOR = _FIELDOPTIONS



class EnumOptions(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ENUMOPTIONS



class EnumValueOptions(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ENUMVALUEOPTIONS



class ServiceOptions(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _SERVICEOPTIONS



class MethodOptions(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _METHODOPTIONS



class StreamOptions(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _STREAMOPTIONS



class UninterpretedOption(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType

  class NamePart(_message.Message):
    __metaclass__ = _reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _UNINTERPRETEDOPTION_NAMEPART


  DESCRIPTOR = _UNINTERPRETEDOPTION



class SourceCodeInfo(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType

  class Location(_message.Message):
    __metaclass__ = _reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _SOURCECODEINFO_LOCATION


  DESCRIPTOR = _SOURCECODEINFO





