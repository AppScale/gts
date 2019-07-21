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
import abc
import array
import base64
import dummy_thread as thread
try:
  from google3.net.proto import _net_proto___parse__python
except ImportError:
  _net_proto___parse__python = None

if hasattr(ProtocolBuffer, 'ExtendableProtocolMessage'):
  _extension_runtime = True
  _ExtendableProtocolMessage = ProtocolBuffer.ExtendableProtocolMessage
else:
  _extension_runtime = False
  _ExtendableProtocolMessage = ProtocolBuffer.ProtocolMessage

class KeyValue(ProtocolBuffer.ProtocolMessage):
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

  if _net_proto___parse__python is not None:
    def _CMergeFromString(self, s):
      _net_proto___parse__python.MergeFromString(self, 'apphosting.ext.mapreduce.KeyValue', s)

  if _net_proto___parse__python is not None:
    def _CEncode(self):
      return _net_proto___parse__python.Encode(self, 'apphosting.ext.mapreduce.KeyValue')

  if _net_proto___parse__python is not None:
    def _CEncodePartial(self):
      return _net_proto___parse__python.EncodePartial(self, 'apphosting.ext.mapreduce.KeyValue')

  if _net_proto___parse__python is not None:
    def _CToASCII(self, output_format):
      return _net_proto___parse__python.ToASCII(self, 'apphosting.ext.mapreduce.KeyValue', output_format)


  if _net_proto___parse__python is not None:
    def ParseASCII(self, s):
      _net_proto___parse__python.ParseASCII(self, 'apphosting.ext.mapreduce.KeyValue', s)


  if _net_proto___parse__python is not None:
    def ParseASCIIIgnoreUnknown(self, s):
      _net_proto___parse__python.ParseASCIIIgnoreUnknown(self, 'apphosting.ext.mapreduce.KeyValue', s)


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
  _PROTO_DESCRIPTOR_NAME = 'apphosting.ext.mapreduce.KeyValue'
  _SERIALIZED_DESCRIPTOR = array.array('B')
  _SERIALIZED_DESCRIPTOR.fromstring(base64.decodestring("WiFhcHBob3N0aW5nL2V4dC9tYXByZWR1Y2Uva3YucHJvdG8KIWFwcGhvc3RpbmcuZXh0Lm1hcHJlZHVjZS5LZXlWYWx1ZRMaA2tleSABKAIwCTgCFBMaBXZhbHVlIAIoAjAJOAIUugGyAQohYXBwaG9zdGluZy9leHQvbWFwcmVkdWNlL2t2LnByb3RvEhhhcHBob3N0aW5nLmV4dC5tYXByZWR1Y2UiJgoIS2V5VmFsdWUSCwoDa2V5GAEgAigMEg0KBXZhbHVlGAIgAigMIkcKCUtleVZhbHVlcxIPCgNrZXkYASACKAxCAggBEhEKBXZhbHVlGAIgAygMQgIIARIWCgdwYXJ0aWFsGAMgASgIOgVmYWxzZUICIAI="))
  if _net_proto___parse__python is not None:
    _net_proto___parse__python.RegisterType(
        _SERIALIZED_DESCRIPTOR.tostring())

class KeyValues(ProtocolBuffer.ProtocolMessage):
  has_key_ = 0
  key_ = ""
  has_partial_ = 0
  partial_ = 0

  def __init__(self, contents=None):
    self.value_ = []
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

  def value_size(self): return len(self.value_)
  def value_list(self): return self.value_

  def value(self, i):
    return self.value_[i]

  def set_value(self, i, x):
    self.value_[i] = x

  def add_value(self, x):
    self.value_.append(x)

  def clear_value(self):
    self.value_ = []

  def partial(self): return self.partial_

  def set_partial(self, x):
    self.has_partial_ = 1
    self.partial_ = x

  def clear_partial(self):
    if self.has_partial_:
      self.has_partial_ = 0
      self.partial_ = 0

  def has_partial(self): return self.has_partial_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_key()): self.set_key(x.key())
    for i in xrange(x.value_size()): self.add_value(x.value(i))
    if (x.has_partial()): self.set_partial(x.partial())

  if _net_proto___parse__python is not None:
    def _CMergeFromString(self, s):
      _net_proto___parse__python.MergeFromString(self, 'apphosting.ext.mapreduce.KeyValues', s)

  if _net_proto___parse__python is not None:
    def _CEncode(self):
      return _net_proto___parse__python.Encode(self, 'apphosting.ext.mapreduce.KeyValues')

  if _net_proto___parse__python is not None:
    def _CEncodePartial(self):
      return _net_proto___parse__python.EncodePartial(self, 'apphosting.ext.mapreduce.KeyValues')

  if _net_proto___parse__python is not None:
    def _CToASCII(self, output_format):
      return _net_proto___parse__python.ToASCII(self, 'apphosting.ext.mapreduce.KeyValues', output_format)


  if _net_proto___parse__python is not None:
    def ParseASCII(self, s):
      _net_proto___parse__python.ParseASCII(self, 'apphosting.ext.mapreduce.KeyValues', s)


  if _net_proto___parse__python is not None:
    def ParseASCIIIgnoreUnknown(self, s):
      _net_proto___parse__python.ParseASCIIIgnoreUnknown(self, 'apphosting.ext.mapreduce.KeyValues', s)


  def Equals(self, x):
    if x is self: return 1
    if self.has_key_ != x.has_key_: return 0
    if self.has_key_ and self.key_ != x.key_: return 0
    if len(self.value_) != len(x.value_): return 0
    for e1, e2 in zip(self.value_, x.value_):
      if e1 != e2: return 0
    if self.has_partial_ != x.has_partial_: return 0
    if self.has_partial_ and self.partial_ != x.partial_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_key_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: key not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.key_))
    n += 1 * len(self.value_)
    for i in xrange(len(self.value_)): n += self.lengthString(len(self.value_[i]))
    if (self.has_partial_): n += 2
    return n + 1

  def ByteSizePartial(self):
    n = 0
    if (self.has_key_):
      n += 1
      n += self.lengthString(len(self.key_))
    n += 1 * len(self.value_)
    for i in xrange(len(self.value_)): n += self.lengthString(len(self.value_[i]))
    if (self.has_partial_): n += 2
    return n

  def Clear(self):
    self.clear_key()
    self.clear_value()
    self.clear_partial()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.key_)
    for i in xrange(len(self.value_)):
      out.putVarInt32(18)
      out.putPrefixedString(self.value_[i])
    if (self.has_partial_):
      out.putVarInt32(24)
      out.putBoolean(self.partial_)

  def OutputPartial(self, out):
    if (self.has_key_):
      out.putVarInt32(10)
      out.putPrefixedString(self.key_)
    for i in xrange(len(self.value_)):
      out.putVarInt32(18)
      out.putPrefixedString(self.value_[i])
    if (self.has_partial_):
      out.putVarInt32(24)
      out.putBoolean(self.partial_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_key(d.getPrefixedString())
        continue
      if tt == 18:
        self.add_value(d.getPrefixedString())
        continue
      if tt == 24:
        self.set_partial(d.getBoolean())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_key_: res+=prefix+("key: %s\n" % self.DebugFormatString(self.key_))
    cnt=0
    for e in self.value_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("value%s: %s\n" % (elm, self.DebugFormatString(e)))
      cnt+=1
    if self.has_partial_: res+=prefix+("partial: %s\n" % self.DebugFormatBool(self.partial_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kkey = 1
  kvalue = 2
  kpartial = 3

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "key",
    2: "value",
    3: "partial",
  }, 3)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.STRING,
    3: ProtocolBuffer.Encoder.NUMERIC,
  }, 3, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _PROTO_DESCRIPTOR_NAME = 'apphosting.ext.mapreduce.KeyValues'
  _SERIALIZED_DESCRIPTOR = array.array('B')
  _SERIALIZED_DESCRIPTOR.fromstring(base64.decodestring("WiFhcHBob3N0aW5nL2V4dC9tYXByZWR1Y2Uva3YucHJvdG8KImFwcGhvc3RpbmcuZXh0Lm1hcHJlZHVjZS5LZXlWYWx1ZXMTGgNrZXkgASgCMAk4AqMBqgEFY3R5cGWyAQRDb3JkpAEUExoFdmFsdWUgAigCMAk4A6MBqgEFY3R5cGWyAQRDb3JkpAEUExoHcGFydGlhbCADKAAwCDgBQgVmYWxzZaMBqgEHZGVmYXVsdLIBBWZhbHNlpAEUwgEhYXBwaG9zdGluZy5leHQubWFwcmVkdWNlLktleVZhbHVl"))
  if _net_proto___parse__python is not None:
    _net_proto___parse__python.RegisterType(
        _SERIALIZED_DESCRIPTOR.tostring())

if _extension_runtime:
  pass

__all__ = ['KeyValue','KeyValues']
