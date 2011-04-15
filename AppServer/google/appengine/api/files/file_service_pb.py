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

from google.appengine.api.api_base_pb import *
import google.appengine.api.api_base_pb
class FileServiceErrors(ProtocolBuffer.ProtocolMessage):


  OK           =    0
  API_TEMPORARILY_UNAVAILABLE =    1
  REQUEST_TOO_LARGE =    3
  RESPONSE_TOO_LARGE =    4
  INVALID_FILE_NAME =    5
  OPERATION_NOT_SUPPORTED =    6
  IO_ERROR     =    7
  PERMISSION_DENIED =    8
  WRONG_CONTENT_TYPE =    9
  FILE_NOT_OPENED =   10
  WRONG_OPEN_MODE =   11
  EXCLUSIVE_LOCK_REQUIRED =   12
  FILE_TEMPORARILY_UNAVAILABLE =   13
  EXISTENCE_ERROR =  100
  FINALIZATION_ERROR =  101
  UNSUPPORTED_CONTENT_TYPE =  102
  READ_ONLY    =  103
  EXCLUSIVE_LOCK_FAILED =  104
  SEQUENCE_KEY_OUT_OF_ORDER =  300
  WRONG_KEY_ORDER =  400
  OUT_OF_BOUNDS =  500
  GLOBS_NOT_SUPPORTED =  600
  FILE_NAME_NOT_SPECIFIED =  701
  FILE_NAME_SPECIFIED =  702
  FILE_ALREADY_EXISTS =  703
  UNSUPPORTED_FILE_SYSTEM =  704
  INVALID_PARAMETER =  705
  MAX_ERROR_CODE = 9999

  _ErrorCode_NAMES = {
    0: "OK",
    1: "API_TEMPORARILY_UNAVAILABLE",
    3: "REQUEST_TOO_LARGE",
    4: "RESPONSE_TOO_LARGE",
    5: "INVALID_FILE_NAME",
    6: "OPERATION_NOT_SUPPORTED",
    7: "IO_ERROR",
    8: "PERMISSION_DENIED",
    9: "WRONG_CONTENT_TYPE",
    10: "FILE_NOT_OPENED",
    11: "WRONG_OPEN_MODE",
    12: "EXCLUSIVE_LOCK_REQUIRED",
    13: "FILE_TEMPORARILY_UNAVAILABLE",
    100: "EXISTENCE_ERROR",
    101: "FINALIZATION_ERROR",
    102: "UNSUPPORTED_CONTENT_TYPE",
    103: "READ_ONLY",
    104: "EXCLUSIVE_LOCK_FAILED",
    300: "SEQUENCE_KEY_OUT_OF_ORDER",
    400: "WRONG_KEY_ORDER",
    500: "OUT_OF_BOUNDS",
    600: "GLOBS_NOT_SUPPORTED",
    701: "FILE_NAME_NOT_SPECIFIED",
    702: "FILE_NAME_SPECIFIED",
    703: "FILE_ALREADY_EXISTS",
    704: "UNSUPPORTED_FILE_SYSTEM",
    705: "INVALID_PARAMETER",
    9999: "MAX_ERROR_CODE",
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
class FileContentType(ProtocolBuffer.ProtocolMessage):


  RAW          =    0
  ORDERED_KEY_VALUE =    2
  INVALID_TYPE =  127

  _ContentType_NAMES = {
    0: "RAW",
    2: "ORDERED_KEY_VALUE",
    127: "INVALID_TYPE",
  }

  def ContentType_Name(cls, x): return cls._ContentType_NAMES.get(x, "")
  ContentType_Name = classmethod(ContentType_Name)


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
class CreateRequest_Parameter(ProtocolBuffer.ProtocolMessage):
  has_name_ = 0
  name_ = ""
  has_value_ = 0
  value_ = ""

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
    if (x.has_name()): self.set_name(x.name())
    if (x.has_value()): self.set_value(x.value())

  def Equals(self, x):
    if x is self: return 1
    if self.has_name_ != x.has_name_: return 0
    if self.has_name_ and self.name_ != x.name_: return 0
    if self.has_value_ != x.has_value_: return 0
    if self.has_value_ and self.value_ != x.value_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_name_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: name not set.')
    if (not self.has_value_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: value not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.name_))
    n += self.lengthString(len(self.value_))
    return n + 2

  def ByteSizePartial(self):
    n = 0
    if (self.has_name_):
      n += 1
      n += self.lengthString(len(self.name_))
    if (self.has_value_):
      n += 1
      n += self.lengthString(len(self.value_))
    return n

  def Clear(self):
    self.clear_name()
    self.clear_value()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.name_)
    out.putVarInt32(18)
    out.putPrefixedString(self.value_)

  def OutputPartial(self, out):
    if (self.has_name_):
      out.putVarInt32(10)
      out.putPrefixedString(self.name_)
    if (self.has_value_):
      out.putVarInt32(18)
      out.putPrefixedString(self.value_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_name(d.getPrefixedString())
        continue
      if tt == 18:
        self.set_value(d.getPrefixedString())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_name_: res+=prefix+("name: %s\n" % self.DebugFormatString(self.name_))
    if self.has_value_: res+=prefix+("value: %s\n" % self.DebugFormatString(self.value_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kname = 1
  kvalue = 2

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "name",
    2: "value",
  }, 2)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.STRING,
  }, 2, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class CreateRequest(ProtocolBuffer.ProtocolMessage):
  has_filesystem_ = 0
  filesystem_ = ""
  has_content_type_ = 0
  content_type_ = 0
  has_filename_ = 0
  filename_ = ""
  has_expiration_time_seconds_ = 0
  expiration_time_seconds_ = 0

  def __init__(self, contents=None):
    self.parameters_ = []
    if contents is not None: self.MergeFromString(contents)

  def filesystem(self): return self.filesystem_

  def set_filesystem(self, x):
    self.has_filesystem_ = 1
    self.filesystem_ = x

  def clear_filesystem(self):
    if self.has_filesystem_:
      self.has_filesystem_ = 0
      self.filesystem_ = ""

  def has_filesystem(self): return self.has_filesystem_

  def content_type(self): return self.content_type_

  def set_content_type(self, x):
    self.has_content_type_ = 1
    self.content_type_ = x

  def clear_content_type(self):
    if self.has_content_type_:
      self.has_content_type_ = 0
      self.content_type_ = 0

  def has_content_type(self): return self.has_content_type_

  def filename(self): return self.filename_

  def set_filename(self, x):
    self.has_filename_ = 1
    self.filename_ = x

  def clear_filename(self):
    if self.has_filename_:
      self.has_filename_ = 0
      self.filename_ = ""

  def has_filename(self): return self.has_filename_

  def parameters_size(self): return len(self.parameters_)
  def parameters_list(self): return self.parameters_

  def parameters(self, i):
    return self.parameters_[i]

  def mutable_parameters(self, i):
    return self.parameters_[i]

  def add_parameters(self):
    x = CreateRequest_Parameter()
    self.parameters_.append(x)
    return x

  def clear_parameters(self):
    self.parameters_ = []
  def expiration_time_seconds(self): return self.expiration_time_seconds_

  def set_expiration_time_seconds(self, x):
    self.has_expiration_time_seconds_ = 1
    self.expiration_time_seconds_ = x

  def clear_expiration_time_seconds(self):
    if self.has_expiration_time_seconds_:
      self.has_expiration_time_seconds_ = 0
      self.expiration_time_seconds_ = 0

  def has_expiration_time_seconds(self): return self.has_expiration_time_seconds_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_filesystem()): self.set_filesystem(x.filesystem())
    if (x.has_content_type()): self.set_content_type(x.content_type())
    if (x.has_filename()): self.set_filename(x.filename())
    for i in xrange(x.parameters_size()): self.add_parameters().CopyFrom(x.parameters(i))
    if (x.has_expiration_time_seconds()): self.set_expiration_time_seconds(x.expiration_time_seconds())

  def Equals(self, x):
    if x is self: return 1
    if self.has_filesystem_ != x.has_filesystem_: return 0
    if self.has_filesystem_ and self.filesystem_ != x.filesystem_: return 0
    if self.has_content_type_ != x.has_content_type_: return 0
    if self.has_content_type_ and self.content_type_ != x.content_type_: return 0
    if self.has_filename_ != x.has_filename_: return 0
    if self.has_filename_ and self.filename_ != x.filename_: return 0
    if len(self.parameters_) != len(x.parameters_): return 0
    for e1, e2 in zip(self.parameters_, x.parameters_):
      if e1 != e2: return 0
    if self.has_expiration_time_seconds_ != x.has_expiration_time_seconds_: return 0
    if self.has_expiration_time_seconds_ and self.expiration_time_seconds_ != x.expiration_time_seconds_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_filesystem_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: filesystem not set.')
    if (not self.has_content_type_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: content_type not set.')
    for p in self.parameters_:
      if not p.IsInitialized(debug_strs): initialized=0
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.filesystem_))
    n += self.lengthVarInt64(self.content_type_)
    if (self.has_filename_): n += 1 + self.lengthString(len(self.filename_))
    n += 1 * len(self.parameters_)
    for i in xrange(len(self.parameters_)): n += self.lengthString(self.parameters_[i].ByteSize())
    if (self.has_expiration_time_seconds_): n += 1 + self.lengthVarInt64(self.expiration_time_seconds_)
    return n + 2

  def ByteSizePartial(self):
    n = 0
    if (self.has_filesystem_):
      n += 1
      n += self.lengthString(len(self.filesystem_))
    if (self.has_content_type_):
      n += 1
      n += self.lengthVarInt64(self.content_type_)
    if (self.has_filename_): n += 1 + self.lengthString(len(self.filename_))
    n += 1 * len(self.parameters_)
    for i in xrange(len(self.parameters_)): n += self.lengthString(self.parameters_[i].ByteSizePartial())
    if (self.has_expiration_time_seconds_): n += 1 + self.lengthVarInt64(self.expiration_time_seconds_)
    return n

  def Clear(self):
    self.clear_filesystem()
    self.clear_content_type()
    self.clear_filename()
    self.clear_parameters()
    self.clear_expiration_time_seconds()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.filesystem_)
    out.putVarInt32(16)
    out.putVarInt32(self.content_type_)
    if (self.has_filename_):
      out.putVarInt32(26)
      out.putPrefixedString(self.filename_)
    for i in xrange(len(self.parameters_)):
      out.putVarInt32(34)
      out.putVarInt32(self.parameters_[i].ByteSize())
      self.parameters_[i].OutputUnchecked(out)
    if (self.has_expiration_time_seconds_):
      out.putVarInt32(40)
      out.putVarInt64(self.expiration_time_seconds_)

  def OutputPartial(self, out):
    if (self.has_filesystem_):
      out.putVarInt32(10)
      out.putPrefixedString(self.filesystem_)
    if (self.has_content_type_):
      out.putVarInt32(16)
      out.putVarInt32(self.content_type_)
    if (self.has_filename_):
      out.putVarInt32(26)
      out.putPrefixedString(self.filename_)
    for i in xrange(len(self.parameters_)):
      out.putVarInt32(34)
      out.putVarInt32(self.parameters_[i].ByteSizePartial())
      self.parameters_[i].OutputPartial(out)
    if (self.has_expiration_time_seconds_):
      out.putVarInt32(40)
      out.putVarInt64(self.expiration_time_seconds_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_filesystem(d.getPrefixedString())
        continue
      if tt == 16:
        self.set_content_type(d.getVarInt32())
        continue
      if tt == 26:
        self.set_filename(d.getPrefixedString())
        continue
      if tt == 34:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.add_parameters().TryMerge(tmp)
        continue
      if tt == 40:
        self.set_expiration_time_seconds(d.getVarInt64())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_filesystem_: res+=prefix+("filesystem: %s\n" % self.DebugFormatString(self.filesystem_))
    if self.has_content_type_: res+=prefix+("content_type: %s\n" % self.DebugFormatInt32(self.content_type_))
    if self.has_filename_: res+=prefix+("filename: %s\n" % self.DebugFormatString(self.filename_))
    cnt=0
    for e in self.parameters_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("parameters%s <\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
      cnt+=1
    if self.has_expiration_time_seconds_: res+=prefix+("expiration_time_seconds: %s\n" % self.DebugFormatInt64(self.expiration_time_seconds_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kfilesystem = 1
  kcontent_type = 2
  kfilename = 3
  kparameters = 4
  kexpiration_time_seconds = 5

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "filesystem",
    2: "content_type",
    3: "filename",
    4: "parameters",
    5: "expiration_time_seconds",
  }, 5)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.NUMERIC,
    3: ProtocolBuffer.Encoder.STRING,
    4: ProtocolBuffer.Encoder.STRING,
    5: ProtocolBuffer.Encoder.NUMERIC,
  }, 5, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class CreateResponse(ProtocolBuffer.ProtocolMessage):
  has_filename_ = 0
  filename_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def filename(self): return self.filename_

  def set_filename(self, x):
    self.has_filename_ = 1
    self.filename_ = x

  def clear_filename(self):
    if self.has_filename_:
      self.has_filename_ = 0
      self.filename_ = ""

  def has_filename(self): return self.has_filename_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_filename()): self.set_filename(x.filename())

  def Equals(self, x):
    if x is self: return 1
    if self.has_filename_ != x.has_filename_: return 0
    if self.has_filename_ and self.filename_ != x.filename_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_filename_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: filename not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.filename_))
    return n + 1

  def ByteSizePartial(self):
    n = 0
    if (self.has_filename_):
      n += 1
      n += self.lengthString(len(self.filename_))
    return n

  def Clear(self):
    self.clear_filename()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.filename_)

  def OutputPartial(self, out):
    if (self.has_filename_):
      out.putVarInt32(10)
      out.putPrefixedString(self.filename_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_filename(d.getPrefixedString())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_filename_: res+=prefix+("filename: %s\n" % self.DebugFormatString(self.filename_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kfilename = 1

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "filename",
  }, 1)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
  }, 1, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class OpenRequest(ProtocolBuffer.ProtocolMessage):


  APPEND       =    1
  READ         =    2

  _OpenMode_NAMES = {
    1: "APPEND",
    2: "READ",
  }

  def OpenMode_Name(cls, x): return cls._OpenMode_NAMES.get(x, "")
  OpenMode_Name = classmethod(OpenMode_Name)

  has_filename_ = 0
  filename_ = ""
  has_content_type_ = 0
  content_type_ = 0
  has_open_mode_ = 0
  open_mode_ = 0
  has_exclusive_lock_ = 0
  exclusive_lock_ = 0
  has_buffered_output_ = 0
  buffered_output_ = 0
  has_open_lease_time_seconds_ = 0
  open_lease_time_seconds_ = 30

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def filename(self): return self.filename_

  def set_filename(self, x):
    self.has_filename_ = 1
    self.filename_ = x

  def clear_filename(self):
    if self.has_filename_:
      self.has_filename_ = 0
      self.filename_ = ""

  def has_filename(self): return self.has_filename_

  def content_type(self): return self.content_type_

  def set_content_type(self, x):
    self.has_content_type_ = 1
    self.content_type_ = x

  def clear_content_type(self):
    if self.has_content_type_:
      self.has_content_type_ = 0
      self.content_type_ = 0

  def has_content_type(self): return self.has_content_type_

  def open_mode(self): return self.open_mode_

  def set_open_mode(self, x):
    self.has_open_mode_ = 1
    self.open_mode_ = x

  def clear_open_mode(self):
    if self.has_open_mode_:
      self.has_open_mode_ = 0
      self.open_mode_ = 0

  def has_open_mode(self): return self.has_open_mode_

  def exclusive_lock(self): return self.exclusive_lock_

  def set_exclusive_lock(self, x):
    self.has_exclusive_lock_ = 1
    self.exclusive_lock_ = x

  def clear_exclusive_lock(self):
    if self.has_exclusive_lock_:
      self.has_exclusive_lock_ = 0
      self.exclusive_lock_ = 0

  def has_exclusive_lock(self): return self.has_exclusive_lock_

  def buffered_output(self): return self.buffered_output_

  def set_buffered_output(self, x):
    self.has_buffered_output_ = 1
    self.buffered_output_ = x

  def clear_buffered_output(self):
    if self.has_buffered_output_:
      self.has_buffered_output_ = 0
      self.buffered_output_ = 0

  def has_buffered_output(self): return self.has_buffered_output_

  def open_lease_time_seconds(self): return self.open_lease_time_seconds_

  def set_open_lease_time_seconds(self, x):
    self.has_open_lease_time_seconds_ = 1
    self.open_lease_time_seconds_ = x

  def clear_open_lease_time_seconds(self):
    if self.has_open_lease_time_seconds_:
      self.has_open_lease_time_seconds_ = 0
      self.open_lease_time_seconds_ = 30

  def has_open_lease_time_seconds(self): return self.has_open_lease_time_seconds_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_filename()): self.set_filename(x.filename())
    if (x.has_content_type()): self.set_content_type(x.content_type())
    if (x.has_open_mode()): self.set_open_mode(x.open_mode())
    if (x.has_exclusive_lock()): self.set_exclusive_lock(x.exclusive_lock())
    if (x.has_buffered_output()): self.set_buffered_output(x.buffered_output())
    if (x.has_open_lease_time_seconds()): self.set_open_lease_time_seconds(x.open_lease_time_seconds())

  def Equals(self, x):
    if x is self: return 1
    if self.has_filename_ != x.has_filename_: return 0
    if self.has_filename_ and self.filename_ != x.filename_: return 0
    if self.has_content_type_ != x.has_content_type_: return 0
    if self.has_content_type_ and self.content_type_ != x.content_type_: return 0
    if self.has_open_mode_ != x.has_open_mode_: return 0
    if self.has_open_mode_ and self.open_mode_ != x.open_mode_: return 0
    if self.has_exclusive_lock_ != x.has_exclusive_lock_: return 0
    if self.has_exclusive_lock_ and self.exclusive_lock_ != x.exclusive_lock_: return 0
    if self.has_buffered_output_ != x.has_buffered_output_: return 0
    if self.has_buffered_output_ and self.buffered_output_ != x.buffered_output_: return 0
    if self.has_open_lease_time_seconds_ != x.has_open_lease_time_seconds_: return 0
    if self.has_open_lease_time_seconds_ and self.open_lease_time_seconds_ != x.open_lease_time_seconds_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_filename_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: filename not set.')
    if (not self.has_content_type_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: content_type not set.')
    if (not self.has_open_mode_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: open_mode not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.filename_))
    n += self.lengthVarInt64(self.content_type_)
    n += self.lengthVarInt64(self.open_mode_)
    if (self.has_exclusive_lock_): n += 2
    if (self.has_buffered_output_): n += 2
    if (self.has_open_lease_time_seconds_): n += 1 + self.lengthVarInt64(self.open_lease_time_seconds_)
    return n + 3

  def ByteSizePartial(self):
    n = 0
    if (self.has_filename_):
      n += 1
      n += self.lengthString(len(self.filename_))
    if (self.has_content_type_):
      n += 1
      n += self.lengthVarInt64(self.content_type_)
    if (self.has_open_mode_):
      n += 1
      n += self.lengthVarInt64(self.open_mode_)
    if (self.has_exclusive_lock_): n += 2
    if (self.has_buffered_output_): n += 2
    if (self.has_open_lease_time_seconds_): n += 1 + self.lengthVarInt64(self.open_lease_time_seconds_)
    return n

  def Clear(self):
    self.clear_filename()
    self.clear_content_type()
    self.clear_open_mode()
    self.clear_exclusive_lock()
    self.clear_buffered_output()
    self.clear_open_lease_time_seconds()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.filename_)
    out.putVarInt32(16)
    out.putVarInt32(self.content_type_)
    out.putVarInt32(24)
    out.putVarInt32(self.open_mode_)
    if (self.has_exclusive_lock_):
      out.putVarInt32(32)
      out.putBoolean(self.exclusive_lock_)
    if (self.has_buffered_output_):
      out.putVarInt32(40)
      out.putBoolean(self.buffered_output_)
    if (self.has_open_lease_time_seconds_):
      out.putVarInt32(48)
      out.putVarInt32(self.open_lease_time_seconds_)

  def OutputPartial(self, out):
    if (self.has_filename_):
      out.putVarInt32(10)
      out.putPrefixedString(self.filename_)
    if (self.has_content_type_):
      out.putVarInt32(16)
      out.putVarInt32(self.content_type_)
    if (self.has_open_mode_):
      out.putVarInt32(24)
      out.putVarInt32(self.open_mode_)
    if (self.has_exclusive_lock_):
      out.putVarInt32(32)
      out.putBoolean(self.exclusive_lock_)
    if (self.has_buffered_output_):
      out.putVarInt32(40)
      out.putBoolean(self.buffered_output_)
    if (self.has_open_lease_time_seconds_):
      out.putVarInt32(48)
      out.putVarInt32(self.open_lease_time_seconds_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_filename(d.getPrefixedString())
        continue
      if tt == 16:
        self.set_content_type(d.getVarInt32())
        continue
      if tt == 24:
        self.set_open_mode(d.getVarInt32())
        continue
      if tt == 32:
        self.set_exclusive_lock(d.getBoolean())
        continue
      if tt == 40:
        self.set_buffered_output(d.getBoolean())
        continue
      if tt == 48:
        self.set_open_lease_time_seconds(d.getVarInt32())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_filename_: res+=prefix+("filename: %s\n" % self.DebugFormatString(self.filename_))
    if self.has_content_type_: res+=prefix+("content_type: %s\n" % self.DebugFormatInt32(self.content_type_))
    if self.has_open_mode_: res+=prefix+("open_mode: %s\n" % self.DebugFormatInt32(self.open_mode_))
    if self.has_exclusive_lock_: res+=prefix+("exclusive_lock: %s\n" % self.DebugFormatBool(self.exclusive_lock_))
    if self.has_buffered_output_: res+=prefix+("buffered_output: %s\n" % self.DebugFormatBool(self.buffered_output_))
    if self.has_open_lease_time_seconds_: res+=prefix+("open_lease_time_seconds: %s\n" % self.DebugFormatInt32(self.open_lease_time_seconds_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kfilename = 1
  kcontent_type = 2
  kopen_mode = 3
  kexclusive_lock = 4
  kbuffered_output = 5
  kopen_lease_time_seconds = 6

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "filename",
    2: "content_type",
    3: "open_mode",
    4: "exclusive_lock",
    5: "buffered_output",
    6: "open_lease_time_seconds",
  }, 6)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.NUMERIC,
    3: ProtocolBuffer.Encoder.NUMERIC,
    4: ProtocolBuffer.Encoder.NUMERIC,
    5: ProtocolBuffer.Encoder.NUMERIC,
    6: ProtocolBuffer.Encoder.NUMERIC,
  }, 6, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class OpenResponse(ProtocolBuffer.ProtocolMessage):

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
class CloseRequest(ProtocolBuffer.ProtocolMessage):
  has_filename_ = 0
  filename_ = ""
  has_finalize_ = 0
  finalize_ = 0

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def filename(self): return self.filename_

  def set_filename(self, x):
    self.has_filename_ = 1
    self.filename_ = x

  def clear_filename(self):
    if self.has_filename_:
      self.has_filename_ = 0
      self.filename_ = ""

  def has_filename(self): return self.has_filename_

  def finalize(self): return self.finalize_

  def set_finalize(self, x):
    self.has_finalize_ = 1
    self.finalize_ = x

  def clear_finalize(self):
    if self.has_finalize_:
      self.has_finalize_ = 0
      self.finalize_ = 0

  def has_finalize(self): return self.has_finalize_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_filename()): self.set_filename(x.filename())
    if (x.has_finalize()): self.set_finalize(x.finalize())

  def Equals(self, x):
    if x is self: return 1
    if self.has_filename_ != x.has_filename_: return 0
    if self.has_filename_ and self.filename_ != x.filename_: return 0
    if self.has_finalize_ != x.has_finalize_: return 0
    if self.has_finalize_ and self.finalize_ != x.finalize_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_filename_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: filename not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.filename_))
    if (self.has_finalize_): n += 2
    return n + 1

  def ByteSizePartial(self):
    n = 0
    if (self.has_filename_):
      n += 1
      n += self.lengthString(len(self.filename_))
    if (self.has_finalize_): n += 2
    return n

  def Clear(self):
    self.clear_filename()
    self.clear_finalize()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.filename_)
    if (self.has_finalize_):
      out.putVarInt32(16)
      out.putBoolean(self.finalize_)

  def OutputPartial(self, out):
    if (self.has_filename_):
      out.putVarInt32(10)
      out.putPrefixedString(self.filename_)
    if (self.has_finalize_):
      out.putVarInt32(16)
      out.putBoolean(self.finalize_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_filename(d.getPrefixedString())
        continue
      if tt == 16:
        self.set_finalize(d.getBoolean())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_filename_: res+=prefix+("filename: %s\n" % self.DebugFormatString(self.filename_))
    if self.has_finalize_: res+=prefix+("finalize: %s\n" % self.DebugFormatBool(self.finalize_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kfilename = 1
  kfinalize = 2

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "filename",
    2: "finalize",
  }, 2)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.NUMERIC,
  }, 2, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class CloseResponse(ProtocolBuffer.ProtocolMessage):

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
class FileStat(ProtocolBuffer.ProtocolMessage):
  has_filename_ = 0
  filename_ = ""
  has_content_type_ = 0
  content_type_ = 0
  has_finalized_ = 0
  finalized_ = 0
  has_length_ = 0
  length_ = 0
  has_ctime_ = 0
  ctime_ = 0
  has_mtime_ = 0
  mtime_ = 0

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def filename(self): return self.filename_

  def set_filename(self, x):
    self.has_filename_ = 1
    self.filename_ = x

  def clear_filename(self):
    if self.has_filename_:
      self.has_filename_ = 0
      self.filename_ = ""

  def has_filename(self): return self.has_filename_

  def content_type(self): return self.content_type_

  def set_content_type(self, x):
    self.has_content_type_ = 1
    self.content_type_ = x

  def clear_content_type(self):
    if self.has_content_type_:
      self.has_content_type_ = 0
      self.content_type_ = 0

  def has_content_type(self): return self.has_content_type_

  def finalized(self): return self.finalized_

  def set_finalized(self, x):
    self.has_finalized_ = 1
    self.finalized_ = x

  def clear_finalized(self):
    if self.has_finalized_:
      self.has_finalized_ = 0
      self.finalized_ = 0

  def has_finalized(self): return self.has_finalized_

  def length(self): return self.length_

  def set_length(self, x):
    self.has_length_ = 1
    self.length_ = x

  def clear_length(self):
    if self.has_length_:
      self.has_length_ = 0
      self.length_ = 0

  def has_length(self): return self.has_length_

  def ctime(self): return self.ctime_

  def set_ctime(self, x):
    self.has_ctime_ = 1
    self.ctime_ = x

  def clear_ctime(self):
    if self.has_ctime_:
      self.has_ctime_ = 0
      self.ctime_ = 0

  def has_ctime(self): return self.has_ctime_

  def mtime(self): return self.mtime_

  def set_mtime(self, x):
    self.has_mtime_ = 1
    self.mtime_ = x

  def clear_mtime(self):
    if self.has_mtime_:
      self.has_mtime_ = 0
      self.mtime_ = 0

  def has_mtime(self): return self.has_mtime_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_filename()): self.set_filename(x.filename())
    if (x.has_content_type()): self.set_content_type(x.content_type())
    if (x.has_finalized()): self.set_finalized(x.finalized())
    if (x.has_length()): self.set_length(x.length())
    if (x.has_ctime()): self.set_ctime(x.ctime())
    if (x.has_mtime()): self.set_mtime(x.mtime())

  def Equals(self, x):
    if x is self: return 1
    if self.has_filename_ != x.has_filename_: return 0
    if self.has_filename_ and self.filename_ != x.filename_: return 0
    if self.has_content_type_ != x.has_content_type_: return 0
    if self.has_content_type_ and self.content_type_ != x.content_type_: return 0
    if self.has_finalized_ != x.has_finalized_: return 0
    if self.has_finalized_ and self.finalized_ != x.finalized_: return 0
    if self.has_length_ != x.has_length_: return 0
    if self.has_length_ and self.length_ != x.length_: return 0
    if self.has_ctime_ != x.has_ctime_: return 0
    if self.has_ctime_ and self.ctime_ != x.ctime_: return 0
    if self.has_mtime_ != x.has_mtime_: return 0
    if self.has_mtime_ and self.mtime_ != x.mtime_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_filename_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: filename not set.')
    if (not self.has_content_type_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: content_type not set.')
    if (not self.has_finalized_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: finalized not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.filename_))
    n += self.lengthVarInt64(self.content_type_)
    if (self.has_length_): n += 1 + self.lengthVarInt64(self.length_)
    if (self.has_ctime_): n += 1 + self.lengthVarInt64(self.ctime_)
    if (self.has_mtime_): n += 1 + self.lengthVarInt64(self.mtime_)
    return n + 4

  def ByteSizePartial(self):
    n = 0
    if (self.has_filename_):
      n += 1
      n += self.lengthString(len(self.filename_))
    if (self.has_content_type_):
      n += 1
      n += self.lengthVarInt64(self.content_type_)
    if (self.has_finalized_):
      n += 2
    if (self.has_length_): n += 1 + self.lengthVarInt64(self.length_)
    if (self.has_ctime_): n += 1 + self.lengthVarInt64(self.ctime_)
    if (self.has_mtime_): n += 1 + self.lengthVarInt64(self.mtime_)
    return n

  def Clear(self):
    self.clear_filename()
    self.clear_content_type()
    self.clear_finalized()
    self.clear_length()
    self.clear_ctime()
    self.clear_mtime()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.filename_)
    out.putVarInt32(16)
    out.putVarInt32(self.content_type_)
    out.putVarInt32(24)
    out.putBoolean(self.finalized_)
    if (self.has_length_):
      out.putVarInt32(32)
      out.putVarInt64(self.length_)
    if (self.has_ctime_):
      out.putVarInt32(40)
      out.putVarInt64(self.ctime_)
    if (self.has_mtime_):
      out.putVarInt32(48)
      out.putVarInt64(self.mtime_)

  def OutputPartial(self, out):
    if (self.has_filename_):
      out.putVarInt32(10)
      out.putPrefixedString(self.filename_)
    if (self.has_content_type_):
      out.putVarInt32(16)
      out.putVarInt32(self.content_type_)
    if (self.has_finalized_):
      out.putVarInt32(24)
      out.putBoolean(self.finalized_)
    if (self.has_length_):
      out.putVarInt32(32)
      out.putVarInt64(self.length_)
    if (self.has_ctime_):
      out.putVarInt32(40)
      out.putVarInt64(self.ctime_)
    if (self.has_mtime_):
      out.putVarInt32(48)
      out.putVarInt64(self.mtime_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_filename(d.getPrefixedString())
        continue
      if tt == 16:
        self.set_content_type(d.getVarInt32())
        continue
      if tt == 24:
        self.set_finalized(d.getBoolean())
        continue
      if tt == 32:
        self.set_length(d.getVarInt64())
        continue
      if tt == 40:
        self.set_ctime(d.getVarInt64())
        continue
      if tt == 48:
        self.set_mtime(d.getVarInt64())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_filename_: res+=prefix+("filename: %s\n" % self.DebugFormatString(self.filename_))
    if self.has_content_type_: res+=prefix+("content_type: %s\n" % self.DebugFormatInt32(self.content_type_))
    if self.has_finalized_: res+=prefix+("finalized: %s\n" % self.DebugFormatBool(self.finalized_))
    if self.has_length_: res+=prefix+("length: %s\n" % self.DebugFormatInt64(self.length_))
    if self.has_ctime_: res+=prefix+("ctime: %s\n" % self.DebugFormatInt64(self.ctime_))
    if self.has_mtime_: res+=prefix+("mtime: %s\n" % self.DebugFormatInt64(self.mtime_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kfilename = 1
  kcontent_type = 2
  kfinalized = 3
  klength = 4
  kctime = 5
  kmtime = 6

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "filename",
    2: "content_type",
    3: "finalized",
    4: "length",
    5: "ctime",
    6: "mtime",
  }, 6)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.NUMERIC,
    3: ProtocolBuffer.Encoder.NUMERIC,
    4: ProtocolBuffer.Encoder.NUMERIC,
    5: ProtocolBuffer.Encoder.NUMERIC,
    6: ProtocolBuffer.Encoder.NUMERIC,
  }, 6, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class StatRequest(ProtocolBuffer.ProtocolMessage):
  has_filename_ = 0
  filename_ = ""
  has_file_glob_ = 0
  file_glob_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def filename(self): return self.filename_

  def set_filename(self, x):
    self.has_filename_ = 1
    self.filename_ = x

  def clear_filename(self):
    if self.has_filename_:
      self.has_filename_ = 0
      self.filename_ = ""

  def has_filename(self): return self.has_filename_

  def file_glob(self): return self.file_glob_

  def set_file_glob(self, x):
    self.has_file_glob_ = 1
    self.file_glob_ = x

  def clear_file_glob(self):
    if self.has_file_glob_:
      self.has_file_glob_ = 0
      self.file_glob_ = ""

  def has_file_glob(self): return self.has_file_glob_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_filename()): self.set_filename(x.filename())
    if (x.has_file_glob()): self.set_file_glob(x.file_glob())

  def Equals(self, x):
    if x is self: return 1
    if self.has_filename_ != x.has_filename_: return 0
    if self.has_filename_ and self.filename_ != x.filename_: return 0
    if self.has_file_glob_ != x.has_file_glob_: return 0
    if self.has_file_glob_ and self.file_glob_ != x.file_glob_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    return initialized

  def ByteSize(self):
    n = 0
    if (self.has_filename_): n += 1 + self.lengthString(len(self.filename_))
    if (self.has_file_glob_): n += 1 + self.lengthString(len(self.file_glob_))
    return n

  def ByteSizePartial(self):
    n = 0
    if (self.has_filename_): n += 1 + self.lengthString(len(self.filename_))
    if (self.has_file_glob_): n += 1 + self.lengthString(len(self.file_glob_))
    return n

  def Clear(self):
    self.clear_filename()
    self.clear_file_glob()

  def OutputUnchecked(self, out):
    if (self.has_filename_):
      out.putVarInt32(10)
      out.putPrefixedString(self.filename_)
    if (self.has_file_glob_):
      out.putVarInt32(18)
      out.putPrefixedString(self.file_glob_)

  def OutputPartial(self, out):
    if (self.has_filename_):
      out.putVarInt32(10)
      out.putPrefixedString(self.filename_)
    if (self.has_file_glob_):
      out.putVarInt32(18)
      out.putPrefixedString(self.file_glob_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_filename(d.getPrefixedString())
        continue
      if tt == 18:
        self.set_file_glob(d.getPrefixedString())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_filename_: res+=prefix+("filename: %s\n" % self.DebugFormatString(self.filename_))
    if self.has_file_glob_: res+=prefix+("file_glob: %s\n" % self.DebugFormatString(self.file_glob_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kfilename = 1
  kfile_glob = 2

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "filename",
    2: "file_glob",
  }, 2)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.STRING,
  }, 2, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class StatResponse(ProtocolBuffer.ProtocolMessage):
  has_more_files_found_ = 0
  more_files_found_ = 0

  def __init__(self, contents=None):
    self.stat_ = []
    if contents is not None: self.MergeFromString(contents)

  def stat_size(self): return len(self.stat_)
  def stat_list(self): return self.stat_

  def stat(self, i):
    return self.stat_[i]

  def mutable_stat(self, i):
    return self.stat_[i]

  def add_stat(self):
    x = FileStat()
    self.stat_.append(x)
    return x

  def clear_stat(self):
    self.stat_ = []
  def more_files_found(self): return self.more_files_found_

  def set_more_files_found(self, x):
    self.has_more_files_found_ = 1
    self.more_files_found_ = x

  def clear_more_files_found(self):
    if self.has_more_files_found_:
      self.has_more_files_found_ = 0
      self.more_files_found_ = 0

  def has_more_files_found(self): return self.has_more_files_found_


  def MergeFrom(self, x):
    assert x is not self
    for i in xrange(x.stat_size()): self.add_stat().CopyFrom(x.stat(i))
    if (x.has_more_files_found()): self.set_more_files_found(x.more_files_found())

  def Equals(self, x):
    if x is self: return 1
    if len(self.stat_) != len(x.stat_): return 0
    for e1, e2 in zip(self.stat_, x.stat_):
      if e1 != e2: return 0
    if self.has_more_files_found_ != x.has_more_files_found_: return 0
    if self.has_more_files_found_ and self.more_files_found_ != x.more_files_found_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    for p in self.stat_:
      if not p.IsInitialized(debug_strs): initialized=0
    if (not self.has_more_files_found_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: more_files_found not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += 1 * len(self.stat_)
    for i in xrange(len(self.stat_)): n += self.lengthString(self.stat_[i].ByteSize())
    return n + 2

  def ByteSizePartial(self):
    n = 0
    n += 1 * len(self.stat_)
    for i in xrange(len(self.stat_)): n += self.lengthString(self.stat_[i].ByteSizePartial())
    if (self.has_more_files_found_):
      n += 2
    return n

  def Clear(self):
    self.clear_stat()
    self.clear_more_files_found()

  def OutputUnchecked(self, out):
    for i in xrange(len(self.stat_)):
      out.putVarInt32(10)
      out.putVarInt32(self.stat_[i].ByteSize())
      self.stat_[i].OutputUnchecked(out)
    out.putVarInt32(16)
    out.putBoolean(self.more_files_found_)

  def OutputPartial(self, out):
    for i in xrange(len(self.stat_)):
      out.putVarInt32(10)
      out.putVarInt32(self.stat_[i].ByteSizePartial())
      self.stat_[i].OutputPartial(out)
    if (self.has_more_files_found_):
      out.putVarInt32(16)
      out.putBoolean(self.more_files_found_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.add_stat().TryMerge(tmp)
        continue
      if tt == 16:
        self.set_more_files_found(d.getBoolean())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    cnt=0
    for e in self.stat_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("stat%s <\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
      cnt+=1
    if self.has_more_files_found_: res+=prefix+("more_files_found: %s\n" % self.DebugFormatBool(self.more_files_found_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kstat = 1
  kmore_files_found = 2

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "stat",
    2: "more_files_found",
  }, 2)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.NUMERIC,
  }, 2, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class AppendRequest(ProtocolBuffer.ProtocolMessage):
  has_filename_ = 0
  filename_ = ""
  has_data_ = 0
  data_ = ""
  has_sequence_key_ = 0
  sequence_key_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def filename(self): return self.filename_

  def set_filename(self, x):
    self.has_filename_ = 1
    self.filename_ = x

  def clear_filename(self):
    if self.has_filename_:
      self.has_filename_ = 0
      self.filename_ = ""

  def has_filename(self): return self.has_filename_

  def data(self): return self.data_

  def set_data(self, x):
    self.has_data_ = 1
    self.data_ = x

  def clear_data(self):
    if self.has_data_:
      self.has_data_ = 0
      self.data_ = ""

  def has_data(self): return self.has_data_

  def sequence_key(self): return self.sequence_key_

  def set_sequence_key(self, x):
    self.has_sequence_key_ = 1
    self.sequence_key_ = x

  def clear_sequence_key(self):
    if self.has_sequence_key_:
      self.has_sequence_key_ = 0
      self.sequence_key_ = ""

  def has_sequence_key(self): return self.has_sequence_key_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_filename()): self.set_filename(x.filename())
    if (x.has_data()): self.set_data(x.data())
    if (x.has_sequence_key()): self.set_sequence_key(x.sequence_key())

  def Equals(self, x):
    if x is self: return 1
    if self.has_filename_ != x.has_filename_: return 0
    if self.has_filename_ and self.filename_ != x.filename_: return 0
    if self.has_data_ != x.has_data_: return 0
    if self.has_data_ and self.data_ != x.data_: return 0
    if self.has_sequence_key_ != x.has_sequence_key_: return 0
    if self.has_sequence_key_ and self.sequence_key_ != x.sequence_key_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_filename_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: filename not set.')
    if (not self.has_data_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: data not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.filename_))
    n += self.lengthString(len(self.data_))
    if (self.has_sequence_key_): n += 1 + self.lengthString(len(self.sequence_key_))
    return n + 2

  def ByteSizePartial(self):
    n = 0
    if (self.has_filename_):
      n += 1
      n += self.lengthString(len(self.filename_))
    if (self.has_data_):
      n += 1
      n += self.lengthString(len(self.data_))
    if (self.has_sequence_key_): n += 1 + self.lengthString(len(self.sequence_key_))
    return n

  def Clear(self):
    self.clear_filename()
    self.clear_data()
    self.clear_sequence_key()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.filename_)
    out.putVarInt32(18)
    out.putPrefixedString(self.data_)
    if (self.has_sequence_key_):
      out.putVarInt32(26)
      out.putPrefixedString(self.sequence_key_)

  def OutputPartial(self, out):
    if (self.has_filename_):
      out.putVarInt32(10)
      out.putPrefixedString(self.filename_)
    if (self.has_data_):
      out.putVarInt32(18)
      out.putPrefixedString(self.data_)
    if (self.has_sequence_key_):
      out.putVarInt32(26)
      out.putPrefixedString(self.sequence_key_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_filename(d.getPrefixedString())
        continue
      if tt == 18:
        self.set_data(d.getPrefixedString())
        continue
      if tt == 26:
        self.set_sequence_key(d.getPrefixedString())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_filename_: res+=prefix+("filename: %s\n" % self.DebugFormatString(self.filename_))
    if self.has_data_: res+=prefix+("data: %s\n" % self.DebugFormatString(self.data_))
    if self.has_sequence_key_: res+=prefix+("sequence_key: %s\n" % self.DebugFormatString(self.sequence_key_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kfilename = 1
  kdata = 2
  ksequence_key = 3

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "filename",
    2: "data",
    3: "sequence_key",
  }, 3)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.STRING,
    3: ProtocolBuffer.Encoder.STRING,
  }, 3, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class AppendResponse(ProtocolBuffer.ProtocolMessage):

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
class AppendKeyValueRequest(ProtocolBuffer.ProtocolMessage):
  has_filename_ = 0
  filename_ = ""
  has_key_ = 0
  key_ = ""
  has_value_ = 0
  value_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def filename(self): return self.filename_

  def set_filename(self, x):
    self.has_filename_ = 1
    self.filename_ = x

  def clear_filename(self):
    if self.has_filename_:
      self.has_filename_ = 0
      self.filename_ = ""

  def has_filename(self): return self.has_filename_

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
    if (x.has_filename()): self.set_filename(x.filename())
    if (x.has_key()): self.set_key(x.key())
    if (x.has_value()): self.set_value(x.value())

  def Equals(self, x):
    if x is self: return 1
    if self.has_filename_ != x.has_filename_: return 0
    if self.has_filename_ and self.filename_ != x.filename_: return 0
    if self.has_key_ != x.has_key_: return 0
    if self.has_key_ and self.key_ != x.key_: return 0
    if self.has_value_ != x.has_value_: return 0
    if self.has_value_ and self.value_ != x.value_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_filename_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: filename not set.')
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
    n += self.lengthString(len(self.filename_))
    n += self.lengthString(len(self.key_))
    n += self.lengthString(len(self.value_))
    return n + 3

  def ByteSizePartial(self):
    n = 0
    if (self.has_filename_):
      n += 1
      n += self.lengthString(len(self.filename_))
    if (self.has_key_):
      n += 1
      n += self.lengthString(len(self.key_))
    if (self.has_value_):
      n += 1
      n += self.lengthString(len(self.value_))
    return n

  def Clear(self):
    self.clear_filename()
    self.clear_key()
    self.clear_value()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.filename_)
    out.putVarInt32(18)
    out.putPrefixedString(self.key_)
    out.putVarInt32(26)
    out.putPrefixedString(self.value_)

  def OutputPartial(self, out):
    if (self.has_filename_):
      out.putVarInt32(10)
      out.putPrefixedString(self.filename_)
    if (self.has_key_):
      out.putVarInt32(18)
      out.putPrefixedString(self.key_)
    if (self.has_value_):
      out.putVarInt32(26)
      out.putPrefixedString(self.value_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_filename(d.getPrefixedString())
        continue
      if tt == 18:
        self.set_key(d.getPrefixedString())
        continue
      if tt == 26:
        self.set_value(d.getPrefixedString())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_filename_: res+=prefix+("filename: %s\n" % self.DebugFormatString(self.filename_))
    if self.has_key_: res+=prefix+("key: %s\n" % self.DebugFormatString(self.key_))
    if self.has_value_: res+=prefix+("value: %s\n" % self.DebugFormatString(self.value_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kfilename = 1
  kkey = 2
  kvalue = 3

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "filename",
    2: "key",
    3: "value",
  }, 3)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.STRING,
    3: ProtocolBuffer.Encoder.STRING,
  }, 3, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class AppendKeyValueResponse(ProtocolBuffer.ProtocolMessage):

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
class DeleteRequest(ProtocolBuffer.ProtocolMessage):
  has_filename_ = 0
  filename_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def filename(self): return self.filename_

  def set_filename(self, x):
    self.has_filename_ = 1
    self.filename_ = x

  def clear_filename(self):
    if self.has_filename_:
      self.has_filename_ = 0
      self.filename_ = ""

  def has_filename(self): return self.has_filename_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_filename()): self.set_filename(x.filename())

  def Equals(self, x):
    if x is self: return 1
    if self.has_filename_ != x.has_filename_: return 0
    if self.has_filename_ and self.filename_ != x.filename_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_filename_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: filename not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.filename_))
    return n + 1

  def ByteSizePartial(self):
    n = 0
    if (self.has_filename_):
      n += 1
      n += self.lengthString(len(self.filename_))
    return n

  def Clear(self):
    self.clear_filename()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.filename_)

  def OutputPartial(self, out):
    if (self.has_filename_):
      out.putVarInt32(10)
      out.putPrefixedString(self.filename_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_filename(d.getPrefixedString())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_filename_: res+=prefix+("filename: %s\n" % self.DebugFormatString(self.filename_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kfilename = 1

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "filename",
  }, 1)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
  }, 1, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class DeleteResponse(ProtocolBuffer.ProtocolMessage):

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
class ReadRequest(ProtocolBuffer.ProtocolMessage):
  has_filename_ = 0
  filename_ = ""
  has_pos_ = 0
  pos_ = 0
  has_max_bytes_ = 0
  max_bytes_ = 0

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def filename(self): return self.filename_

  def set_filename(self, x):
    self.has_filename_ = 1
    self.filename_ = x

  def clear_filename(self):
    if self.has_filename_:
      self.has_filename_ = 0
      self.filename_ = ""

  def has_filename(self): return self.has_filename_

  def pos(self): return self.pos_

  def set_pos(self, x):
    self.has_pos_ = 1
    self.pos_ = x

  def clear_pos(self):
    if self.has_pos_:
      self.has_pos_ = 0
      self.pos_ = 0

  def has_pos(self): return self.has_pos_

  def max_bytes(self): return self.max_bytes_

  def set_max_bytes(self, x):
    self.has_max_bytes_ = 1
    self.max_bytes_ = x

  def clear_max_bytes(self):
    if self.has_max_bytes_:
      self.has_max_bytes_ = 0
      self.max_bytes_ = 0

  def has_max_bytes(self): return self.has_max_bytes_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_filename()): self.set_filename(x.filename())
    if (x.has_pos()): self.set_pos(x.pos())
    if (x.has_max_bytes()): self.set_max_bytes(x.max_bytes())

  def Equals(self, x):
    if x is self: return 1
    if self.has_filename_ != x.has_filename_: return 0
    if self.has_filename_ and self.filename_ != x.filename_: return 0
    if self.has_pos_ != x.has_pos_: return 0
    if self.has_pos_ and self.pos_ != x.pos_: return 0
    if self.has_max_bytes_ != x.has_max_bytes_: return 0
    if self.has_max_bytes_ and self.max_bytes_ != x.max_bytes_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_filename_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: filename not set.')
    if (not self.has_pos_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: pos not set.')
    if (not self.has_max_bytes_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: max_bytes not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.filename_))
    n += self.lengthVarInt64(self.pos_)
    n += self.lengthVarInt64(self.max_bytes_)
    return n + 3

  def ByteSizePartial(self):
    n = 0
    if (self.has_filename_):
      n += 1
      n += self.lengthString(len(self.filename_))
    if (self.has_pos_):
      n += 1
      n += self.lengthVarInt64(self.pos_)
    if (self.has_max_bytes_):
      n += 1
      n += self.lengthVarInt64(self.max_bytes_)
    return n

  def Clear(self):
    self.clear_filename()
    self.clear_pos()
    self.clear_max_bytes()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.filename_)
    out.putVarInt32(16)
    out.putVarInt64(self.pos_)
    out.putVarInt32(24)
    out.putVarInt64(self.max_bytes_)

  def OutputPartial(self, out):
    if (self.has_filename_):
      out.putVarInt32(10)
      out.putPrefixedString(self.filename_)
    if (self.has_pos_):
      out.putVarInt32(16)
      out.putVarInt64(self.pos_)
    if (self.has_max_bytes_):
      out.putVarInt32(24)
      out.putVarInt64(self.max_bytes_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_filename(d.getPrefixedString())
        continue
      if tt == 16:
        self.set_pos(d.getVarInt64())
        continue
      if tt == 24:
        self.set_max_bytes(d.getVarInt64())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_filename_: res+=prefix+("filename: %s\n" % self.DebugFormatString(self.filename_))
    if self.has_pos_: res+=prefix+("pos: %s\n" % self.DebugFormatInt64(self.pos_))
    if self.has_max_bytes_: res+=prefix+("max_bytes: %s\n" % self.DebugFormatInt64(self.max_bytes_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kfilename = 1
  kpos = 2
  kmax_bytes = 3

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "filename",
    2: "pos",
    3: "max_bytes",
  }, 3)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.NUMERIC,
    3: ProtocolBuffer.Encoder.NUMERIC,
  }, 3, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class ReadResponse(ProtocolBuffer.ProtocolMessage):
  has_data_ = 0
  data_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def data(self): return self.data_

  def set_data(self, x):
    self.has_data_ = 1
    self.data_ = x

  def clear_data(self):
    if self.has_data_:
      self.has_data_ = 0
      self.data_ = ""

  def has_data(self): return self.has_data_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_data()): self.set_data(x.data())

  def Equals(self, x):
    if x is self: return 1
    if self.has_data_ != x.has_data_: return 0
    if self.has_data_ and self.data_ != x.data_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_data_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: data not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.data_))
    return n + 1

  def ByteSizePartial(self):
    n = 0
    if (self.has_data_):
      n += 1
      n += self.lengthString(len(self.data_))
    return n

  def Clear(self):
    self.clear_data()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.data_)

  def OutputPartial(self, out):
    if (self.has_data_):
      out.putVarInt32(10)
      out.putPrefixedString(self.data_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_data(d.getPrefixedString())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_data_: res+=prefix+("data: %s\n" % self.DebugFormatString(self.data_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kdata = 1

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "data",
  }, 1)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
  }, 1, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class ReadKeyValueRequest(ProtocolBuffer.ProtocolMessage):
  has_filename_ = 0
  filename_ = ""
  has_start_key_ = 0
  start_key_ = ""
  has_max_bytes_ = 0
  max_bytes_ = 0
  has_value_pos_ = 0
  value_pos_ = 0

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def filename(self): return self.filename_

  def set_filename(self, x):
    self.has_filename_ = 1
    self.filename_ = x

  def clear_filename(self):
    if self.has_filename_:
      self.has_filename_ = 0
      self.filename_ = ""

  def has_filename(self): return self.has_filename_

  def start_key(self): return self.start_key_

  def set_start_key(self, x):
    self.has_start_key_ = 1
    self.start_key_ = x

  def clear_start_key(self):
    if self.has_start_key_:
      self.has_start_key_ = 0
      self.start_key_ = ""

  def has_start_key(self): return self.has_start_key_

  def max_bytes(self): return self.max_bytes_

  def set_max_bytes(self, x):
    self.has_max_bytes_ = 1
    self.max_bytes_ = x

  def clear_max_bytes(self):
    if self.has_max_bytes_:
      self.has_max_bytes_ = 0
      self.max_bytes_ = 0

  def has_max_bytes(self): return self.has_max_bytes_

  def value_pos(self): return self.value_pos_

  def set_value_pos(self, x):
    self.has_value_pos_ = 1
    self.value_pos_ = x

  def clear_value_pos(self):
    if self.has_value_pos_:
      self.has_value_pos_ = 0
      self.value_pos_ = 0

  def has_value_pos(self): return self.has_value_pos_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_filename()): self.set_filename(x.filename())
    if (x.has_start_key()): self.set_start_key(x.start_key())
    if (x.has_max_bytes()): self.set_max_bytes(x.max_bytes())
    if (x.has_value_pos()): self.set_value_pos(x.value_pos())

  def Equals(self, x):
    if x is self: return 1
    if self.has_filename_ != x.has_filename_: return 0
    if self.has_filename_ and self.filename_ != x.filename_: return 0
    if self.has_start_key_ != x.has_start_key_: return 0
    if self.has_start_key_ and self.start_key_ != x.start_key_: return 0
    if self.has_max_bytes_ != x.has_max_bytes_: return 0
    if self.has_max_bytes_ and self.max_bytes_ != x.max_bytes_: return 0
    if self.has_value_pos_ != x.has_value_pos_: return 0
    if self.has_value_pos_ and self.value_pos_ != x.value_pos_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_filename_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: filename not set.')
    if (not self.has_start_key_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: start_key not set.')
    if (not self.has_max_bytes_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: max_bytes not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.filename_))
    n += self.lengthString(len(self.start_key_))
    n += self.lengthVarInt64(self.max_bytes_)
    if (self.has_value_pos_): n += 1 + self.lengthVarInt64(self.value_pos_)
    return n + 3

  def ByteSizePartial(self):
    n = 0
    if (self.has_filename_):
      n += 1
      n += self.lengthString(len(self.filename_))
    if (self.has_start_key_):
      n += 1
      n += self.lengthString(len(self.start_key_))
    if (self.has_max_bytes_):
      n += 1
      n += self.lengthVarInt64(self.max_bytes_)
    if (self.has_value_pos_): n += 1 + self.lengthVarInt64(self.value_pos_)
    return n

  def Clear(self):
    self.clear_filename()
    self.clear_start_key()
    self.clear_max_bytes()
    self.clear_value_pos()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.filename_)
    out.putVarInt32(18)
    out.putPrefixedString(self.start_key_)
    out.putVarInt32(24)
    out.putVarInt64(self.max_bytes_)
    if (self.has_value_pos_):
      out.putVarInt32(32)
      out.putVarInt64(self.value_pos_)

  def OutputPartial(self, out):
    if (self.has_filename_):
      out.putVarInt32(10)
      out.putPrefixedString(self.filename_)
    if (self.has_start_key_):
      out.putVarInt32(18)
      out.putPrefixedString(self.start_key_)
    if (self.has_max_bytes_):
      out.putVarInt32(24)
      out.putVarInt64(self.max_bytes_)
    if (self.has_value_pos_):
      out.putVarInt32(32)
      out.putVarInt64(self.value_pos_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_filename(d.getPrefixedString())
        continue
      if tt == 18:
        self.set_start_key(d.getPrefixedString())
        continue
      if tt == 24:
        self.set_max_bytes(d.getVarInt64())
        continue
      if tt == 32:
        self.set_value_pos(d.getVarInt64())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_filename_: res+=prefix+("filename: %s\n" % self.DebugFormatString(self.filename_))
    if self.has_start_key_: res+=prefix+("start_key: %s\n" % self.DebugFormatString(self.start_key_))
    if self.has_max_bytes_: res+=prefix+("max_bytes: %s\n" % self.DebugFormatInt64(self.max_bytes_))
    if self.has_value_pos_: res+=prefix+("value_pos: %s\n" % self.DebugFormatInt64(self.value_pos_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kfilename = 1
  kstart_key = 2
  kmax_bytes = 3
  kvalue_pos = 4

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "filename",
    2: "start_key",
    3: "max_bytes",
    4: "value_pos",
  }, 4)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.STRING,
    3: ProtocolBuffer.Encoder.NUMERIC,
    4: ProtocolBuffer.Encoder.NUMERIC,
  }, 4, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class ReadKeyValueResponse_KeyValue(ProtocolBuffer.ProtocolMessage):
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
class ReadKeyValueResponse(ProtocolBuffer.ProtocolMessage):
  has_next_key_ = 0
  next_key_ = ""
  has_truncated_value_ = 0
  truncated_value_ = 0

  def __init__(self, contents=None):
    self.data_ = []
    if contents is not None: self.MergeFromString(contents)

  def data_size(self): return len(self.data_)
  def data_list(self): return self.data_

  def data(self, i):
    return self.data_[i]

  def mutable_data(self, i):
    return self.data_[i]

  def add_data(self):
    x = ReadKeyValueResponse_KeyValue()
    self.data_.append(x)
    return x

  def clear_data(self):
    self.data_ = []
  def next_key(self): return self.next_key_

  def set_next_key(self, x):
    self.has_next_key_ = 1
    self.next_key_ = x

  def clear_next_key(self):
    if self.has_next_key_:
      self.has_next_key_ = 0
      self.next_key_ = ""

  def has_next_key(self): return self.has_next_key_

  def truncated_value(self): return self.truncated_value_

  def set_truncated_value(self, x):
    self.has_truncated_value_ = 1
    self.truncated_value_ = x

  def clear_truncated_value(self):
    if self.has_truncated_value_:
      self.has_truncated_value_ = 0
      self.truncated_value_ = 0

  def has_truncated_value(self): return self.has_truncated_value_


  def MergeFrom(self, x):
    assert x is not self
    for i in xrange(x.data_size()): self.add_data().CopyFrom(x.data(i))
    if (x.has_next_key()): self.set_next_key(x.next_key())
    if (x.has_truncated_value()): self.set_truncated_value(x.truncated_value())

  def Equals(self, x):
    if x is self: return 1
    if len(self.data_) != len(x.data_): return 0
    for e1, e2 in zip(self.data_, x.data_):
      if e1 != e2: return 0
    if self.has_next_key_ != x.has_next_key_: return 0
    if self.has_next_key_ and self.next_key_ != x.next_key_: return 0
    if self.has_truncated_value_ != x.has_truncated_value_: return 0
    if self.has_truncated_value_ and self.truncated_value_ != x.truncated_value_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    for p in self.data_:
      if not p.IsInitialized(debug_strs): initialized=0
    return initialized

  def ByteSize(self):
    n = 0
    n += 1 * len(self.data_)
    for i in xrange(len(self.data_)): n += self.lengthString(self.data_[i].ByteSize())
    if (self.has_next_key_): n += 1 + self.lengthString(len(self.next_key_))
    if (self.has_truncated_value_): n += 2
    return n

  def ByteSizePartial(self):
    n = 0
    n += 1 * len(self.data_)
    for i in xrange(len(self.data_)): n += self.lengthString(self.data_[i].ByteSizePartial())
    if (self.has_next_key_): n += 1 + self.lengthString(len(self.next_key_))
    if (self.has_truncated_value_): n += 2
    return n

  def Clear(self):
    self.clear_data()
    self.clear_next_key()
    self.clear_truncated_value()

  def OutputUnchecked(self, out):
    for i in xrange(len(self.data_)):
      out.putVarInt32(10)
      out.putVarInt32(self.data_[i].ByteSize())
      self.data_[i].OutputUnchecked(out)
    if (self.has_next_key_):
      out.putVarInt32(18)
      out.putPrefixedString(self.next_key_)
    if (self.has_truncated_value_):
      out.putVarInt32(24)
      out.putBoolean(self.truncated_value_)

  def OutputPartial(self, out):
    for i in xrange(len(self.data_)):
      out.putVarInt32(10)
      out.putVarInt32(self.data_[i].ByteSizePartial())
      self.data_[i].OutputPartial(out)
    if (self.has_next_key_):
      out.putVarInt32(18)
      out.putPrefixedString(self.next_key_)
    if (self.has_truncated_value_):
      out.putVarInt32(24)
      out.putBoolean(self.truncated_value_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.add_data().TryMerge(tmp)
        continue
      if tt == 18:
        self.set_next_key(d.getPrefixedString())
        continue
      if tt == 24:
        self.set_truncated_value(d.getBoolean())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    cnt=0
    for e in self.data_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("data%s <\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
      cnt+=1
    if self.has_next_key_: res+=prefix+("next_key: %s\n" % self.DebugFormatString(self.next_key_))
    if self.has_truncated_value_: res+=prefix+("truncated_value: %s\n" % self.DebugFormatBool(self.truncated_value_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kdata = 1
  knext_key = 2
  ktruncated_value = 3

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "data",
    2: "next_key",
    3: "truncated_value",
  }, 3)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.STRING,
    3: ProtocolBuffer.Encoder.NUMERIC,
  }, 3, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""

__all__ = ['FileServiceErrors','FileContentType','CreateRequest_Parameter','CreateRequest','CreateResponse','OpenRequest','OpenResponse','CloseRequest','CloseResponse','FileStat','StatRequest','StatResponse','AppendRequest','AppendResponse','AppendKeyValueRequest','AppendKeyValueResponse','DeleteRequest','DeleteResponse','ReadRequest','ReadResponse','ReadKeyValueRequest','ReadKeyValueResponse_KeyValue','ReadKeyValueResponse']
