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
class BlobstoreServiceError(ProtocolBuffer.ProtocolMessage):


  OK           =    0
  INTERNAL_ERROR =    1
  URL_TOO_LONG =    2
  PERMISSION_DENIED =    3
  BLOB_NOT_FOUND =    4
  DATA_INDEX_OUT_OF_RANGE =    5
  BLOB_FETCH_SIZE_TOO_LARGE =    6

  _ErrorCode_NAMES = {
    0: "OK",
    1: "INTERNAL_ERROR",
    2: "URL_TOO_LONG",
    3: "PERMISSION_DENIED",
    4: "BLOB_NOT_FOUND",
    5: "DATA_INDEX_OUT_OF_RANGE",
    6: "BLOB_FETCH_SIZE_TOO_LARGE",
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
class CreateUploadURLRequest(ProtocolBuffer.ProtocolMessage):
  has_success_path_ = 0
  success_path_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def success_path(self): return self.success_path_

  def set_success_path(self, x):
    self.has_success_path_ = 1
    self.success_path_ = x

  def clear_success_path(self):
    if self.has_success_path_:
      self.has_success_path_ = 0
      self.success_path_ = ""

  def has_success_path(self): return self.has_success_path_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_success_path()): self.set_success_path(x.success_path())

  def Equals(self, x):
    if x is self: return 1
    if self.has_success_path_ != x.has_success_path_: return 0
    if self.has_success_path_ and self.success_path_ != x.success_path_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_success_path_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: success_path not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.success_path_))
    return n + 1

  def ByteSizePartial(self):
    n = 0
    if (self.has_success_path_):
      n += 1
      n += self.lengthString(len(self.success_path_))
    return n

  def Clear(self):
    self.clear_success_path()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.success_path_)

  def OutputPartial(self, out):
    if (self.has_success_path_):
      out.putVarInt32(10)
      out.putPrefixedString(self.success_path_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_success_path(d.getPrefixedString())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_success_path_: res+=prefix+("success_path: %s\n" % self.DebugFormatString(self.success_path_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  ksuccess_path = 1

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "success_path",
  }, 1)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
  }, 1, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class CreateUploadURLResponse(ProtocolBuffer.ProtocolMessage):
  has_url_ = 0
  url_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def url(self): return self.url_

  def set_url(self, x):
    self.has_url_ = 1
    self.url_ = x

  def clear_url(self):
    if self.has_url_:
      self.has_url_ = 0
      self.url_ = ""

  def has_url(self): return self.has_url_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_url()): self.set_url(x.url())

  def Equals(self, x):
    if x is self: return 1
    if self.has_url_ != x.has_url_: return 0
    if self.has_url_ and self.url_ != x.url_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_url_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: url not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.url_))
    return n + 1

  def ByteSizePartial(self):
    n = 0
    if (self.has_url_):
      n += 1
      n += self.lengthString(len(self.url_))
    return n

  def Clear(self):
    self.clear_url()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.url_)

  def OutputPartial(self, out):
    if (self.has_url_):
      out.putVarInt32(10)
      out.putPrefixedString(self.url_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_url(d.getPrefixedString())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_url_: res+=prefix+("url: %s\n" % self.DebugFormatString(self.url_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kurl = 1

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "url",
  }, 1)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
  }, 1, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class DeleteBlobRequest(ProtocolBuffer.ProtocolMessage):

  def __init__(self, contents=None):
    self.blob_key_ = []
    if contents is not None: self.MergeFromString(contents)

  def blob_key_size(self): return len(self.blob_key_)
  def blob_key_list(self): return self.blob_key_

  def blob_key(self, i):
    return self.blob_key_[i]

  def set_blob_key(self, i, x):
    self.blob_key_[i] = x

  def add_blob_key(self, x):
    self.blob_key_.append(x)

  def clear_blob_key(self):
    self.blob_key_ = []


  def MergeFrom(self, x):
    assert x is not self
    for i in xrange(x.blob_key_size()): self.add_blob_key(x.blob_key(i))

  def Equals(self, x):
    if x is self: return 1
    if len(self.blob_key_) != len(x.blob_key_): return 0
    for e1, e2 in zip(self.blob_key_, x.blob_key_):
      if e1 != e2: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    return initialized

  def ByteSize(self):
    n = 0
    n += 1 * len(self.blob_key_)
    for i in xrange(len(self.blob_key_)): n += self.lengthString(len(self.blob_key_[i]))
    return n

  def ByteSizePartial(self):
    n = 0
    n += 1 * len(self.blob_key_)
    for i in xrange(len(self.blob_key_)): n += self.lengthString(len(self.blob_key_[i]))
    return n

  def Clear(self):
    self.clear_blob_key()

  def OutputUnchecked(self, out):
    for i in xrange(len(self.blob_key_)):
      out.putVarInt32(10)
      out.putPrefixedString(self.blob_key_[i])

  def OutputPartial(self, out):
    for i in xrange(len(self.blob_key_)):
      out.putVarInt32(10)
      out.putPrefixedString(self.blob_key_[i])

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.add_blob_key(d.getPrefixedString())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    cnt=0
    for e in self.blob_key_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("blob_key%s: %s\n" % (elm, self.DebugFormatString(e)))
      cnt+=1
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kblob_key = 1

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "blob_key",
  }, 1)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
  }, 1, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class FetchDataRequest(ProtocolBuffer.ProtocolMessage):
  has_blob_key_ = 0
  blob_key_ = ""
  has_start_index_ = 0
  start_index_ = 0
  has_end_index_ = 0
  end_index_ = 0

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def blob_key(self): return self.blob_key_

  def set_blob_key(self, x):
    self.has_blob_key_ = 1
    self.blob_key_ = x

  def clear_blob_key(self):
    if self.has_blob_key_:
      self.has_blob_key_ = 0
      self.blob_key_ = ""

  def has_blob_key(self): return self.has_blob_key_

  def start_index(self): return self.start_index_

  def set_start_index(self, x):
    self.has_start_index_ = 1
    self.start_index_ = x

  def clear_start_index(self):
    if self.has_start_index_:
      self.has_start_index_ = 0
      self.start_index_ = 0

  def has_start_index(self): return self.has_start_index_

  def end_index(self): return self.end_index_

  def set_end_index(self, x):
    self.has_end_index_ = 1
    self.end_index_ = x

  def clear_end_index(self):
    if self.has_end_index_:
      self.has_end_index_ = 0
      self.end_index_ = 0

  def has_end_index(self): return self.has_end_index_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_blob_key()): self.set_blob_key(x.blob_key())
    if (x.has_start_index()): self.set_start_index(x.start_index())
    if (x.has_end_index()): self.set_end_index(x.end_index())

  def Equals(self, x):
    if x is self: return 1
    if self.has_blob_key_ != x.has_blob_key_: return 0
    if self.has_blob_key_ and self.blob_key_ != x.blob_key_: return 0
    if self.has_start_index_ != x.has_start_index_: return 0
    if self.has_start_index_ and self.start_index_ != x.start_index_: return 0
    if self.has_end_index_ != x.has_end_index_: return 0
    if self.has_end_index_ and self.end_index_ != x.end_index_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_blob_key_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: blob_key not set.')
    if (not self.has_start_index_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: start_index not set.')
    if (not self.has_end_index_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: end_index not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.blob_key_))
    n += self.lengthVarInt64(self.start_index_)
    n += self.lengthVarInt64(self.end_index_)
    return n + 3

  def ByteSizePartial(self):
    n = 0
    if (self.has_blob_key_):
      n += 1
      n += self.lengthString(len(self.blob_key_))
    if (self.has_start_index_):
      n += 1
      n += self.lengthVarInt64(self.start_index_)
    if (self.has_end_index_):
      n += 1
      n += self.lengthVarInt64(self.end_index_)
    return n

  def Clear(self):
    self.clear_blob_key()
    self.clear_start_index()
    self.clear_end_index()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.blob_key_)
    out.putVarInt32(16)
    out.putVarInt64(self.start_index_)
    out.putVarInt32(24)
    out.putVarInt64(self.end_index_)

  def OutputPartial(self, out):
    if (self.has_blob_key_):
      out.putVarInt32(10)
      out.putPrefixedString(self.blob_key_)
    if (self.has_start_index_):
      out.putVarInt32(16)
      out.putVarInt64(self.start_index_)
    if (self.has_end_index_):
      out.putVarInt32(24)
      out.putVarInt64(self.end_index_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_blob_key(d.getPrefixedString())
        continue
      if tt == 16:
        self.set_start_index(d.getVarInt64())
        continue
      if tt == 24:
        self.set_end_index(d.getVarInt64())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_blob_key_: res+=prefix+("blob_key: %s\n" % self.DebugFormatString(self.blob_key_))
    if self.has_start_index_: res+=prefix+("start_index: %s\n" % self.DebugFormatInt64(self.start_index_))
    if self.has_end_index_: res+=prefix+("end_index: %s\n" % self.DebugFormatInt64(self.end_index_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kblob_key = 1
  kstart_index = 2
  kend_index = 3

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "blob_key",
    2: "start_index",
    3: "end_index",
  }, 3)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.NUMERIC,
    3: ProtocolBuffer.Encoder.NUMERIC,
  }, 3, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class FetchDataResponse(ProtocolBuffer.ProtocolMessage):
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
    return n + 2

  def ByteSizePartial(self):
    n = 0
    if (self.has_data_):
      n += 2
      n += self.lengthString(len(self.data_))
    return n

  def Clear(self):
    self.clear_data()

  def OutputUnchecked(self, out):
    out.putVarInt32(8002)
    out.putPrefixedString(self.data_)

  def OutputPartial(self, out):
    if (self.has_data_):
      out.putVarInt32(8002)
      out.putPrefixedString(self.data_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 8002:
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

  kdata = 1000

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1000: "data",
  }, 1000)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1000: ProtocolBuffer.Encoder.STRING,
  }, 1000, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class DecodeBlobKeyRequest(ProtocolBuffer.ProtocolMessage):

  def __init__(self, contents=None):
    self.blob_key_ = []
    if contents is not None: self.MergeFromString(contents)

  def blob_key_size(self): return len(self.blob_key_)
  def blob_key_list(self): return self.blob_key_

  def blob_key(self, i):
    return self.blob_key_[i]

  def set_blob_key(self, i, x):
    self.blob_key_[i] = x

  def add_blob_key(self, x):
    self.blob_key_.append(x)

  def clear_blob_key(self):
    self.blob_key_ = []


  def MergeFrom(self, x):
    assert x is not self
    for i in xrange(x.blob_key_size()): self.add_blob_key(x.blob_key(i))

  def Equals(self, x):
    if x is self: return 1
    if len(self.blob_key_) != len(x.blob_key_): return 0
    for e1, e2 in zip(self.blob_key_, x.blob_key_):
      if e1 != e2: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    return initialized

  def ByteSize(self):
    n = 0
    n += 1 * len(self.blob_key_)
    for i in xrange(len(self.blob_key_)): n += self.lengthString(len(self.blob_key_[i]))
    return n

  def ByteSizePartial(self):
    n = 0
    n += 1 * len(self.blob_key_)
    for i in xrange(len(self.blob_key_)): n += self.lengthString(len(self.blob_key_[i]))
    return n

  def Clear(self):
    self.clear_blob_key()

  def OutputUnchecked(self, out):
    for i in xrange(len(self.blob_key_)):
      out.putVarInt32(10)
      out.putPrefixedString(self.blob_key_[i])

  def OutputPartial(self, out):
    for i in xrange(len(self.blob_key_)):
      out.putVarInt32(10)
      out.putPrefixedString(self.blob_key_[i])

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.add_blob_key(d.getPrefixedString())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    cnt=0
    for e in self.blob_key_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("blob_key%s: %s\n" % (elm, self.DebugFormatString(e)))
      cnt+=1
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kblob_key = 1

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "blob_key",
  }, 1)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
  }, 1, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class DecodeBlobKeyResponse(ProtocolBuffer.ProtocolMessage):

  def __init__(self, contents=None):
    self.decoded_ = []
    if contents is not None: self.MergeFromString(contents)

  def decoded_size(self): return len(self.decoded_)
  def decoded_list(self): return self.decoded_

  def decoded(self, i):
    return self.decoded_[i]

  def set_decoded(self, i, x):
    self.decoded_[i] = x

  def add_decoded(self, x):
    self.decoded_.append(x)

  def clear_decoded(self):
    self.decoded_ = []


  def MergeFrom(self, x):
    assert x is not self
    for i in xrange(x.decoded_size()): self.add_decoded(x.decoded(i))

  def Equals(self, x):
    if x is self: return 1
    if len(self.decoded_) != len(x.decoded_): return 0
    for e1, e2 in zip(self.decoded_, x.decoded_):
      if e1 != e2: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    return initialized

  def ByteSize(self):
    n = 0
    n += 1 * len(self.decoded_)
    for i in xrange(len(self.decoded_)): n += self.lengthString(len(self.decoded_[i]))
    return n

  def ByteSizePartial(self):
    n = 0
    n += 1 * len(self.decoded_)
    for i in xrange(len(self.decoded_)): n += self.lengthString(len(self.decoded_[i]))
    return n

  def Clear(self):
    self.clear_decoded()

  def OutputUnchecked(self, out):
    for i in xrange(len(self.decoded_)):
      out.putVarInt32(10)
      out.putPrefixedString(self.decoded_[i])

  def OutputPartial(self, out):
    for i in xrange(len(self.decoded_)):
      out.putVarInt32(10)
      out.putPrefixedString(self.decoded_[i])

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.add_decoded(d.getPrefixedString())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    cnt=0
    for e in self.decoded_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("decoded%s: %s\n" % (elm, self.DebugFormatString(e)))
      cnt+=1
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kdecoded = 1

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "decoded",
  }, 1)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
  }, 1, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""

__all__ = ['BlobstoreServiceError','CreateUploadURLRequest','CreateUploadURLResponse','DeleteBlobRequest','FetchDataRequest','FetchDataResponse','DecodeBlobKeyRequest','DecodeBlobKeyResponse']
