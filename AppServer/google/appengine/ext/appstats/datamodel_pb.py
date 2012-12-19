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

from google.appengine.datastore.entity_pb import *
import google.appengine.datastore.entity_pb
class AggregateRpcStatsProto(ProtocolBuffer.ProtocolMessage):
  has_service_call_name_ = 0
  service_call_name_ = ""
  has_total_amount_of_calls_ = 0
  total_amount_of_calls_ = 0
  has_total_cost_of_calls_microdollars_ = 0
  total_cost_of_calls_microdollars_ = 0

  def __init__(self, contents=None):
    self.total_billed_ops_ = []
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

  def total_cost_of_calls_microdollars(self): return self.total_cost_of_calls_microdollars_

  def set_total_cost_of_calls_microdollars(self, x):
    self.has_total_cost_of_calls_microdollars_ = 1
    self.total_cost_of_calls_microdollars_ = x

  def clear_total_cost_of_calls_microdollars(self):
    if self.has_total_cost_of_calls_microdollars_:
      self.has_total_cost_of_calls_microdollars_ = 0
      self.total_cost_of_calls_microdollars_ = 0

  def has_total_cost_of_calls_microdollars(self): return self.has_total_cost_of_calls_microdollars_

  def total_billed_ops_size(self): return len(self.total_billed_ops_)
  def total_billed_ops_list(self): return self.total_billed_ops_

  def total_billed_ops(self, i):
    return self.total_billed_ops_[i]

  def mutable_total_billed_ops(self, i):
    return self.total_billed_ops_[i]

  def add_total_billed_ops(self):
    x = BilledOpProto()
    self.total_billed_ops_.append(x)
    return x

  def clear_total_billed_ops(self):
    self.total_billed_ops_ = []

  def MergeFrom(self, x):
    assert x is not self
    if (x.has_service_call_name()): self.set_service_call_name(x.service_call_name())
    if (x.has_total_amount_of_calls()): self.set_total_amount_of_calls(x.total_amount_of_calls())
    if (x.has_total_cost_of_calls_microdollars()): self.set_total_cost_of_calls_microdollars(x.total_cost_of_calls_microdollars())
    for i in xrange(x.total_billed_ops_size()): self.add_total_billed_ops().CopyFrom(x.total_billed_ops(i))

  def Equals(self, x):
    if x is self: return 1
    if self.has_service_call_name_ != x.has_service_call_name_: return 0
    if self.has_service_call_name_ and self.service_call_name_ != x.service_call_name_: return 0
    if self.has_total_amount_of_calls_ != x.has_total_amount_of_calls_: return 0
    if self.has_total_amount_of_calls_ and self.total_amount_of_calls_ != x.total_amount_of_calls_: return 0
    if self.has_total_cost_of_calls_microdollars_ != x.has_total_cost_of_calls_microdollars_: return 0
    if self.has_total_cost_of_calls_microdollars_ and self.total_cost_of_calls_microdollars_ != x.total_cost_of_calls_microdollars_: return 0
    if len(self.total_billed_ops_) != len(x.total_billed_ops_): return 0
    for e1, e2 in zip(self.total_billed_ops_, x.total_billed_ops_):
      if e1 != e2: return 0
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
    for p in self.total_billed_ops_:
      if not p.IsInitialized(debug_strs): initialized=0
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.service_call_name_))
    n += self.lengthVarInt64(self.total_amount_of_calls_)
    if (self.has_total_cost_of_calls_microdollars_): n += 1 + self.lengthVarInt64(self.total_cost_of_calls_microdollars_)
    n += 1 * len(self.total_billed_ops_)
    for i in xrange(len(self.total_billed_ops_)): n += self.lengthString(self.total_billed_ops_[i].ByteSize())
    return n + 2

  def ByteSizePartial(self):
    n = 0
    if (self.has_service_call_name_):
      n += 1
      n += self.lengthString(len(self.service_call_name_))
    if (self.has_total_amount_of_calls_):
      n += 1
      n += self.lengthVarInt64(self.total_amount_of_calls_)
    if (self.has_total_cost_of_calls_microdollars_): n += 1 + self.lengthVarInt64(self.total_cost_of_calls_microdollars_)
    n += 1 * len(self.total_billed_ops_)
    for i in xrange(len(self.total_billed_ops_)): n += self.lengthString(self.total_billed_ops_[i].ByteSizePartial())
    return n

  def Clear(self):
    self.clear_service_call_name()
    self.clear_total_amount_of_calls()
    self.clear_total_cost_of_calls_microdollars()
    self.clear_total_billed_ops()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.service_call_name_)
    out.putVarInt32(24)
    out.putVarInt64(self.total_amount_of_calls_)
    if (self.has_total_cost_of_calls_microdollars_):
      out.putVarInt32(32)
      out.putVarInt64(self.total_cost_of_calls_microdollars_)
    for i in xrange(len(self.total_billed_ops_)):
      out.putVarInt32(42)
      out.putVarInt32(self.total_billed_ops_[i].ByteSize())
      self.total_billed_ops_[i].OutputUnchecked(out)

  def OutputPartial(self, out):
    if (self.has_service_call_name_):
      out.putVarInt32(10)
      out.putPrefixedString(self.service_call_name_)
    if (self.has_total_amount_of_calls_):
      out.putVarInt32(24)
      out.putVarInt64(self.total_amount_of_calls_)
    if (self.has_total_cost_of_calls_microdollars_):
      out.putVarInt32(32)
      out.putVarInt64(self.total_cost_of_calls_microdollars_)
    for i in xrange(len(self.total_billed_ops_)):
      out.putVarInt32(42)
      out.putVarInt32(self.total_billed_ops_[i].ByteSizePartial())
      self.total_billed_ops_[i].OutputPartial(out)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_service_call_name(d.getPrefixedString())
        continue
      if tt == 24:
        self.set_total_amount_of_calls(d.getVarInt64())
        continue
      if tt == 32:
        self.set_total_cost_of_calls_microdollars(d.getVarInt64())
        continue
      if tt == 42:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.add_total_billed_ops().TryMerge(tmp)
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_service_call_name_: res+=prefix+("service_call_name: %s\n" % self.DebugFormatString(self.service_call_name_))
    if self.has_total_amount_of_calls_: res+=prefix+("total_amount_of_calls: %s\n" % self.DebugFormatInt64(self.total_amount_of_calls_))
    if self.has_total_cost_of_calls_microdollars_: res+=prefix+("total_cost_of_calls_microdollars: %s\n" % self.DebugFormatInt64(self.total_cost_of_calls_microdollars_))
    cnt=0
    for e in self.total_billed_ops_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("total_billed_ops%s <\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
      cnt+=1
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kservice_call_name = 1
  ktotal_amount_of_calls = 3
  ktotal_cost_of_calls_microdollars = 4
  ktotal_billed_ops = 5

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "service_call_name",
    3: "total_amount_of_calls",
    4: "total_cost_of_calls_microdollars",
    5: "total_billed_ops",
  }, 5)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    3: ProtocolBuffer.Encoder.NUMERIC,
    4: ProtocolBuffer.Encoder.NUMERIC,
    5: ProtocolBuffer.Encoder.STRING,
  }, 5, ProtocolBuffer.Encoder.MAX_TYPE)


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
class BilledOpProto(ProtocolBuffer.ProtocolMessage):


  DATASTORE_READ =    0
  DATASTORE_WRITE =    1
  DATASTORE_SMALL =    2
  MAIL_RECIPIENT =    3
  CHANNEL_OPEN =    4
  XMPP_STANZA  =    5
  CHANNEL_PRESENCE =    6

  _BilledOp_NAMES = {
    0: "DATASTORE_READ",
    1: "DATASTORE_WRITE",
    2: "DATASTORE_SMALL",
    3: "MAIL_RECIPIENT",
    4: "CHANNEL_OPEN",
    5: "XMPP_STANZA",
    6: "CHANNEL_PRESENCE",
  }

  def BilledOp_Name(cls, x): return cls._BilledOp_NAMES.get(x, "")
  BilledOp_Name = classmethod(BilledOp_Name)

  has_op_ = 0
  op_ = 0
  has_num_ops_ = 0
  num_ops_ = 0

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def op(self): return self.op_

  def set_op(self, x):
    self.has_op_ = 1
    self.op_ = x

  def clear_op(self):
    if self.has_op_:
      self.has_op_ = 0
      self.op_ = 0

  def has_op(self): return self.has_op_

  def num_ops(self): return self.num_ops_

  def set_num_ops(self, x):
    self.has_num_ops_ = 1
    self.num_ops_ = x

  def clear_num_ops(self):
    if self.has_num_ops_:
      self.has_num_ops_ = 0
      self.num_ops_ = 0

  def has_num_ops(self): return self.has_num_ops_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_op()): self.set_op(x.op())
    if (x.has_num_ops()): self.set_num_ops(x.num_ops())

  def Equals(self, x):
    if x is self: return 1
    if self.has_op_ != x.has_op_: return 0
    if self.has_op_ and self.op_ != x.op_: return 0
    if self.has_num_ops_ != x.has_num_ops_: return 0
    if self.has_num_ops_ and self.num_ops_ != x.num_ops_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_op_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: op not set.')
    if (not self.has_num_ops_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: num_ops not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthVarInt64(self.op_)
    n += self.lengthVarInt64(self.num_ops_)
    return n + 2

  def ByteSizePartial(self):
    n = 0
    if (self.has_op_):
      n += 1
      n += self.lengthVarInt64(self.op_)
    if (self.has_num_ops_):
      n += 1
      n += self.lengthVarInt64(self.num_ops_)
    return n

  def Clear(self):
    self.clear_op()
    self.clear_num_ops()

  def OutputUnchecked(self, out):
    out.putVarInt32(8)
    out.putVarInt32(self.op_)
    out.putVarInt32(16)
    out.putVarInt32(self.num_ops_)

  def OutputPartial(self, out):
    if (self.has_op_):
      out.putVarInt32(8)
      out.putVarInt32(self.op_)
    if (self.has_num_ops_):
      out.putVarInt32(16)
      out.putVarInt32(self.num_ops_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 8:
        self.set_op(d.getVarInt32())
        continue
      if tt == 16:
        self.set_num_ops(d.getVarInt32())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_op_: res+=prefix+("op: %s\n" % self.DebugFormatInt32(self.op_))
    if self.has_num_ops_: res+=prefix+("num_ops: %s\n" % self.DebugFormatInt32(self.num_ops_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kop = 1
  knum_ops = 2

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "op",
    2: "num_ops",
  }, 2)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.NUMERIC,
    2: ProtocolBuffer.Encoder.NUMERIC,
  }, 2, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _PROTO_DESCRIPTOR_NAME = 'apphosting.BilledOpProto'
class DatastoreCallDetailsProto(ProtocolBuffer.ProtocolMessage):
  has_query_kind_ = 0
  query_kind_ = ""
  has_query_ancestor_ = 0
  query_ancestor_ = None
  has_query_thiscursor_ = 0
  query_thiscursor_ = 0
  has_query_nextcursor_ = 0
  query_nextcursor_ = 0

  def __init__(self, contents=None):
    self.get_successful_fetch_ = []
    self.keys_read_ = []
    self.keys_written_ = []
    self.lazy_init_lock_ = thread.allocate_lock()
    if contents is not None: self.MergeFromString(contents)

  def query_kind(self): return self.query_kind_

  def set_query_kind(self, x):
    self.has_query_kind_ = 1
    self.query_kind_ = x

  def clear_query_kind(self):
    if self.has_query_kind_:
      self.has_query_kind_ = 0
      self.query_kind_ = ""

  def has_query_kind(self): return self.has_query_kind_

  def query_ancestor(self):
    if self.query_ancestor_ is None:
      self.lazy_init_lock_.acquire()
      try:
        if self.query_ancestor_ is None: self.query_ancestor_ = Reference()
      finally:
        self.lazy_init_lock_.release()
    return self.query_ancestor_

  def mutable_query_ancestor(self): self.has_query_ancestor_ = 1; return self.query_ancestor()

  def clear_query_ancestor(self):

    if self.has_query_ancestor_:
      self.has_query_ancestor_ = 0;
      if self.query_ancestor_ is not None: self.query_ancestor_.Clear()

  def has_query_ancestor(self): return self.has_query_ancestor_

  def query_thiscursor(self): return self.query_thiscursor_

  def set_query_thiscursor(self, x):
    self.has_query_thiscursor_ = 1
    self.query_thiscursor_ = x

  def clear_query_thiscursor(self):
    if self.has_query_thiscursor_:
      self.has_query_thiscursor_ = 0
      self.query_thiscursor_ = 0

  def has_query_thiscursor(self): return self.has_query_thiscursor_

  def query_nextcursor(self): return self.query_nextcursor_

  def set_query_nextcursor(self, x):
    self.has_query_nextcursor_ = 1
    self.query_nextcursor_ = x

  def clear_query_nextcursor(self):
    if self.has_query_nextcursor_:
      self.has_query_nextcursor_ = 0
      self.query_nextcursor_ = 0

  def has_query_nextcursor(self): return self.has_query_nextcursor_

  def get_successful_fetch_size(self): return len(self.get_successful_fetch_)
  def get_successful_fetch_list(self): return self.get_successful_fetch_

  def get_successful_fetch(self, i):
    return self.get_successful_fetch_[i]

  def set_get_successful_fetch(self, i, x):
    self.get_successful_fetch_[i] = x

  def add_get_successful_fetch(self, x):
    self.get_successful_fetch_.append(x)

  def clear_get_successful_fetch(self):
    self.get_successful_fetch_ = []

  def keys_read_size(self): return len(self.keys_read_)
  def keys_read_list(self): return self.keys_read_

  def keys_read(self, i):
    return self.keys_read_[i]

  def mutable_keys_read(self, i):
    return self.keys_read_[i]

  def add_keys_read(self):
    x = Reference()
    self.keys_read_.append(x)
    return x

  def clear_keys_read(self):
    self.keys_read_ = []
  def keys_written_size(self): return len(self.keys_written_)
  def keys_written_list(self): return self.keys_written_

  def keys_written(self, i):
    return self.keys_written_[i]

  def mutable_keys_written(self, i):
    return self.keys_written_[i]

  def add_keys_written(self):
    x = Reference()
    self.keys_written_.append(x)
    return x

  def clear_keys_written(self):
    self.keys_written_ = []

  def MergeFrom(self, x):
    assert x is not self
    if (x.has_query_kind()): self.set_query_kind(x.query_kind())
    if (x.has_query_ancestor()): self.mutable_query_ancestor().MergeFrom(x.query_ancestor())
    if (x.has_query_thiscursor()): self.set_query_thiscursor(x.query_thiscursor())
    if (x.has_query_nextcursor()): self.set_query_nextcursor(x.query_nextcursor())
    for i in xrange(x.get_successful_fetch_size()): self.add_get_successful_fetch(x.get_successful_fetch(i))
    for i in xrange(x.keys_read_size()): self.add_keys_read().CopyFrom(x.keys_read(i))
    for i in xrange(x.keys_written_size()): self.add_keys_written().CopyFrom(x.keys_written(i))

  def Equals(self, x):
    if x is self: return 1
    if self.has_query_kind_ != x.has_query_kind_: return 0
    if self.has_query_kind_ and self.query_kind_ != x.query_kind_: return 0
    if self.has_query_ancestor_ != x.has_query_ancestor_: return 0
    if self.has_query_ancestor_ and self.query_ancestor_ != x.query_ancestor_: return 0
    if self.has_query_thiscursor_ != x.has_query_thiscursor_: return 0
    if self.has_query_thiscursor_ and self.query_thiscursor_ != x.query_thiscursor_: return 0
    if self.has_query_nextcursor_ != x.has_query_nextcursor_: return 0
    if self.has_query_nextcursor_ and self.query_nextcursor_ != x.query_nextcursor_: return 0
    if len(self.get_successful_fetch_) != len(x.get_successful_fetch_): return 0
    for e1, e2 in zip(self.get_successful_fetch_, x.get_successful_fetch_):
      if e1 != e2: return 0
    if len(self.keys_read_) != len(x.keys_read_): return 0
    for e1, e2 in zip(self.keys_read_, x.keys_read_):
      if e1 != e2: return 0
    if len(self.keys_written_) != len(x.keys_written_): return 0
    for e1, e2 in zip(self.keys_written_, x.keys_written_):
      if e1 != e2: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (self.has_query_ancestor_ and not self.query_ancestor_.IsInitialized(debug_strs)): initialized = 0
    for p in self.keys_read_:
      if not p.IsInitialized(debug_strs): initialized=0
    for p in self.keys_written_:
      if not p.IsInitialized(debug_strs): initialized=0
    return initialized

  def ByteSize(self):
    n = 0
    if (self.has_query_kind_): n += 1 + self.lengthString(len(self.query_kind_))
    if (self.has_query_ancestor_): n += 1 + self.lengthString(self.query_ancestor_.ByteSize())
    if (self.has_query_thiscursor_): n += 9
    if (self.has_query_nextcursor_): n += 9
    n += 2 * len(self.get_successful_fetch_)
    n += 1 * len(self.keys_read_)
    for i in xrange(len(self.keys_read_)): n += self.lengthString(self.keys_read_[i].ByteSize())
    n += 1 * len(self.keys_written_)
    for i in xrange(len(self.keys_written_)): n += self.lengthString(self.keys_written_[i].ByteSize())
    return n

  def ByteSizePartial(self):
    n = 0
    if (self.has_query_kind_): n += 1 + self.lengthString(len(self.query_kind_))
    if (self.has_query_ancestor_): n += 1 + self.lengthString(self.query_ancestor_.ByteSizePartial())
    if (self.has_query_thiscursor_): n += 9
    if (self.has_query_nextcursor_): n += 9
    n += 2 * len(self.get_successful_fetch_)
    n += 1 * len(self.keys_read_)
    for i in xrange(len(self.keys_read_)): n += self.lengthString(self.keys_read_[i].ByteSizePartial())
    n += 1 * len(self.keys_written_)
    for i in xrange(len(self.keys_written_)): n += self.lengthString(self.keys_written_[i].ByteSizePartial())
    return n

  def Clear(self):
    self.clear_query_kind()
    self.clear_query_ancestor()
    self.clear_query_thiscursor()
    self.clear_query_nextcursor()
    self.clear_get_successful_fetch()
    self.clear_keys_read()
    self.clear_keys_written()

  def OutputUnchecked(self, out):
    if (self.has_query_kind_):
      out.putVarInt32(10)
      out.putPrefixedString(self.query_kind_)
    if (self.has_query_ancestor_):
      out.putVarInt32(18)
      out.putVarInt32(self.query_ancestor_.ByteSize())
      self.query_ancestor_.OutputUnchecked(out)
    if (self.has_query_thiscursor_):
      out.putVarInt32(25)
      out.put64(self.query_thiscursor_)
    if (self.has_query_nextcursor_):
      out.putVarInt32(33)
      out.put64(self.query_nextcursor_)
    for i in xrange(len(self.get_successful_fetch_)):
      out.putVarInt32(40)
      out.putBoolean(self.get_successful_fetch_[i])
    for i in xrange(len(self.keys_read_)):
      out.putVarInt32(50)
      out.putVarInt32(self.keys_read_[i].ByteSize())
      self.keys_read_[i].OutputUnchecked(out)
    for i in xrange(len(self.keys_written_)):
      out.putVarInt32(58)
      out.putVarInt32(self.keys_written_[i].ByteSize())
      self.keys_written_[i].OutputUnchecked(out)

  def OutputPartial(self, out):
    if (self.has_query_kind_):
      out.putVarInt32(10)
      out.putPrefixedString(self.query_kind_)
    if (self.has_query_ancestor_):
      out.putVarInt32(18)
      out.putVarInt32(self.query_ancestor_.ByteSizePartial())
      self.query_ancestor_.OutputPartial(out)
    if (self.has_query_thiscursor_):
      out.putVarInt32(25)
      out.put64(self.query_thiscursor_)
    if (self.has_query_nextcursor_):
      out.putVarInt32(33)
      out.put64(self.query_nextcursor_)
    for i in xrange(len(self.get_successful_fetch_)):
      out.putVarInt32(40)
      out.putBoolean(self.get_successful_fetch_[i])
    for i in xrange(len(self.keys_read_)):
      out.putVarInt32(50)
      out.putVarInt32(self.keys_read_[i].ByteSizePartial())
      self.keys_read_[i].OutputPartial(out)
    for i in xrange(len(self.keys_written_)):
      out.putVarInt32(58)
      out.putVarInt32(self.keys_written_[i].ByteSizePartial())
      self.keys_written_[i].OutputPartial(out)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_query_kind(d.getPrefixedString())
        continue
      if tt == 18:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.mutable_query_ancestor().TryMerge(tmp)
        continue
      if tt == 25:
        self.set_query_thiscursor(d.get64())
        continue
      if tt == 33:
        self.set_query_nextcursor(d.get64())
        continue
      if tt == 40:
        self.add_get_successful_fetch(d.getBoolean())
        continue
      if tt == 50:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.add_keys_read().TryMerge(tmp)
        continue
      if tt == 58:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.add_keys_written().TryMerge(tmp)
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_query_kind_: res+=prefix+("query_kind: %s\n" % self.DebugFormatString(self.query_kind_))
    if self.has_query_ancestor_:
      res+=prefix+"query_ancestor <\n"
      res+=self.query_ancestor_.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
    if self.has_query_thiscursor_: res+=prefix+("query_thiscursor: %s\n" % self.DebugFormatFixed64(self.query_thiscursor_))
    if self.has_query_nextcursor_: res+=prefix+("query_nextcursor: %s\n" % self.DebugFormatFixed64(self.query_nextcursor_))
    cnt=0
    for e in self.get_successful_fetch_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("get_successful_fetch%s: %s\n" % (elm, self.DebugFormatBool(e)))
      cnt+=1
    cnt=0
    for e in self.keys_read_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("keys_read%s <\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
      cnt+=1
    cnt=0
    for e in self.keys_written_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("keys_written%s <\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
      cnt+=1
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kquery_kind = 1
  kquery_ancestor = 2
  kquery_thiscursor = 3
  kquery_nextcursor = 4
  kget_successful_fetch = 5
  kkeys_read = 6
  kkeys_written = 7

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "query_kind",
    2: "query_ancestor",
    3: "query_thiscursor",
    4: "query_nextcursor",
    5: "get_successful_fetch",
    6: "keys_read",
    7: "keys_written",
  }, 7)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.STRING,
    3: ProtocolBuffer.Encoder.DOUBLE,
    4: ProtocolBuffer.Encoder.DOUBLE,
    5: ProtocolBuffer.Encoder.NUMERIC,
    6: ProtocolBuffer.Encoder.STRING,
    7: ProtocolBuffer.Encoder.STRING,
  }, 7, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _PROTO_DESCRIPTOR_NAME = 'apphosting.DatastoreCallDetailsProto'
class IndividualRpcStatsProto(ProtocolBuffer.ProtocolMessage):
  has_service_call_name_ = 0
  service_call_name_ = ""
  has_request_data_summary_ = 0
  request_data_summary_ = ""
  has_response_data_summary_ = 0
  response_data_summary_ = ""
  has_api_mcycles_ = 0
  api_mcycles_ = 0
  has_api_milliseconds_ = 0
  api_milliseconds_ = 0
  has_start_offset_milliseconds_ = 0
  start_offset_milliseconds_ = 0
  has_duration_milliseconds_ = 0
  duration_milliseconds_ = 0
  has_namespace_ = 0
  namespace_ = ""
  has_was_successful_ = 0
  was_successful_ = 1
  has_datastore_details_ = 0
  datastore_details_ = None
  has_call_cost_microdollars_ = 0
  call_cost_microdollars_ = 0

  def __init__(self, contents=None):
    self.call_stack_ = []
    self.billed_ops_ = []
    self.lazy_init_lock_ = thread.allocate_lock()
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

  def api_milliseconds(self): return self.api_milliseconds_

  def set_api_milliseconds(self, x):
    self.has_api_milliseconds_ = 1
    self.api_milliseconds_ = x

  def clear_api_milliseconds(self):
    if self.has_api_milliseconds_:
      self.has_api_milliseconds_ = 0
      self.api_milliseconds_ = 0

  def has_api_milliseconds(self): return self.has_api_milliseconds_

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
  def datastore_details(self):
    if self.datastore_details_ is None:
      self.lazy_init_lock_.acquire()
      try:
        if self.datastore_details_ is None: self.datastore_details_ = DatastoreCallDetailsProto()
      finally:
        self.lazy_init_lock_.release()
    return self.datastore_details_

  def mutable_datastore_details(self): self.has_datastore_details_ = 1; return self.datastore_details()

  def clear_datastore_details(self):

    if self.has_datastore_details_:
      self.has_datastore_details_ = 0;
      if self.datastore_details_ is not None: self.datastore_details_.Clear()

  def has_datastore_details(self): return self.has_datastore_details_

  def call_cost_microdollars(self): return self.call_cost_microdollars_

  def set_call_cost_microdollars(self, x):
    self.has_call_cost_microdollars_ = 1
    self.call_cost_microdollars_ = x

  def clear_call_cost_microdollars(self):
    if self.has_call_cost_microdollars_:
      self.has_call_cost_microdollars_ = 0
      self.call_cost_microdollars_ = 0

  def has_call_cost_microdollars(self): return self.has_call_cost_microdollars_

  def billed_ops_size(self): return len(self.billed_ops_)
  def billed_ops_list(self): return self.billed_ops_

  def billed_ops(self, i):
    return self.billed_ops_[i]

  def mutable_billed_ops(self, i):
    return self.billed_ops_[i]

  def add_billed_ops(self):
    x = BilledOpProto()
    self.billed_ops_.append(x)
    return x

  def clear_billed_ops(self):
    self.billed_ops_ = []

  def MergeFrom(self, x):
    assert x is not self
    if (x.has_service_call_name()): self.set_service_call_name(x.service_call_name())
    if (x.has_request_data_summary()): self.set_request_data_summary(x.request_data_summary())
    if (x.has_response_data_summary()): self.set_response_data_summary(x.response_data_summary())
    if (x.has_api_mcycles()): self.set_api_mcycles(x.api_mcycles())
    if (x.has_api_milliseconds()): self.set_api_milliseconds(x.api_milliseconds())
    if (x.has_start_offset_milliseconds()): self.set_start_offset_milliseconds(x.start_offset_milliseconds())
    if (x.has_duration_milliseconds()): self.set_duration_milliseconds(x.duration_milliseconds())
    if (x.has_namespace()): self.set_namespace(x.namespace())
    if (x.has_was_successful()): self.set_was_successful(x.was_successful())
    for i in xrange(x.call_stack_size()): self.add_call_stack().CopyFrom(x.call_stack(i))
    if (x.has_datastore_details()): self.mutable_datastore_details().MergeFrom(x.datastore_details())
    if (x.has_call_cost_microdollars()): self.set_call_cost_microdollars(x.call_cost_microdollars())
    for i in xrange(x.billed_ops_size()): self.add_billed_ops().CopyFrom(x.billed_ops(i))

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
    if self.has_api_milliseconds_ != x.has_api_milliseconds_: return 0
    if self.has_api_milliseconds_ and self.api_milliseconds_ != x.api_milliseconds_: return 0
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
    if self.has_datastore_details_ != x.has_datastore_details_: return 0
    if self.has_datastore_details_ and self.datastore_details_ != x.datastore_details_: return 0
    if self.has_call_cost_microdollars_ != x.has_call_cost_microdollars_: return 0
    if self.has_call_cost_microdollars_ and self.call_cost_microdollars_ != x.call_cost_microdollars_: return 0
    if len(self.billed_ops_) != len(x.billed_ops_): return 0
    for e1, e2 in zip(self.billed_ops_, x.billed_ops_):
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
    if (self.has_datastore_details_ and not self.datastore_details_.IsInitialized(debug_strs)): initialized = 0
    for p in self.billed_ops_:
      if not p.IsInitialized(debug_strs): initialized=0
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.service_call_name_))
    if (self.has_request_data_summary_): n += 1 + self.lengthString(len(self.request_data_summary_))
    if (self.has_response_data_summary_): n += 1 + self.lengthString(len(self.response_data_summary_))
    if (self.has_api_mcycles_): n += 1 + self.lengthVarInt64(self.api_mcycles_)
    if (self.has_api_milliseconds_): n += 1 + self.lengthVarInt64(self.api_milliseconds_)
    n += self.lengthVarInt64(self.start_offset_milliseconds_)
    if (self.has_duration_milliseconds_): n += 1 + self.lengthVarInt64(self.duration_milliseconds_)
    if (self.has_namespace_): n += 1 + self.lengthString(len(self.namespace_))
    if (self.has_was_successful_): n += 2
    n += 1 * len(self.call_stack_)
    for i in xrange(len(self.call_stack_)): n += self.lengthString(self.call_stack_[i].ByteSize())
    if (self.has_datastore_details_): n += 1 + self.lengthString(self.datastore_details_.ByteSize())
    if (self.has_call_cost_microdollars_): n += 1 + self.lengthVarInt64(self.call_cost_microdollars_)
    n += 1 * len(self.billed_ops_)
    for i in xrange(len(self.billed_ops_)): n += self.lengthString(self.billed_ops_[i].ByteSize())
    return n + 2

  def ByteSizePartial(self):
    n = 0
    if (self.has_service_call_name_):
      n += 1
      n += self.lengthString(len(self.service_call_name_))
    if (self.has_request_data_summary_): n += 1 + self.lengthString(len(self.request_data_summary_))
    if (self.has_response_data_summary_): n += 1 + self.lengthString(len(self.response_data_summary_))
    if (self.has_api_mcycles_): n += 1 + self.lengthVarInt64(self.api_mcycles_)
    if (self.has_api_milliseconds_): n += 1 + self.lengthVarInt64(self.api_milliseconds_)
    if (self.has_start_offset_milliseconds_):
      n += 1
      n += self.lengthVarInt64(self.start_offset_milliseconds_)
    if (self.has_duration_milliseconds_): n += 1 + self.lengthVarInt64(self.duration_milliseconds_)
    if (self.has_namespace_): n += 1 + self.lengthString(len(self.namespace_))
    if (self.has_was_successful_): n += 2
    n += 1 * len(self.call_stack_)
    for i in xrange(len(self.call_stack_)): n += self.lengthString(self.call_stack_[i].ByteSizePartial())
    if (self.has_datastore_details_): n += 1 + self.lengthString(self.datastore_details_.ByteSizePartial())
    if (self.has_call_cost_microdollars_): n += 1 + self.lengthVarInt64(self.call_cost_microdollars_)
    n += 1 * len(self.billed_ops_)
    for i in xrange(len(self.billed_ops_)): n += self.lengthString(self.billed_ops_[i].ByteSizePartial())
    return n

  def Clear(self):
    self.clear_service_call_name()
    self.clear_request_data_summary()
    self.clear_response_data_summary()
    self.clear_api_mcycles()
    self.clear_api_milliseconds()
    self.clear_start_offset_milliseconds()
    self.clear_duration_milliseconds()
    self.clear_namespace()
    self.clear_was_successful()
    self.clear_call_stack()
    self.clear_datastore_details()
    self.clear_call_cost_microdollars()
    self.clear_billed_ops()

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
    if (self.has_api_milliseconds_):
      out.putVarInt32(88)
      out.putVarInt64(self.api_milliseconds_)
    if (self.has_datastore_details_):
      out.putVarInt32(98)
      out.putVarInt32(self.datastore_details_.ByteSize())
      self.datastore_details_.OutputUnchecked(out)
    if (self.has_call_cost_microdollars_):
      out.putVarInt32(104)
      out.putVarInt64(self.call_cost_microdollars_)
    for i in xrange(len(self.billed_ops_)):
      out.putVarInt32(114)
      out.putVarInt32(self.billed_ops_[i].ByteSize())
      self.billed_ops_[i].OutputUnchecked(out)

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
    if (self.has_api_milliseconds_):
      out.putVarInt32(88)
      out.putVarInt64(self.api_milliseconds_)
    if (self.has_datastore_details_):
      out.putVarInt32(98)
      out.putVarInt32(self.datastore_details_.ByteSizePartial())
      self.datastore_details_.OutputPartial(out)
    if (self.has_call_cost_microdollars_):
      out.putVarInt32(104)
      out.putVarInt64(self.call_cost_microdollars_)
    for i in xrange(len(self.billed_ops_)):
      out.putVarInt32(114)
      out.putVarInt32(self.billed_ops_[i].ByteSizePartial())
      self.billed_ops_[i].OutputPartial(out)

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
      if tt == 88:
        self.set_api_milliseconds(d.getVarInt64())
        continue
      if tt == 98:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.mutable_datastore_details().TryMerge(tmp)
        continue
      if tt == 104:
        self.set_call_cost_microdollars(d.getVarInt64())
        continue
      if tt == 114:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.add_billed_ops().TryMerge(tmp)
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_service_call_name_: res+=prefix+("service_call_name: %s\n" % self.DebugFormatString(self.service_call_name_))
    if self.has_request_data_summary_: res+=prefix+("request_data_summary: %s\n" % self.DebugFormatString(self.request_data_summary_))
    if self.has_response_data_summary_: res+=prefix+("response_data_summary: %s\n" % self.DebugFormatString(self.response_data_summary_))
    if self.has_api_mcycles_: res+=prefix+("api_mcycles: %s\n" % self.DebugFormatInt64(self.api_mcycles_))
    if self.has_api_milliseconds_: res+=prefix+("api_milliseconds: %s\n" % self.DebugFormatInt64(self.api_milliseconds_))
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
    if self.has_datastore_details_:
      res+=prefix+"datastore_details <\n"
      res+=self.datastore_details_.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
    if self.has_call_cost_microdollars_: res+=prefix+("call_cost_microdollars: %s\n" % self.DebugFormatInt64(self.call_cost_microdollars_))
    cnt=0
    for e in self.billed_ops_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("billed_ops%s <\n" % elm)
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
  kapi_milliseconds = 11
  kstart_offset_milliseconds = 6
  kduration_milliseconds = 7
  knamespace = 8
  kwas_successful = 9
  kcall_stack = 10
  kdatastore_details = 12
  kcall_cost_microdollars = 13
  kbilled_ops = 14

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
    11: "api_milliseconds",
    12: "datastore_details",
    13: "call_cost_microdollars",
    14: "billed_ops",
  }, 14)

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
    11: ProtocolBuffer.Encoder.NUMERIC,
    12: ProtocolBuffer.Encoder.STRING,
    13: ProtocolBuffer.Encoder.NUMERIC,
    14: ProtocolBuffer.Encoder.STRING,
  }, 14, ProtocolBuffer.Encoder.MAX_TYPE)


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

__all__ = ['AggregateRpcStatsProto','KeyValProto','StackFrameProto','BilledOpProto','DatastoreCallDetailsProto','IndividualRpcStatsProto','RequestStatProto']
