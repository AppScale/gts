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



from google.net.proto import ProtocolBuffer
import array
import dummy_thread as thread

__pychecker__ = """maxreturns=0 maxbranches=0 no-callinit
                   unusednames=printElemNumber,debug_strs no-special"""

if hasattr(ProtocolBuffer, 'ExtendableProtocolMessage'):
  _extension_runtime = True
  _ExtendableProtocolMessage = ProtocolBuffer.ExtendableProtocolMessage
else:
  _extension_runtime = False
  _ExtendableProtocolMessage = ProtocolBuffer.ProtocolMessage

class AggregateRpcStatsProto(ProtocolBuffer.ProtocolMessage):
  has_service_call_name_ = 0
  service_call_name_ = ""
  has_total_amount_of_calls_ = 0
  total_amount_of_calls_ = 0

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def service_call_name(self): return self.service_call_name_

  def set_service_call_name(self, x):
    self.has_service_call_name_ = 1
    self.service_call_name_ = x

  def clear_service_call_name(self):
    if self.has_service_call_name_:
      self.has_service_call_name_ = 0
      self.service_call_name_ = ""

  def has_service_call_name(self): return self.has_service_call_name_

  def total_amount_of_calls(self): return self.total_amount_of_calls_

  def set_total_amount_of_calls(self, x):
    self.has_total_amount_of_calls_ = 1
    self.total_amount_of_calls_ = x

  def clear_total_amount_of_calls(self):
    if self.has_total_amount_of_calls_:
      self.has_total_amount_of_calls_ = 0
      self.total_amount_of_calls_ = 0

  def has_total_amount_of_calls(self): return self.has_total_amount_of_calls_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_service_call_name()): self.set_service_call_name(x.service_call_name())
    if (x.has_total_amount_of_calls()): self.set_total_amount_of_calls(x.total_amount_of_calls())

  def Equals(self, x):
    if x is self: return 1
    if self.has_service_call_name_ != x.has_service_call_name_: return 0
    if self.has_service_call_name_ and self.service_call_name_ != x.service_call_name_: return 0
    if self.has_total_amount_of_calls_ != x.has_total_amount_of_calls_: return 0
    if self.has_total_amount_of_calls_ and self.total_amount_of_calls_ != x.total_amount_of_calls_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_service_call_name_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: service_call_name not set.')
    if (not self.has_total_amount_of_calls_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: total_amount_of_calls not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.service_call_name_))
    n += self.lengthVarInt64(self.total_amount_of_calls_)
    return n + 2

  def ByteSizePartial(self):
    n = 0
    if (self.has_service_call_name_):
      n += 1
      n += self.lengthString(len(self.service_call_name_))
    if (self.has_total_amount_of_calls_):
      n += 1
      n += self.lengthVarInt64(self.total_amount_of_calls_)
    return n

  def Clear(self):
    self.clear_service_call_name()
    self.clear_total_amount_of_calls()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.service_call_name_)
    out.putVarInt32(24)
    out.putVarInt64(self.total_amount_of_calls_)

  def OutputPartial(self, out):
    if (self.has_service_call_name_):
      out.putVarInt32(10)
      out.putPrefixedString(self.service_call_name_)
    if (self.has_total_amount_of_calls_):
      out.putVarInt32(24)
      out.putVarInt64(self.total_amount_of_calls_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_service_call_name(d.getPrefixedString())
        continue
      if tt == 24:
        self.set_total_amount_of_calls(d.getVarInt64())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_service_call_name_: res+=prefix+("service_call_name: %s\n" % self.DebugFormatString(self.service_call_name_))
    if self.has_total_amount_of_calls_: res+=prefix+("total_amount_of_calls: %s\n" % self.DebugFormatInt64(self.total_amount_of_calls_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kservice_call_name = 1
  ktotal_amount_of_calls = 3

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "service_call_name",
    3: "total_amount_of_calls",
  }, 3)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    3: ProtocolBuffer.Encoder.NUMERIC,
  }, 3, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _PROTO_DESCRIPTOR_NAME = 'apphosting.AggregateRpcStatsProto'
class KeyValProto(ProtocolBuffer.ProtocolMessage):
  has_key_ = 0
  key_ = ""
  has_value_ = 0
  value_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def key(self): return self.key_

  def set_key(self, x):
    self.has_key_ = 1
    self.key_ = x

  def clear_key(self):
    if self.has_key_:
      self.has_key_ = 0
      self.key_ = ""

  def has_key(self): return self.has_key_

  def value(self): return self.value_

  def set_value(self, x):
    self.has_value_ = 1
    self.value_ = x

  def clear_value(self):
    if self.has_value_:
      self.has_value_ = 0
      self.value_ = ""

  def has_value(self): return self.has_value_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_key()): self.set_key(x.key())
    if (x.has_value()): self.set_value(x.value())

  def Equals(self, x):
    if x is self: return 1
    if self.has_key_ != x.has_key_: return 0
    if self.has_key_ and self.key_ != x.key_: return 0
    if self.has_value_ != x.has_value_: return 0
    if self.has_value_ and self.value_ != x.value_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_key_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: key not set.')
    if (not self.has_value_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: value not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.key_))
    n += self.lengthString(len(self.value_))
    return n + 2

  def ByteSizePartial(self):
    n = 0
    if (self.has_key_):
      n += 1
      n += self.lengthString(len(self.key_))
    if (self.has_value_):
      n += 1
      n += self.lengthString(len(self.value_))
    return n

  def Clear(self):
    self.clear_key()
    self.clear_value()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.key_)
    out.putVarInt32(18)
    out.putPrefixedString(self.value_)

  def OutputPartial(self, out):
    if (self.has_key_):
      out.putVarInt32(10)
      out.putPrefixedString(self.key_)
    if (self.has_value_):
      out.putVarInt32(18)
      out.putPrefixedString(self.value_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_key(d.getPrefixedString())
        continue
      if tt == 18:
        self.set_value(d.getPrefixedString())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_key_: res+=prefix+("key: %s\n" % self.DebugFormatString(self.key_))
    if self.has_value_: res+=prefix+("value: %s\n" % self.DebugFormatString(self.value_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kkey = 1
  kvalue = 2

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "key",
    2: "value",
  }, 2)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.STRING,
  }, 2, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _PROTO_DESCRIPTOR_NAME = 'apphosting.KeyValProto'
class StackFrameProto(ProtocolBuffer.ProtocolMessage):
  has_class_or_file_name_ = 0
  class_or_file_name_ = ""
  has_line_number_ = 0
  line_number_ = 0
  has_function_name_ = 0
  function_name_ = ""

  def __init__(self, contents=None):
    self.variables_ = []
    if contents is not None: self.MergeFromString(contents)

  def class_or_file_name(self): return self.class_or_file_name_

  def set_class_or_file_name(self, x):
    self.has_class_or_file_name_ = 1
    self.class_or_file_name_ = x

  def clear_class_or_file_name(self):
    if self.has_class_or_file_name_:
      self.has_class_or_file_name_ = 0
      self.class_or_file_name_ = ""

  def has_class_or_file_name(self): return self.has_class_or_file_name_

  def line_number(self): return self.line_number_

  def set_line_number(self, x):
    self.has_line_number_ = 1
    self.line_number_ = x

  def clear_line_number(self):
    if self.has_line_number_:
      self.has_line_number_ = 0
      self.line_number_ = 0

  def has_line_number(self): return self.has_line_number_

  def function_name(self): return self.function_name_

  def set_function_name(self, x):
    self.has_function_name_ = 1
    self.function_name_ = x

  def clear_function_name(self):
    if self.has_function_name_:
      self.has_function_name_ = 0
      self.function_name_ = ""

  def has_function_name(self): return self.has_function_name_

  def variables_size(self): return len(self.variables_)
  def variables_list(self): return self.variables_

  def variables(self, i):
    return self.variables_[i]

  def mutable_variables(self, i):
    return self.variables_[i]

  def add_variables(self):
    x = KeyValProto()
    self.variables_.append(x)
    return x

  def clear_variables(self):
    self.variables_ = []

  def MergeFrom(self, x):
    assert x is not self
    if (x.has_class_or_file_name()): self.set_class_or_file_name(x.class_or_file_name())
    if (x.has_line_number()): self.set_line_number(x.line_number())
    if (x.has_function_name()): self.set_function_name(x.function_name())
    for i in xrange(x.variables_size()): self.add_variables().CopyFrom(x.variables(i))

  def Equals(self, x):
    if x is self: return 1
    if self.has_class_or_file_name_ != x.has_class_or_file_name_: return 0
    if self.has_class_or_file_name_ and self.class_or_file_name_ != x.class_or_file_name_: return 0
    if self.has_line_number_ != x.has_line_number_: return 0
    if self.has_line_number_ and self.line_number_ != x.line_number_: return 0
    if self.has_function_name_ != x.has_function_name_: return 0
    if self.has_function_name_ and self.function_name_ != x.function_name_: return 0
    if len(self.variables_) != len(x.variables_): return 0
    for e1, e2 in zip(self.variables_, x.variables_):
      if e1 != e2: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_class_or_file_name_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: class_or_file_name not set.')
    if (not self.has_function_name_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: function_name not set.')
    for p in self.variables_:
      if not p.IsInitialized(debug_strs): initialized=0
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.class_or_file_name_))
    if (self.has_line_number_): n += 1 + self.lengthVarInt64(self.line_number_)
    n += self.lengthString(len(self.function_name_))
    n += 1 * len(self.variables_)
    for i in xrange(len(self.variables_)): n += self.lengthString(self.variables_[i].ByteSize())
    return n + 2

  def ByteSizePartial(self):
    n = 0
    if (self.has_class_or_file_name_):
      n += 1
      n += self.lengthString(len(self.class_or_file_name_))
    if (self.has_line_number_): n += 1 + self.lengthVarInt64(self.line_number_)
    if (self.has_function_name_):
      n += 1
      n += self.lengthString(len(self.function_name_))
    n += 1 * len(self.variables_)
    for i in xrange(len(self.variables_)): n += self.lengthString(self.variables_[i].ByteSizePartial())
    return n

  def Clear(self):
    self.clear_class_or_file_name()
    self.clear_line_number()
    self.clear_function_name()
    self.clear_variables()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.class_or_file_name_)
    if (self.has_line_number_):
      out.putVarInt32(16)
      out.putVarInt32(self.line_number_)
    out.putVarInt32(26)
    out.putPrefixedString(self.function_name_)
    for i in xrange(len(self.variables_)):
      out.putVarInt32(34)
      out.putVarInt32(self.variables_[i].ByteSize())
      self.variables_[i].OutputUnchecked(out)

  def OutputPartial(self, out):
    if (self.has_class_or_file_name_):
      out.putVarInt32(10)
      out.putPrefixedString(self.class_or_file_name_)
    if (self.has_line_number_):
      out.putVarInt32(16)
      out.putVarInt32(self.line_number_)
    if (self.has_function_name_):
      out.putVarInt32(26)
      out.putPrefixedString(self.function_name_)
    for i in xrange(len(self.variables_)):
      out.putVarInt32(34)
      out.putVarInt32(self.variables_[i].ByteSizePartial())
      self.variables_[i].OutputPartial(out)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_class_or_file_name(d.getPrefixedString())
        continue
      if tt == 16:
        self.set_line_number(d.getVarInt32())
        continue
      if tt == 26:
        self.set_function_name(d.getPrefixedString())
        continue
      if tt == 34:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.add_variables().TryMerge(tmp)
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_class_or_file_name_: res+=prefix+("class_or_file_name: %s\n" % self.DebugFormatString(self.class_or_file_name_))
    if self.has_line_number_: res+=prefix+("line_number: %s\n" % self.DebugFormatInt32(self.line_number_))
    if self.has_function_name_: res+=prefix+("function_name: %s\n" % self.DebugFormatString(self.function_name_))
    cnt=0
    for e in self.variables_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("variables%s <\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
      cnt+=1
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kclass_or_file_name = 1
  kline_number = 2
  kfunction_name = 3
  kvariables = 4

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "class_or_file_name",
    2: "line_number",
    3: "function_name",
    4: "variables",
  }, 4)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.NUMERIC,
    3: ProtocolBuffer.Encoder.STRING,
    4: ProtocolBuffer.Encoder.STRING,
  }, 4, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _PROTO_DESCRIPTOR_NAME = 'apphosting.StackFrameProto'
class IndividualRpcStatsProto(ProtocolBuffer.ProtocolMessage):
  has_service_call_name_ = 0
  service_call_name_ = ""
  has_request_data_summary_ = 0
  request_data_summary_ = ""
  has_response_data_summary_ = 0
  response_data_summary_ = ""
  has_api_mcycles_ = 0
  api_mcycles_ = 0
  has_start_offset_milliseconds_ = 0
  start_offset_milliseconds_ = 0
  has_duration_milliseconds_ = 0
  duration_milliseconds_ = 0
  has_namespace_ = 0
  namespace_ = ""
  has_was_successful_ = 0
  was_successful_ = 1

  def __init__(self, contents=None):
    self.call_stack_ = []
    if contents is not None: self.MergeFromString(contents)

  def service_call_name(self): return self.service_call_name_

  def set_service_call_name(self, x):
    self.has_service_call_name_ = 1
    self.service_call_name_ = x

  def clear_service_call_name(self):
    if self.has_service_call_name_:
      self.has_service_call_name_ = 0
      self.service_call_name_ = ""

  def has_service_call_name(self): return self.has_service_call_name_

  def request_data_summary(self): return self.request_data_summary_

  def set_request_data_summary(self, x):
    self.has_request_data_summary_ = 1
    self.request_data_summary_ = x

  def clear_request_data_summary(self):
    if self.has_request_data_summary_:
      self.has_request_data_summary_ = 0
      self.request_data_summary_ = ""

  def has_request_data_summary(self): return self.has_request_data_summary_

  def response_data_summary(self): return self.response_data_summary_

  def set_response_data_summary(self, x):
    self.has_response_data_summary_ = 1
    self.response_data_summary_ = x

  def clear_response_data_summary(self):
    if self.has_response_data_summary_:
      self.has_response_data_summary_ = 0
      self.response_data_summary_ = ""

  def has_response_data_summary(self): return self.has_response_data_summary_

  def api_mcycles(self): return self.api_mcycles_

  def set_api_mcycles(self, x):
    self.has_api_mcycles_ = 1
    self.api_mcycles_ = x

  def clear_api_mcycles(self):
    if self.has_api_mcycles_:
      self.has_api_mcycles_ = 0
      self.api_mcycles_ = 0

  def has_api_mcycles(self): return self.has_api_mcycles_

  def start_offset_milliseconds(self): return self.start_offset_milliseconds_

  def set_start_offset_milliseconds(self, x):
    self.has_start_offset_milliseconds_ = 1
    self.start_offset_milliseconds_ = x

  def clear_start_offset_milliseconds(self):
    if self.has_start_offset_milliseconds_:
      self.has_start_offset_milliseconds_ = 0
      self.start_offset_milliseconds_ = 0

  def has_start_offset_milliseconds(self): return self.has_start_offset_milliseconds_

  def duration_milliseconds(self): return self.duration_milliseconds_

  def set_duration_milliseconds(self, x):
    self.has_duration_milliseconds_ = 1
    self.duration_milliseconds_ = x

  def clear_duration_milliseconds(self):
    if self.has_duration_milliseconds_:
      self.has_duration_milliseconds_ = 0
      self.duration_milliseconds_ = 0

  def has_duration_milliseconds(self): return self.has_duration_milliseconds_

  def namespace(self): return self.namespace_

  def set_namespace(self, x):
    self.has_namespace_ = 1
    self.namespace_ = x

  def clear_namespace(self):
    if self.has_namespace_:
      self.has_namespace_ = 0
      self.namespace_ = ""

  def has_namespace(self): return self.has_namespace_

  def was_successful(self): return self.was_successful_

  def set_was_successful(self, x):
    self.has_was_successful_ = 1
    self.was_successful_ = x

  def clear_was_successful(self):
    if self.has_was_successful_:
      self.has_was_successful_ = 0
      self.was_successful_ = 1

  def has_was_successful(self): return self.has_was_successful_

  def call_stack_size(self): return len(self.call_stack_)
  def call_stack_list(self): return self.call_stack_

  def call_stack(self, i):
    return self.call_stack_[i]

  def mutable_call_stack(self, i):
    return self.call_stack_[i]

  def add_call_stack(self):
    x = StackFrameProto()
    self.call_stack_.append(x)
    return x

  def clear_call_stack(self):
    self.call_stack_ = []

  def MergeFrom(self, x):
    assert x is not self
    if (x.has_service_call_name()): self.set_service_call_name(x.service_call_name())
    if (x.has_request_data_summary()): self.set_request_data_summary(x.request_data_summary())
    if (x.has_response_data_summary()): self.set_response_data_summary(x.response_data_summary())
    if (x.has_api_mcycles()): self.set_api_mcycles(x.api_mcycles())
    if (x.has_start_offset_milliseconds()): self.set_start_offset_milliseconds(x.start_offset_milliseconds())
    if (x.has_duration_milliseconds()): self.set_duration_milliseconds(x.duration_milliseconds())
    if (x.has_namespace()): self.set_namespace(x.namespace())
    if (x.has_was_successful()): self.set_was_successful(x.was_successful())
    for i in xrange(x.call_stack_size()): self.add_call_stack().CopyFrom(x.call_stack(i))

  def Equals(self, x):
    if x is self: return 1
    if self.has_service_call_name_ != x.has_service_call_name_: return 0
    if self.has_service_call_name_ and self.service_call_name_ != x.service_call_name_: return 0
    if self.has_request_data_summary_ != x.has_request_data_summary_: return 0
    if self.has_request_data_summary_ and self.request_data_summary_ != x.request_data_summary_: return 0
    if self.has_response_data_summary_ != x.has_response_data_summary_: return 0
    if self.has_response_data_summary_ and self.response_data_summary_ != x.response_data_summary_: return 0
    if self.has_api_mcycles_ != x.has_api_mcycles_: return 0
    if self.has_api_mcycles_ and self.api_mcycles_ != x.api_mcycles_: return 0
    if self.has_start_offset_milliseconds_ != x.has_start_offset_milliseconds_: return 0
    if self.has_start_offset_milliseconds_ and self.start_offset_milliseconds_ != x.start_offset_milliseconds_: return 0
    if self.has_duration_milliseconds_ != x.has_duration_milliseconds_: return 0
    if self.has_duration_milliseconds_ and self.duration_milliseconds_ != x.duration_milliseconds_: return 0
    if self.has_namespace_ != x.has_namespace_: return 0
    if self.has_namespace_ and self.namespace_ != x.namespace_: return 0
    if self.has_was_successful_ != x.has_was_successful_: return 0
    if self.has_was_successful_ and self.was_successful_ != x.was_successful_: return 0
    if len(self.call_stack_) != len(x.call_stack_): return 0
    for e1, e2 in zip(self.call_stack_, x.call_stack_):
      if e1 != e2: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_service_call_name_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: service_call_name not set.')
    if (not self.has_start_offset_milliseconds_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: start_offset_milliseconds not set.')
    for p in self.call_stack_:
      if not p.IsInitialized(debug_strs): initialized=0
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.service_call_name_))
    if (self.has_request_data_summary_): n += 1 + self.lengthString(len(self.request_data_summary_))
    if (self.has_response_data_summary_): n += 1 + self.lengthString(len(self.response_data_summary_))
    if (self.has_api_mcycles_): n += 1 + self.lengthVarInt64(self.api_mcycles_)
    n += self.lengthVarInt64(self.start_offset_milliseconds_)
    if (self.has_duration_milliseconds_): n += 1 + self.lengthVarInt64(self.duration_milliseconds_)
    if (self.has_namespace_): n += 1 + self.lengthString(len(self.namespace_))
    if (self.has_was_successful_): n += 2
    n += 1 * len(self.call_stack_)
    for i in xrange(len(self.call_stack_)): n += self.lengthString(self.call_stack_[i].ByteSize())
    return n + 2

  def ByteSizePartial(self):
    n = 0
    if (self.has_service_call_name_):
      n += 1
      n += self.lengthString(len(self.service_call_name_))
    if (self.has_request_data_summary_): n += 1 + self.lengthString(len(self.request_data_summary_))
    if (self.has_response_data_summary_): n += 1 + self.lengthString(len(self.response_data_summary_))
    if (self.has_api_mcycles_): n += 1 + self.lengthVarInt64(self.api_mcycles_)
    if (self.has_start_offset_milliseconds_):
      n += 1
      n += self.lengthVarInt64(self.start_offset_milliseconds_)
    if (self.has_duration_milliseconds_): n += 1 + self.lengthVarInt64(self.duration_milliseconds_)
    if (self.has_namespace_): n += 1 + self.lengthString(len(self.namespace_))
    if (self.has_was_successful_): n += 2
    n += 1 * len(self.call_stack_)
    for i in xrange(len(self.call_stack_)): n += self.lengthString(self.call_stack_[i].ByteSizePartial())
    return n

  def Clear(self):
    self.clear_service_call_name()
    self.clear_request_data_summary()
    self.clear_response_data_summary()
    self.clear_api_mcycles()
    self.clear_start_offset_milliseconds()
    self.clear_duration_milliseconds()
    self.clear_namespace()
    self.clear_was_successful()
    self.clear_call_stack()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.service_call_name_)
    if (self.has_request_data_summary_):
      out.putVarInt32(26)
      out.putPrefixedString(self.request_data_summary_)
    if (self.has_response_data_summary_):
      out.putVarInt32(34)
      out.putPrefixedString(self.response_data_summary_)
    if (self.has_api_mcycles_):
      out.putVarInt32(40)
      out.putVarInt64(self.api_mcycles_)
    out.putVarInt32(48)
    out.putVarInt64(self.start_offset_milliseconds_)
    if (self.has_duration_milliseconds_):
      out.putVarInt32(56)
      out.putVarInt64(self.duration_milliseconds_)
    if (self.has_namespace_):
      out.putVarInt32(66)
      out.putPrefixedString(self.namespace_)
    if (self.has_was_successful_):
      out.putVarInt32(72)
      out.putBoolean(self.was_successful_)
    for i in xrange(len(self.call_stack_)):
      out.putVarInt32(82)
      out.putVarInt32(self.call_stack_[i].ByteSize())
      self.call_stack_[i].OutputUnchecked(out)

  def OutputPartial(self, out):
    if (self.has_service_call_name_):
      out.putVarInt32(10)
      out.putPrefixedString(self.service_call_name_)
    if (self.has_request_data_summary_):
      out.putVarInt32(26)
      out.putPrefixedString(self.request_data_summary_)
    if (self.has_response_data_summary_):
      out.putVarInt32(34)
      out.putPrefixedString(self.response_data_summary_)
    if (self.has_api_mcycles_):
      out.putVarInt32(40)
      out.putVarInt64(self.api_mcycles_)
    if (self.has_start_offset_milliseconds_):
      out.putVarInt32(48)
      out.putVarInt64(self.start_offset_milliseconds_)
    if (self.has_duration_milliseconds_):
      out.putVarInt32(56)
      out.putVarInt64(self.duration_milliseconds_)
    if (self.has_namespace_):
      out.putVarInt32(66)
      out.putPrefixedString(self.namespace_)
    if (self.has_was_successful_):
      out.putVarInt32(72)
      out.putBoolean(self.was_successful_)
    for i in xrange(len(self.call_stack_)):
      out.putVarInt32(82)
      out.putVarInt32(self.call_stack_[i].ByteSizePartial())
      self.call_stack_[i].OutputPartial(out)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_service_call_name(d.getPrefixedString())
        continue
      if tt == 26:
        self.set_request_data_summary(d.getPrefixedString())
        continue
      if tt == 34:
        self.set_response_data_summary(d.getPrefixedString())
        continue
      if tt == 40:
        self.set_api_mcycles(d.getVarInt64())
        continue
      if tt == 48:
        self.set_start_offset_milliseconds(d.getVarInt64())
        continue
      if tt == 56:
        self.set_duration_milliseconds(d.getVarInt64())
        continue
      if tt == 66:
        self.set_namespace(d.getPrefixedString())
        continue
      if tt == 72:
        self.set_was_successful(d.getBoolean())
        continue
      if tt == 82:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.add_call_stack().TryMerge(tmp)
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_service_call_name_: res+=prefix+("service_call_name: %s\n" % self.DebugFormatString(self.service_call_name_))
    if self.has_request_data_summary_: res+=prefix+("request_data_summary: %s\n" % self.DebugFormatString(self.request_data_summary_))
    if self.has_response_data_summary_: res+=prefix+("response_data_summary: %s\n" % self.DebugFormatString(self.response_data_summary_))
    if self.has_api_mcycles_: res+=prefix+("api_mcycles: %s\n" % self.DebugFormatInt64(self.api_mcycles_))
    if self.has_start_offset_milliseconds_: res+=prefix+("start_offset_milliseconds: %s\n" % self.DebugFormatInt64(self.start_offset_milliseconds_))
    if self.has_duration_milliseconds_: res+=prefix+("duration_milliseconds: %s\n" % self.DebugFormatInt64(self.duration_milliseconds_))
    if self.has_namespace_: res+=prefix+("namespace: %s\n" % self.DebugFormatString(self.namespace_))
    if self.has_was_successful_: res+=prefix+("was_successful: %s\n" % self.DebugFormatBool(self.was_successful_))
    cnt=0
    for e in self.call_stack_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("call_stack%s <\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
      cnt+=1
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kservice_call_name = 1
  krequest_data_summary = 3
  kresponse_data_summary = 4
  kapi_mcycles = 5
  kstart_offset_milliseconds = 6
  kduration_milliseconds = 7
  knamespace = 8
  kwas_successful = 9
  kcall_stack = 10

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "service_call_name",
    3: "request_data_summary",
    4: "response_data_summary",
    5: "api_mcycles",
    6: "start_offset_milliseconds",
    7: "duration_milliseconds",
    8: "namespace",
    9: "was_successful",
    10: "call_stack",
  }, 10)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    3: ProtocolBuffer.Encoder.STRING,
    4: ProtocolBuffer.Encoder.STRING,
    5: ProtocolBuffer.Encoder.NUMERIC,
    6: ProtocolBuffer.Encoder.NUMERIC,
    7: ProtocolBuffer.Encoder.NUMERIC,
    8: ProtocolBuffer.Encoder.STRING,
    9: ProtocolBuffer.Encoder.NUMERIC,
    10: ProtocolBuffer.Encoder.STRING,
  }, 10, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _PROTO_DESCRIPTOR_NAME = 'apphosting.IndividualRpcStatsProto'
class RequestStatProto(ProtocolBuffer.ProtocolMessage):
  has_start_timestamp_milliseconds_ = 0
  start_timestamp_milliseconds_ = 0
  has_http_method_ = 0
  http_method_ = "GET"
  has_http_path_ = 0
  http_path_ = "/"
  has_http_query_ = 0
  http_query_ = ""
  has_http_status_ = 0
  http_status_ = 200
  has_duration_milliseconds_ = 0
  duration_milliseconds_ = 0
  has_api_mcycles_ = 0
  api_mcycles_ = 0
  has_processor_mcycles_ = 0
  processor_mcycles_ = 0
  has_overhead_walltime_milliseconds_ = 0
  overhead_walltime_milliseconds_ = 0
  has_user_email_ = 0
  user_email_ = ""
  has_is_admin_ = 0
  is_admin_ = 0

  def __init__(self, contents=None):
    self.rpc_stats_ = []
    self.cgi_env_ = []
    self.individual_stats_ = []
    if contents is not None: self.MergeFromString(contents)

  def start_timestamp_milliseconds(self): return self.start_timestamp_milliseconds_

  def set_start_timestamp_milliseconds(self, x):
    self.has_start_timestamp_milliseconds_ = 1
    self.start_timestamp_milliseconds_ = x

  def clear_start_timestamp_milliseconds(self):
    if self.has_start_timestamp_milliseconds_:
      self.has_start_timestamp_milliseconds_ = 0
      self.start_timestamp_milliseconds_ = 0

  def has_start_timestamp_milliseconds(self): return self.has_start_timestamp_milliseconds_

  def http_method(self): return self.http_method_

  def set_http_method(self, x):
    self.has_http_method_ = 1
    self.http_method_ = x

  def clear_http_method(self):
    if self.has_http_method_:
      self.has_http_method_ = 0
      self.http_method_ = "GET"

  def has_http_method(self): return self.has_http_method_

  def http_path(self): return self.http_path_

  def set_http_path(self, x):
    self.has_http_path_ = 1
    self.http_path_ = x

  def clear_http_path(self):
    if self.has_http_path_:
      self.has_http_path_ = 0
      self.http_path_ = "/"

  def has_http_path(self): return self.has_http_path_

  def http_query(self): return self.http_query_

  def set_http_query(self, x):
    self.has_http_query_ = 1
    self.http_query_ = x

  def clear_http_query(self):
    if self.has_http_query_:
      self.has_http_query_ = 0
      self.http_query_ = ""

  def has_http_query(self): return self.has_http_query_

  def http_status(self): return self.http_status_

  def set_http_status(self, x):
    self.has_http_status_ = 1
    self.http_status_ = x

  def clear_http_status(self):
    if self.has_http_status_:
      self.has_http_status_ = 0
      self.http_status_ = 200

  def has_http_status(self): return self.has_http_status_

  def duration_milliseconds(self): return self.duration_milliseconds_

  def set_duration_milliseconds(self, x):
    self.has_duration_milliseconds_ = 1
    self.duration_milliseconds_ = x

  def clear_duration_milliseconds(self):
    if self.has_duration_milliseconds_:
      self.has_duration_milliseconds_ = 0
      self.duration_milliseconds_ = 0

  def has_duration_milliseconds(self): return self.has_duration_milliseconds_

  def api_mcycles(self): return self.api_mcycles_

  def set_api_mcycles(self, x):
    self.has_api_mcycles_ = 1
    self.api_mcycles_ = x

  def clear_api_mcycles(self):
    if self.has_api_mcycles_:
      self.has_api_mcycles_ = 0
      self.api_mcycles_ = 0

  def has_api_mcycles(self): return self.has_api_mcycles_

  def processor_mcycles(self): return self.processor_mcycles_

  def set_processor_mcycles(self, x):
    self.has_processor_mcycles_ = 1
    self.processor_mcycles_ = x

  def clear_processor_mcycles(self):
    if self.has_processor_mcycles_:
      self.has_processor_mcycles_ = 0
      self.processor_mcycles_ = 0

  def has_processor_mcycles(self): return self.has_processor_mcycles_

  def rpc_stats_size(self): return len(self.rpc_stats_)
  def rpc_stats_list(self): return self.rpc_stats_

  def rpc_stats(self, i):
    return self.rpc_stats_[i]

  def mutable_rpc_stats(self, i):
    return self.rpc_stats_[i]

  def add_rpc_stats(self):
    x = AggregateRpcStatsProto()
    self.rpc_stats_.append(x)
    return x

  def clear_rpc_stats(self):
    self.rpc_stats_ = []
  def cgi_env_size(self): return len(self.cgi_env_)
  def cgi_env_list(self): return self.cgi_env_

  def cgi_env(self, i):
    return self.cgi_env_[i]

  def mutable_cgi_env(self, i):
    return self.cgi_env_[i]

  def add_cgi_env(self):
    x = KeyValProto()
    self.cgi_env_.append(x)
    return x

  def clear_cgi_env(self):
    self.cgi_env_ = []
  def overhead_walltime_milliseconds(self): return self.overhead_walltime_milliseconds_

  def set_overhead_walltime_milliseconds(self, x):
    self.has_overhead_walltime_milliseconds_ = 1
    self.overhead_walltime_milliseconds_ = x

  def clear_overhead_walltime_milliseconds(self):
    if self.has_overhead_walltime_milliseconds_:
      self.has_overhead_walltime_milliseconds_ = 0
      self.overhead_walltime_milliseconds_ = 0

  def has_overhead_walltime_milliseconds(self): return self.has_overhead_walltime_milliseconds_

  def user_email(self): return self.user_email_

  def set_user_email(self, x):
    self.has_user_email_ = 1
    self.user_email_ = x

  def clear_user_email(self):
    if self.has_user_email_:
      self.has_user_email_ = 0
      self.user_email_ = ""

  def has_user_email(self): return self.has_user_email_

  def is_admin(self): return self.is_admin_

  def set_is_admin(self, x):
    self.has_is_admin_ = 1
    self.is_admin_ = x

  def clear_is_admin(self):
    if self.has_is_admin_:
      self.has_is_admin_ = 0
      self.is_admin_ = 0

  def has_is_admin(self): return self.has_is_admin_

  def individual_stats_size(self): return len(self.individual_stats_)
  def individual_stats_list(self): return self.individual_stats_

  def individual_stats(self, i):
    return self.individual_stats_[i]

  def mutable_individual_stats(self, i):
    return self.individual_stats_[i]

  def add_individual_stats(self):
    x = IndividualRpcStatsProto()
    self.individual_stats_.append(x)
    return x

  def clear_individual_stats(self):
    self.individual_stats_ = []

  def MergeFrom(self, x):
    assert x is not self
    if (x.has_start_timestamp_milliseconds()): self.set_start_timestamp_milliseconds(x.start_timestamp_milliseconds())
    if (x.has_http_method()): self.set_http_method(x.http_method())
    if (x.has_http_path()): self.set_http_path(x.http_path())
    if (x.has_http_query()): self.set_http_query(x.http_query())
    if (x.has_http_status()): self.set_http_status(x.http_status())
    if (x.has_duration_milliseconds()): self.set_duration_milliseconds(x.duration_milliseconds())
    if (x.has_api_mcycles()): self.set_api_mcycles(x.api_mcycles())
    if (x.has_processor_mcycles()): self.set_processor_mcycles(x.processor_mcycles())
    for i in xrange(x.rpc_stats_size()): self.add_rpc_stats().CopyFrom(x.rpc_stats(i))
    for i in xrange(x.cgi_env_size()): self.add_cgi_env().CopyFrom(x.cgi_env(i))
    if (x.has_overhead_walltime_milliseconds()): self.set_overhead_walltime_milliseconds(x.overhead_walltime_milliseconds())
    if (x.has_user_email()): self.set_user_email(x.user_email())
    if (x.has_is_admin()): self.set_is_admin(x.is_admin())
    for i in xrange(x.individual_stats_size()): self.add_individual_stats().CopyFrom(x.individual_stats(i))

  def Equals(self, x):
    if x is self: return 1
    if self.has_start_timestamp_milliseconds_ != x.has_start_timestamp_milliseconds_: return 0
    if self.has_start_timestamp_milliseconds_ and self.start_timestamp_milliseconds_ != x.start_timestamp_milliseconds_: return 0
    if self.has_http_method_ != x.has_http_method_: return 0
    if self.has_http_method_ and self.http_method_ != x.http_method_: return 0
    if self.has_http_path_ != x.has_http_path_: return 0
    if self.has_http_path_ and self.http_path_ != x.http_path_: return 0
    if self.has_http_query_ != x.has_http_query_: return 0
    if self.has_http_query_ and self.http_query_ != x.http_query_: return 0
    if self.has_http_status_ != x.has_http_status_: return 0
    if self.has_http_status_ and self.http_status_ != x.http_status_: return 0
    if self.has_duration_milliseconds_ != x.has_duration_milliseconds_: return 0
    if self.has_duration_milliseconds_ and self.duration_milliseconds_ != x.duration_milliseconds_: return 0
    if self.has_api_mcycles_ != x.has_api_mcycles_: return 0
    if self.has_api_mcycles_ and self.api_mcycles_ != x.api_mcycles_: return 0
    if self.has_processor_mcycles_ != x.has_processor_mcycles_: return 0
    if self.has_processor_mcycles_ and self.processor_mcycles_ != x.processor_mcycles_: return 0
    if len(self.rpc_stats_) != len(x.rpc_stats_): return 0
    for e1, e2 in zip(self.rpc_stats_, x.rpc_stats_):
      if e1 != e2: return 0
    if len(self.cgi_env_) != len(x.cgi_env_): return 0
    for e1, e2 in zip(self.cgi_env_, x.cgi_env_):
      if e1 != e2: return 0
    if self.has_overhead_walltime_milliseconds_ != x.has_overhead_walltime_milliseconds_: return 0
    if self.has_overhead_walltime_milliseconds_ and self.overhead_walltime_milliseconds_ != x.overhead_walltime_milliseconds_: return 0
    if self.has_user_email_ != x.has_user_email_: return 0
    if self.has_user_email_ and self.user_email_ != x.user_email_: return 0
    if self.has_is_admin_ != x.has_is_admin_: return 0
    if self.has_is_admin_ and self.is_admin_ != x.is_admin_: return 0
    if len(self.individual_stats_) != len(x.individual_stats_): return 0
    for e1, e2 in zip(self.individual_stats_, x.individual_stats_):
      if e1 != e2: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_start_timestamp_milliseconds_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: start_timestamp_milliseconds not set.')
    if (not self.has_duration_milliseconds_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: duration_milliseconds not set.')
    for p in self.rpc_stats_:
      if not p.IsInitialized(debug_strs): initialized=0
    for p in self.cgi_env_:
      if not p.IsInitialized(debug_strs): initialized=0
    for p in self.individual_stats_:
      if not p.IsInitialized(debug_strs): initialized=0
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthVarInt64(self.start_timestamp_milliseconds_)
    if (self.has_http_method_): n += 1 + self.lengthString(len(self.http_method_))
    if (self.has_http_path_): n += 1 + self.lengthString(len(self.http_path_))
    if (self.has_http_query_): n += 1 + self.lengthString(len(self.http_query_))
    if (self.has_http_status_): n += 1 + self.lengthVarInt64(self.http_status_)
    n += self.lengthVarInt64(self.duration_milliseconds_)
    if (self.has_api_mcycles_): n += 1 + self.lengthVarInt64(self.api_mcycles_)
    if (self.has_processor_mcycles_): n += 1 + self.lengthVarInt64(self.processor_mcycles_)
    n += 1 * len(self.rpc_stats_)
    for i in xrange(len(self.rpc_stats_)): n += self.lengthString(self.rpc_stats_[i].ByteSize())
    n += 2 * len(self.cgi_env_)
    for i in xrange(len(self.cgi_env_)): n += self.lengthString(self.cgi_env_[i].ByteSize())
    if (self.has_overhead_walltime_milliseconds_): n += 2 + self.lengthVarInt64(self.overhead_walltime_milliseconds_)
    if (self.has_user_email_): n += 2 + self.lengthString(len(self.user_email_))
    if (self.has_is_admin_): n += 3
    n += 2 * len(self.individual_stats_)
    for i in xrange(len(self.individual_stats_)): n += self.lengthString(self.individual_stats_[i].ByteSize())
    return n + 2

  def ByteSizePartial(self):
    n = 0
    if (self.has_start_timestamp_milliseconds_):
      n += 1
      n += self.lengthVarInt64(self.start_timestamp_milliseconds_)
    if (self.has_http_method_): n += 1 + self.lengthString(len(self.http_method_))
    if (self.has_http_path_): n += 1 + self.lengthString(len(self.http_path_))
    if (self.has_http_query_): n += 1 + self.lengthString(len(self.http_query_))
    if (self.has_http_status_): n += 1 + self.lengthVarInt64(self.http_status_)
    if (self.has_duration_milliseconds_):
      n += 1
      n += self.lengthVarInt64(self.duration_milliseconds_)
    if (self.has_api_mcycles_): n += 1 + self.lengthVarInt64(self.api_mcycles_)
    if (self.has_processor_mcycles_): n += 1 + self.lengthVarInt64(self.processor_mcycles_)
    n += 1 * len(self.rpc_stats_)
    for i in xrange(len(self.rpc_stats_)): n += self.lengthString(self.rpc_stats_[i].ByteSizePartial())
    n += 2 * len(self.cgi_env_)
    for i in xrange(len(self.cgi_env_)): n += self.lengthString(self.cgi_env_[i].ByteSizePartial())
    if (self.has_overhead_walltime_milliseconds_): n += 2 + self.lengthVarInt64(self.overhead_walltime_milliseconds_)
    if (self.has_user_email_): n += 2 + self.lengthString(len(self.user_email_))
    if (self.has_is_admin_): n += 3
    n += 2 * len(self.individual_stats_)
    for i in xrange(len(self.individual_stats_)): n += self.lengthString(self.individual_stats_[i].ByteSizePartial())
    return n

  def Clear(self):
    self.clear_start_timestamp_milliseconds()
    self.clear_http_method()
    self.clear_http_path()
    self.clear_http_query()
    self.clear_http_status()
    self.clear_duration_milliseconds()
    self.clear_api_mcycles()
    self.clear_processor_mcycles()
    self.clear_rpc_stats()
    self.clear_cgi_env()
    self.clear_overhead_walltime_milliseconds()
    self.clear_user_email()
    self.clear_is_admin()
    self.clear_individual_stats()

  def OutputUnchecked(self, out):
    out.putVarInt32(8)
    out.putVarInt64(self.start_timestamp_milliseconds_)
    if (self.has_http_method_):
      out.putVarInt32(18)
      out.putPrefixedString(self.http_method_)
    if (self.has_http_path_):
      out.putVarInt32(26)
      out.putPrefixedString(self.http_path_)
    if (self.has_http_query_):
      out.putVarInt32(34)
      out.putPrefixedString(self.http_query_)
    if (self.has_http_status_):
      out.putVarInt32(40)
      out.putVarInt32(self.http_status_)
    out.putVarInt32(48)
    out.putVarInt64(self.duration_milliseconds_)
    if (self.has_api_mcycles_):
      out.putVarInt32(56)
      out.putVarInt64(self.api_mcycles_)
    if (self.has_processor_mcycles_):
      out.putVarInt32(64)
      out.putVarInt64(self.processor_mcycles_)
    for i in xrange(len(self.rpc_stats_)):
      out.putVarInt32(74)
      out.putVarInt32(self.rpc_stats_[i].ByteSize())
      self.rpc_stats_[i].OutputUnchecked(out)
    for i in xrange(len(self.cgi_env_)):
      out.putVarInt32(810)
      out.putVarInt32(self.cgi_env_[i].ByteSize())
      self.cgi_env_[i].OutputUnchecked(out)
    if (self.has_overhead_walltime_milliseconds_):
      out.putVarInt32(816)
      out.putVarInt64(self.overhead_walltime_milliseconds_)
    if (self.has_user_email_):
      out.putVarInt32(826)
      out.putPrefixedString(self.user_email_)
    if (self.has_is_admin_):
      out.putVarInt32(832)
      out.putBoolean(self.is_admin_)
    for i in xrange(len(self.individual_stats_)):
      out.putVarInt32(858)
      out.putVarInt32(self.individual_stats_[i].ByteSize())
      self.individual_stats_[i].OutputUnchecked(out)

  def OutputPartial(self, out):
    if (self.has_start_timestamp_milliseconds_):
      out.putVarInt32(8)
      out.putVarInt64(self.start_timestamp_milliseconds_)
    if (self.has_http_method_):
      out.putVarInt32(18)
      out.putPrefixedString(self.http_method_)
    if (self.has_http_path_):
      out.putVarInt32(26)
      out.putPrefixedString(self.http_path_)
    if (self.has_http_query_):
      out.putVarInt32(34)
      out.putPrefixedString(self.http_query_)
    if (self.has_http_status_):
      out.putVarInt32(40)
      out.putVarInt32(self.http_status_)
    if (self.has_duration_milliseconds_):
      out.putVarInt32(48)
      out.putVarInt64(self.duration_milliseconds_)
    if (self.has_api_mcycles_):
      out.putVarInt32(56)
      out.putVarInt64(self.api_mcycles_)
    if (self.has_processor_mcycles_):
      out.putVarInt32(64)
      out.putVarInt64(self.processor_mcycles_)
    for i in xrange(len(self.rpc_stats_)):
      out.putVarInt32(74)
      out.putVarInt32(self.rpc_stats_[i].ByteSizePartial())
      self.rpc_stats_[i].OutputPartial(out)
    for i in xrange(len(self.cgi_env_)):
      out.putVarInt32(810)
      out.putVarInt32(self.cgi_env_[i].ByteSizePartial())
      self.cgi_env_[i].OutputPartial(out)
    if (self.has_overhead_walltime_milliseconds_):
      out.putVarInt32(816)
      out.putVarInt64(self.overhead_walltime_milliseconds_)
    if (self.has_user_email_):
      out.putVarInt32(826)
      out.putPrefixedString(self.user_email_)
    if (self.has_is_admin_):
      out.putVarInt32(832)
      out.putBoolean(self.is_admin_)
    for i in xrange(len(self.individual_stats_)):
      out.putVarInt32(858)
      out.putVarInt32(self.individual_stats_[i].ByteSizePartial())
      self.individual_stats_[i].OutputPartial(out)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 8:
        self.set_start_timestamp_milliseconds(d.getVarInt64())
        continue
      if tt == 18:
        self.set_http_method(d.getPrefixedString())
        continue
      if tt == 26:
        self.set_http_path(d.getPrefixedString())
        continue
      if tt == 34:
        self.set_http_query(d.getPrefixedString())
        continue
      if tt == 40:
        self.set_http_status(d.getVarInt32())
        continue
      if tt == 48:
        self.set_duration_milliseconds(d.getVarInt64())
        continue
      if tt == 56:
        self.set_api_mcycles(d.getVarInt64())
        continue
      if tt == 64:
        self.set_processor_mcycles(d.getVarInt64())
        continue
      if tt == 74:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.add_rpc_stats().TryMerge(tmp)
        continue
      if tt == 810:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.add_cgi_env().TryMerge(tmp)
        continue
      if tt == 816:
        self.set_overhead_walltime_milliseconds(d.getVarInt64())
        continue
      if tt == 826:
        self.set_user_email(d.getPrefixedString())
        continue
      if tt == 832:
        self.set_is_admin(d.getBoolean())
        continue
      if tt == 858:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.add_individual_stats().TryMerge(tmp)
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_start_timestamp_milliseconds_: res+=prefix+("start_timestamp_milliseconds: %s\n" % self.DebugFormatInt64(self.start_timestamp_milliseconds_))
    if self.has_http_method_: res+=prefix+("http_method: %s\n" % self.DebugFormatString(self.http_method_))
    if self.has_http_path_: res+=prefix+("http_path: %s\n" % self.DebugFormatString(self.http_path_))
    if self.has_http_query_: res+=prefix+("http_query: %s\n" % self.DebugFormatString(self.http_query_))
    if self.has_http_status_: res+=prefix+("http_status: %s\n" % self.DebugFormatInt32(self.http_status_))
    if self.has_duration_milliseconds_: res+=prefix+("duration_milliseconds: %s\n" % self.DebugFormatInt64(self.duration_milliseconds_))
    if self.has_api_mcycles_: res+=prefix+("api_mcycles: %s\n" % self.DebugFormatInt64(self.api_mcycles_))
    if self.has_processor_mcycles_: res+=prefix+("processor_mcycles: %s\n" % self.DebugFormatInt64(self.processor_mcycles_))
    cnt=0
    for e in self.rpc_stats_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("rpc_stats%s <\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
      cnt+=1
    cnt=0
    for e in self.cgi_env_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("cgi_env%s <\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
      cnt+=1
    if self.has_overhead_walltime_milliseconds_: res+=prefix+("overhead_walltime_milliseconds: %s\n" % self.DebugFormatInt64(self.overhead_walltime_milliseconds_))
    if self.has_user_email_: res+=prefix+("user_email: %s\n" % self.DebugFormatString(self.user_email_))
    if self.has_is_admin_: res+=prefix+("is_admin: %s\n" % self.DebugFormatBool(self.is_admin_))
    cnt=0
    for e in self.individual_stats_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("individual_stats%s <\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
      cnt+=1
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kstart_timestamp_milliseconds = 1
  khttp_method = 2
  khttp_path = 3
  khttp_query = 4
  khttp_status = 5
  kduration_milliseconds = 6
  kapi_mcycles = 7
  kprocessor_mcycles = 8
  krpc_stats = 9
  kcgi_env = 101
  koverhead_walltime_milliseconds = 102
  kuser_email = 103
  kis_admin = 104
  kindividual_stats = 107

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "start_timestamp_milliseconds",
    2: "http_method",
    3: "http_path",
    4: "http_query",
    5: "http_status",
    6: "duration_milliseconds",
    7: "api_mcycles",
    8: "processor_mcycles",
    9: "rpc_stats",
    101: "cgi_env",
    102: "overhead_walltime_milliseconds",
    103: "user_email",
    104: "is_admin",
    107: "individual_stats",
  }, 107)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.NUMERIC,
    2: ProtocolBuffer.Encoder.STRING,
    3: ProtocolBuffer.Encoder.STRING,
    4: ProtocolBuffer.Encoder.STRING,
    5: ProtocolBuffer.Encoder.NUMERIC,
    6: ProtocolBuffer.Encoder.NUMERIC,
    7: ProtocolBuffer.Encoder.NUMERIC,
    8: ProtocolBuffer.Encoder.NUMERIC,
    9: ProtocolBuffer.Encoder.STRING,
    101: ProtocolBuffer.Encoder.STRING,
    102: ProtocolBuffer.Encoder.NUMERIC,
    103: ProtocolBuffer.Encoder.STRING,
    104: ProtocolBuffer.Encoder.NUMERIC,
    107: ProtocolBuffer.Encoder.STRING,
  }, 107, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _PROTO_DESCRIPTOR_NAME = 'apphosting.RequestStatProto'
if _extension_runtime:
  pass

__all__ = ['AggregateRpcStatsProto','KeyValProto','StackFrameProto','IndividualRpcStatsProto','RequestStatProto']
