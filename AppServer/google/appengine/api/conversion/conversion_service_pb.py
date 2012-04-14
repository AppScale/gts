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

class ConversionServiceError(ProtocolBuffer.ProtocolMessage):


  OK           =    0
  TIMEOUT      =    1
  TRANSIENT_ERROR =    2
  INTERNAL_ERROR =    3
  UNSUPPORTED_CONVERSION =    4
  CONVERSION_TOO_LARGE =    5
  TOO_MANY_CONVERSIONS =    6
  INVALID_REQUEST =    7

  _ErrorCode_NAMES = {
    0: "OK",
    1: "TIMEOUT",
    2: "TRANSIENT_ERROR",
    3: "INTERNAL_ERROR",
    4: "UNSUPPORTED_CONVERSION",
    5: "CONVERSION_TOO_LARGE",
    6: "TOO_MANY_CONVERSIONS",
    7: "INVALID_REQUEST",
  }

  def ErrorCode_Name(cls, x): return cls._ErrorCode_NAMES.get(x, "")
  ErrorCode_Name = classmethod(ErrorCode_Name)


  def __init__(self, contents=None):
    pass
    if contents is not None: self.MergeFromString(contents)


  def MergeFrom(self, x):
    assert x is not self

  def Equals(self, x):
    if x is self: return 1
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    return initialized

  def ByteSize(self):
    n = 0
    return n

  def ByteSizePartial(self):
    n = 0
    return n

  def Clear(self):
    pass

  def OutputUnchecked(self, out):
    pass

  def OutputPartial(self, out):
    pass

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])


  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
  }, 0)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
  }, 0, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _PROTO_DESCRIPTOR_NAME = 'apphosting.ConversionServiceError'
class AssetInfo(ProtocolBuffer.ProtocolMessage):
  has_name_ = 0
  name_ = ""
  has_data_ = 0
  data_ = ""
  has_mime_type_ = 0
  mime_type_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def name(self): return self.name_

  def set_name(self, x):
    self.has_name_ = 1
    self.name_ = x

  def clear_name(self):
    if self.has_name_:
      self.has_name_ = 0
      self.name_ = ""

  def has_name(self): return self.has_name_

  def data(self): return self.data_

  def set_data(self, x):
    self.has_data_ = 1
    self.data_ = x

  def clear_data(self):
    if self.has_data_:
      self.has_data_ = 0
      self.data_ = ""

  def has_data(self): return self.has_data_

  def mime_type(self): return self.mime_type_

  def set_mime_type(self, x):
    self.has_mime_type_ = 1
    self.mime_type_ = x

  def clear_mime_type(self):
    if self.has_mime_type_:
      self.has_mime_type_ = 0
      self.mime_type_ = ""

  def has_mime_type(self): return self.has_mime_type_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_name()): self.set_name(x.name())
    if (x.has_data()): self.set_data(x.data())
    if (x.has_mime_type()): self.set_mime_type(x.mime_type())

  def Equals(self, x):
    if x is self: return 1
    if self.has_name_ != x.has_name_: return 0
    if self.has_name_ and self.name_ != x.name_: return 0
    if self.has_data_ != x.has_data_: return 0
    if self.has_data_ and self.data_ != x.data_: return 0
    if self.has_mime_type_ != x.has_mime_type_: return 0
    if self.has_mime_type_ and self.mime_type_ != x.mime_type_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    return initialized

  def ByteSize(self):
    n = 0
    if (self.has_name_): n += 1 + self.lengthString(len(self.name_))
    if (self.has_data_): n += 1 + self.lengthString(len(self.data_))
    if (self.has_mime_type_): n += 1 + self.lengthString(len(self.mime_type_))
    return n

  def ByteSizePartial(self):
    n = 0
    if (self.has_name_): n += 1 + self.lengthString(len(self.name_))
    if (self.has_data_): n += 1 + self.lengthString(len(self.data_))
    if (self.has_mime_type_): n += 1 + self.lengthString(len(self.mime_type_))
    return n

  def Clear(self):
    self.clear_name()
    self.clear_data()
    self.clear_mime_type()

  def OutputUnchecked(self, out):
    if (self.has_name_):
      out.putVarInt32(10)
      out.putPrefixedString(self.name_)
    if (self.has_data_):
      out.putVarInt32(18)
      out.putPrefixedString(self.data_)
    if (self.has_mime_type_):
      out.putVarInt32(26)
      out.putPrefixedString(self.mime_type_)

  def OutputPartial(self, out):
    if (self.has_name_):
      out.putVarInt32(10)
      out.putPrefixedString(self.name_)
    if (self.has_data_):
      out.putVarInt32(18)
      out.putPrefixedString(self.data_)
    if (self.has_mime_type_):
      out.putVarInt32(26)
      out.putPrefixedString(self.mime_type_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_name(d.getPrefixedString())
        continue
      if tt == 18:
        self.set_data(d.getPrefixedString())
        continue
      if tt == 26:
        self.set_mime_type(d.getPrefixedString())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_name_: res+=prefix+("name: %s\n" % self.DebugFormatString(self.name_))
    if self.has_data_: res+=prefix+("data: %s\n" % self.DebugFormatString(self.data_))
    if self.has_mime_type_: res+=prefix+("mime_type: %s\n" % self.DebugFormatString(self.mime_type_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kname = 1
  kdata = 2
  kmime_type = 3

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "name",
    2: "data",
    3: "mime_type",
  }, 3)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.STRING,
    3: ProtocolBuffer.Encoder.STRING,
  }, 3, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _PROTO_DESCRIPTOR_NAME = 'apphosting.AssetInfo'
class DocumentInfo(ProtocolBuffer.ProtocolMessage):

  def __init__(self, contents=None):
    self.asset_ = []
    if contents is not None: self.MergeFromString(contents)

  def asset_size(self): return len(self.asset_)
  def asset_list(self): return self.asset_

  def asset(self, i):
    return self.asset_[i]

  def mutable_asset(self, i):
    return self.asset_[i]

  def add_asset(self):
    x = AssetInfo()
    self.asset_.append(x)
    return x

  def clear_asset(self):
    self.asset_ = []

  def MergeFrom(self, x):
    assert x is not self
    for i in xrange(x.asset_size()): self.add_asset().CopyFrom(x.asset(i))

  def Equals(self, x):
    if x is self: return 1
    if len(self.asset_) != len(x.asset_): return 0
    for e1, e2 in zip(self.asset_, x.asset_):
      if e1 != e2: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    for p in self.asset_:
      if not p.IsInitialized(debug_strs): initialized=0
    return initialized

  def ByteSize(self):
    n = 0
    n += 1 * len(self.asset_)
    for i in xrange(len(self.asset_)): n += self.lengthString(self.asset_[i].ByteSize())
    return n

  def ByteSizePartial(self):
    n = 0
    n += 1 * len(self.asset_)
    for i in xrange(len(self.asset_)): n += self.lengthString(self.asset_[i].ByteSizePartial())
    return n

  def Clear(self):
    self.clear_asset()

  def OutputUnchecked(self, out):
    for i in xrange(len(self.asset_)):
      out.putVarInt32(10)
      out.putVarInt32(self.asset_[i].ByteSize())
      self.asset_[i].OutputUnchecked(out)

  def OutputPartial(self, out):
    for i in xrange(len(self.asset_)):
      out.putVarInt32(10)
      out.putVarInt32(self.asset_[i].ByteSizePartial())
      self.asset_[i].OutputPartial(out)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.add_asset().TryMerge(tmp)
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    cnt=0
    for e in self.asset_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("asset%s <\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
      cnt+=1
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kasset = 1

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "asset",
  }, 1)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
  }, 1, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _PROTO_DESCRIPTOR_NAME = 'apphosting.DocumentInfo'
class ConversionInput_AuxData(ProtocolBuffer.ProtocolMessage):
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
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.key_))
    if (self.has_value_): n += 1 + self.lengthString(len(self.value_))
    return n + 1

  def ByteSizePartial(self):
    n = 0
    if (self.has_key_):
      n += 1
      n += self.lengthString(len(self.key_))
    if (self.has_value_): n += 1 + self.lengthString(len(self.value_))
    return n

  def Clear(self):
    self.clear_key()
    self.clear_value()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.key_)
    if (self.has_value_):
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
  _PROTO_DESCRIPTOR_NAME = 'apphosting.ConversionInput_AuxData'
class ConversionInput(ProtocolBuffer.ProtocolMessage):
  has_input_ = 0
  has_output_mime_type_ = 0
  output_mime_type_ = ""

  def __init__(self, contents=None):
    self.input_ = DocumentInfo()
    self.flag_ = []
    if contents is not None: self.MergeFromString(contents)

  def input(self): return self.input_

  def mutable_input(self): self.has_input_ = 1; return self.input_

  def clear_input(self):self.has_input_ = 0; self.input_.Clear()

  def has_input(self): return self.has_input_

  def output_mime_type(self): return self.output_mime_type_

  def set_output_mime_type(self, x):
    self.has_output_mime_type_ = 1
    self.output_mime_type_ = x

  def clear_output_mime_type(self):
    if self.has_output_mime_type_:
      self.has_output_mime_type_ = 0
      self.output_mime_type_ = ""

  def has_output_mime_type(self): return self.has_output_mime_type_

  def flag_size(self): return len(self.flag_)
  def flag_list(self): return self.flag_

  def flag(self, i):
    return self.flag_[i]

  def mutable_flag(self, i):
    return self.flag_[i]

  def add_flag(self):
    x = ConversionInput_AuxData()
    self.flag_.append(x)
    return x

  def clear_flag(self):
    self.flag_ = []

  def MergeFrom(self, x):
    assert x is not self
    if (x.has_input()): self.mutable_input().MergeFrom(x.input())
    if (x.has_output_mime_type()): self.set_output_mime_type(x.output_mime_type())
    for i in xrange(x.flag_size()): self.add_flag().CopyFrom(x.flag(i))

  def Equals(self, x):
    if x is self: return 1
    if self.has_input_ != x.has_input_: return 0
    if self.has_input_ and self.input_ != x.input_: return 0
    if self.has_output_mime_type_ != x.has_output_mime_type_: return 0
    if self.has_output_mime_type_ and self.output_mime_type_ != x.output_mime_type_: return 0
    if len(self.flag_) != len(x.flag_): return 0
    for e1, e2 in zip(self.flag_, x.flag_):
      if e1 != e2: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_input_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: input not set.')
    elif not self.input_.IsInitialized(debug_strs): initialized = 0
    if (not self.has_output_mime_type_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: output_mime_type not set.')
    for p in self.flag_:
      if not p.IsInitialized(debug_strs): initialized=0
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(self.input_.ByteSize())
    n += self.lengthString(len(self.output_mime_type_))
    n += 1 * len(self.flag_)
    for i in xrange(len(self.flag_)): n += self.lengthString(self.flag_[i].ByteSize())
    return n + 2

  def ByteSizePartial(self):
    n = 0
    if (self.has_input_):
      n += 1
      n += self.lengthString(self.input_.ByteSizePartial())
    if (self.has_output_mime_type_):
      n += 1
      n += self.lengthString(len(self.output_mime_type_))
    n += 1 * len(self.flag_)
    for i in xrange(len(self.flag_)): n += self.lengthString(self.flag_[i].ByteSizePartial())
    return n

  def Clear(self):
    self.clear_input()
    self.clear_output_mime_type()
    self.clear_flag()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putVarInt32(self.input_.ByteSize())
    self.input_.OutputUnchecked(out)
    out.putVarInt32(18)
    out.putPrefixedString(self.output_mime_type_)
    for i in xrange(len(self.flag_)):
      out.putVarInt32(26)
      out.putVarInt32(self.flag_[i].ByteSize())
      self.flag_[i].OutputUnchecked(out)

  def OutputPartial(self, out):
    if (self.has_input_):
      out.putVarInt32(10)
      out.putVarInt32(self.input_.ByteSizePartial())
      self.input_.OutputPartial(out)
    if (self.has_output_mime_type_):
      out.putVarInt32(18)
      out.putPrefixedString(self.output_mime_type_)
    for i in xrange(len(self.flag_)):
      out.putVarInt32(26)
      out.putVarInt32(self.flag_[i].ByteSizePartial())
      self.flag_[i].OutputPartial(out)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.mutable_input().TryMerge(tmp)
        continue
      if tt == 18:
        self.set_output_mime_type(d.getPrefixedString())
        continue
      if tt == 26:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.add_flag().TryMerge(tmp)
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_input_:
      res+=prefix+"input <\n"
      res+=self.input_.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
    if self.has_output_mime_type_: res+=prefix+("output_mime_type: %s\n" % self.DebugFormatString(self.output_mime_type_))
    cnt=0
    for e in self.flag_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("flag%s <\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
      cnt+=1
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kinput = 1
  koutput_mime_type = 2
  kflag = 3

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "input",
    2: "output_mime_type",
    3: "flag",
  }, 3)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.STRING,
    3: ProtocolBuffer.Encoder.STRING,
  }, 3, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _PROTO_DESCRIPTOR_NAME = 'apphosting.ConversionInput'
class ConversionOutput(ProtocolBuffer.ProtocolMessage):
  has_error_code_ = 0
  error_code_ = 0
  has_output_ = 0
  output_ = None

  def __init__(self, contents=None):
    self.lazy_init_lock_ = thread.allocate_lock()
    if contents is not None: self.MergeFromString(contents)

  def error_code(self): return self.error_code_

  def set_error_code(self, x):
    self.has_error_code_ = 1
    self.error_code_ = x

  def clear_error_code(self):
    if self.has_error_code_:
      self.has_error_code_ = 0
      self.error_code_ = 0

  def has_error_code(self): return self.has_error_code_

  def output(self):
    if self.output_ is None:
      self.lazy_init_lock_.acquire()
      try:
        if self.output_ is None: self.output_ = DocumentInfo()
      finally:
        self.lazy_init_lock_.release()
    return self.output_

  def mutable_output(self): self.has_output_ = 1; return self.output()

  def clear_output(self):

    if self.has_output_:
      self.has_output_ = 0;
      if self.output_ is not None: self.output_.Clear()

  def has_output(self): return self.has_output_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_error_code()): self.set_error_code(x.error_code())
    if (x.has_output()): self.mutable_output().MergeFrom(x.output())

  def Equals(self, x):
    if x is self: return 1
    if self.has_error_code_ != x.has_error_code_: return 0
    if self.has_error_code_ and self.error_code_ != x.error_code_: return 0
    if self.has_output_ != x.has_output_: return 0
    if self.has_output_ and self.output_ != x.output_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_error_code_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: error_code not set.')
    if (self.has_output_ and not self.output_.IsInitialized(debug_strs)): initialized = 0
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthVarInt64(self.error_code_)
    if (self.has_output_): n += 1 + self.lengthString(self.output_.ByteSize())
    return n + 1

  def ByteSizePartial(self):
    n = 0
    if (self.has_error_code_):
      n += 1
      n += self.lengthVarInt64(self.error_code_)
    if (self.has_output_): n += 1 + self.lengthString(self.output_.ByteSizePartial())
    return n

  def Clear(self):
    self.clear_error_code()
    self.clear_output()

  def OutputUnchecked(self, out):
    out.putVarInt32(8)
    out.putVarInt32(self.error_code_)
    if (self.has_output_):
      out.putVarInt32(18)
      out.putVarInt32(self.output_.ByteSize())
      self.output_.OutputUnchecked(out)

  def OutputPartial(self, out):
    if (self.has_error_code_):
      out.putVarInt32(8)
      out.putVarInt32(self.error_code_)
    if (self.has_output_):
      out.putVarInt32(18)
      out.putVarInt32(self.output_.ByteSizePartial())
      self.output_.OutputPartial(out)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 8:
        self.set_error_code(d.getVarInt32())
        continue
      if tt == 18:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.mutable_output().TryMerge(tmp)
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_error_code_: res+=prefix+("error_code: %s\n" % self.DebugFormatInt32(self.error_code_))
    if self.has_output_:
      res+=prefix+"output <\n"
      res+=self.output_.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kerror_code = 1
  koutput = 2

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "error_code",
    2: "output",
  }, 2)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.NUMERIC,
    2: ProtocolBuffer.Encoder.STRING,
  }, 2, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _PROTO_DESCRIPTOR_NAME = 'apphosting.ConversionOutput'
class ConversionRequest(ProtocolBuffer.ProtocolMessage):

  def __init__(self, contents=None):
    self.conversion_ = []
    if contents is not None: self.MergeFromString(contents)

  def conversion_size(self): return len(self.conversion_)
  def conversion_list(self): return self.conversion_

  def conversion(self, i):
    return self.conversion_[i]

  def mutable_conversion(self, i):
    return self.conversion_[i]

  def add_conversion(self):
    x = ConversionInput()
    self.conversion_.append(x)
    return x

  def clear_conversion(self):
    self.conversion_ = []

  def MergeFrom(self, x):
    assert x is not self
    for i in xrange(x.conversion_size()): self.add_conversion().CopyFrom(x.conversion(i))

  def Equals(self, x):
    if x is self: return 1
    if len(self.conversion_) != len(x.conversion_): return 0
    for e1, e2 in zip(self.conversion_, x.conversion_):
      if e1 != e2: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    for p in self.conversion_:
      if not p.IsInitialized(debug_strs): initialized=0
    return initialized

  def ByteSize(self):
    n = 0
    n += 1 * len(self.conversion_)
    for i in xrange(len(self.conversion_)): n += self.lengthString(self.conversion_[i].ByteSize())
    return n

  def ByteSizePartial(self):
    n = 0
    n += 1 * len(self.conversion_)
    for i in xrange(len(self.conversion_)): n += self.lengthString(self.conversion_[i].ByteSizePartial())
    return n

  def Clear(self):
    self.clear_conversion()

  def OutputUnchecked(self, out):
    for i in xrange(len(self.conversion_)):
      out.putVarInt32(10)
      out.putVarInt32(self.conversion_[i].ByteSize())
      self.conversion_[i].OutputUnchecked(out)

  def OutputPartial(self, out):
    for i in xrange(len(self.conversion_)):
      out.putVarInt32(10)
      out.putVarInt32(self.conversion_[i].ByteSizePartial())
      self.conversion_[i].OutputPartial(out)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.add_conversion().TryMerge(tmp)
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    cnt=0
    for e in self.conversion_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("conversion%s <\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
      cnt+=1
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kconversion = 1

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "conversion",
  }, 1)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
  }, 1, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _PROTO_DESCRIPTOR_NAME = 'apphosting.ConversionRequest'
class ConversionResponse(ProtocolBuffer.ProtocolMessage):

  def __init__(self, contents=None):
    self.result_ = []
    if contents is not None: self.MergeFromString(contents)

  def result_size(self): return len(self.result_)
  def result_list(self): return self.result_

  def result(self, i):
    return self.result_[i]

  def mutable_result(self, i):
    return self.result_[i]

  def add_result(self):
    x = ConversionOutput()
    self.result_.append(x)
    return x

  def clear_result(self):
    self.result_ = []

  def MergeFrom(self, x):
    assert x is not self
    for i in xrange(x.result_size()): self.add_result().CopyFrom(x.result(i))

  def Equals(self, x):
    if x is self: return 1
    if len(self.result_) != len(x.result_): return 0
    for e1, e2 in zip(self.result_, x.result_):
      if e1 != e2: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    for p in self.result_:
      if not p.IsInitialized(debug_strs): initialized=0
    return initialized

  def ByteSize(self):
    n = 0
    n += 1 * len(self.result_)
    for i in xrange(len(self.result_)): n += self.lengthString(self.result_[i].ByteSize())
    return n

  def ByteSizePartial(self):
    n = 0
    n += 1 * len(self.result_)
    for i in xrange(len(self.result_)): n += self.lengthString(self.result_[i].ByteSizePartial())
    return n

  def Clear(self):
    self.clear_result()

  def OutputUnchecked(self, out):
    for i in xrange(len(self.result_)):
      out.putVarInt32(10)
      out.putVarInt32(self.result_[i].ByteSize())
      self.result_[i].OutputUnchecked(out)

  def OutputPartial(self, out):
    for i in xrange(len(self.result_)):
      out.putVarInt32(10)
      out.putVarInt32(self.result_[i].ByteSizePartial())
      self.result_[i].OutputPartial(out)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.add_result().TryMerge(tmp)
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    cnt=0
    for e in self.result_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("result%s <\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
      cnt+=1
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kresult = 1

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "result",
  }, 1)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
  }, 1, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _PROTO_DESCRIPTOR_NAME = 'apphosting.ConversionResponse'
if _extension_runtime:
  pass

__all__ = ['ConversionServiceError','AssetInfo','DocumentInfo','ConversionInput_AuxData','ConversionInput','ConversionOutput','ConversionRequest','ConversionResponse']
