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


import struct
import array
import string
import re
from google.pyglib.gexcept import AbstractMethod
import httplib
from string import strip, split
__all__ = ['ProtocolMessage', 'Encoder', 'Decoder',
           'ProtocolBufferDecodeError',
           'ProtocolBufferEncodeError',
           'ProtocolBufferReturnError']

URL_RE = re.compile('^(https?)://([^/]+)(/.*)$')

class ProtocolMessage:


  def __init__(self, contents=None):
    raise AbstractMethod

  def Clear(self):
    raise AbstractMethod

  def IsInitialized(self, debug_strs=None):
    raise AbstractMethod

  def Encode(self):
    try:
      return self._CEncode()
    except AbstractMethod:
      e = Encoder()
      self.Output(e)
      return e.buffer().tostring()

  def _CEncode(self):
    raise AbstractMethod

  def ParseFromString(self, s):
    self.Clear()
    self.MergeFromString(s)
    return

  def MergeFromString(self, s):
    try:
      self._CMergeFromString(s)
      dbg = []
      if not self.IsInitialized(dbg):
        raise ProtocolBufferDecodeError, '\n\t'.join(dbg)
    except AbstractMethod:
      a = array.array('B')
      a.fromstring(s)
      d = Decoder(a, 0, len(a))
      self.Merge(d)
      return

  def _CMergeFromString(self, s):
    raise AbstractMethod

  def __getstate__(self):
    return self.Encode()

  def __setstate__(self, contents_):
    self.__init__(contents=contents_)

  def sendCommand(self, server, url, response, follow_redirects=1,
                  secure=0, keyfile=None, certfile=None):
    data = self.Encode()
    if secure:
      if keyfile and certfile:
        conn = httplib.HTTPSConnection(server, key_file=keyfile,
                                       cert_file=certfile)
      else:
        conn = httplib.HTTPSConnection(server)
    else:
      conn = httplib.HTTPConnection(server)
    # Mods for AppScale
    conn.putrequest("POST", "/")
    pb_type = split(str(self.__class__),'.')[-1]
    conn.putheader("ProtocolBufferType" , pb_type)
    conn.putheader("AppData", url) # app id, user email, nick name, auth domain

    conn.putheader("Content-Length", "%d" %len(data))
    conn.endheaders()
    conn.send(data)
    resp = conn.getresponse()
    if follow_redirects > 0 and resp.status == 302:
      m = URL_RE.match(resp.getheader('Location'))
      if m:
        protocol, server, url = m.groups()
        return self.sendCommand(server, url, response,
                                follow_redirects=follow_redirects - 1,
                                secure=(protocol == 'https'),
                                keyfile=keyfile,
                                certfile=certfile)
    if resp.status != 200:
      raise ProtocolBufferReturnError(resp.status)
    if response is not None:
      response.ParseFromString(resp.read())
    return response

  def sendSecureCommand(self, server, keyfile, certfile, url, response,
                        follow_redirects=1):
    return self.sendCommand(server, url, response,
                            follow_redirects=follow_redirects,
                            secure=1, keyfile=keyfile, certfile=certfile)

  def __str__(self, prefix="", printElemNumber=0):
    raise AbstractMethod

  def ToASCII(self):
    return self._CToASCII(ProtocolMessage._SYMBOLIC_FULL_ASCII)

  def ToCompactASCII(self):
    return self._CToASCII(ProtocolMessage._NUMERIC_ASCII)

  def ToShortASCII(self):
    return self._CToASCII(ProtocolMessage._SYMBOLIC_SHORT_ASCII)

  _NUMERIC_ASCII = 0
  _SYMBOLIC_SHORT_ASCII = 1
  _SYMBOLIC_FULL_ASCII = 2

  def _CToASCII(self, output_format):
    raise AbstractMethod

  def ParseASCII(self, ascii_string):
    raise AbstractMethod

  def ParseASCIIIgnoreUnknown(self, ascii_string):
    raise AbstractMethod

  def Equals(self, other):
    raise AbstractMethod

  def __eq__(self, other):
    if other.__class__ is self.__class__:
      return self.Equals(other)
    return NotImplemented

  def __ne__(self, other):
    if other.__class__ is self.__class__:
      return not self.Equals(other)
    return NotImplemented


  def Output(self, e):
    dbg = []
    if not self.IsInitialized(dbg):
      raise ProtocolBufferEncodeError, '\n\t'.join(dbg)
    self.OutputUnchecked(e)
    return

  def OutputUnchecked(self, e):
    raise AbstractMethod

  def Parse(self, d):
    self.Clear()
    self.Merge(d)
    return

  def Merge(self, d):
    self.TryMerge(d)
    dbg = []
    if not self.IsInitialized(dbg):
      raise ProtocolBufferDecodeError, '\n\t'.join(dbg)
    return

  def TryMerge(self, d):
    raise AbstractMethod

  def CopyFrom(self, pb):
    if (pb == self): return
    self.Clear()
    self.MergeFrom(pb)

  def MergeFrom(self, pb):
    raise AbstractMethod


  def lengthVarInt32(self, n):
    return self.lengthVarInt64(n)

  def lengthVarInt64(self, n):
    if n < 0:
      return 10
    result = 0
    while 1:
      result += 1
      n >>= 7
      if n == 0:
        break
    return result

  def lengthString(self, n):
    return self.lengthVarInt32(n) + n

  def DebugFormat(self, value):
    return "%s" % value
  def DebugFormatInt32(self, value):
    if (value <= -2000000000 or value >= 2000000000):
      return self.DebugFormatFixed32(value)
    return "%d" % value
  def DebugFormatInt64(self, value):
    if (value <= -20000000000000 or value >= 20000000000000):
      return self.DebugFormatFixed64(value)
    return "%d" % value
  def DebugFormatString(self, value):
    def escape(c):
      o = ord(c)
      if o == 10: return r"\n"
      if o == 39: return r"\'"

      if o == 34: return r'\"'
      if o == 92: return r"\\"

      if o >= 127 or o < 32: return "\\%03o" % o
      return c
    return '"' + "".join([escape(c) for c in value]) + '"'
  def DebugFormatFloat(self, value):
    return "%ff" % value
  def DebugFormatFixed32(self, value):
    if (value < 0): value += (1L<<32)
    return "0x%x" % value
  def DebugFormatFixed64(self, value):
    if (value < 0): value += (1L<<64)
    return "0x%x" % value
  def DebugFormatBool(self, value):
    if value:
      return "true"
    else:
      return "false"

class Encoder:

  NUMERIC     = 0
  DOUBLE      = 1
  STRING      = 2
  STARTGROUP  = 3
  ENDGROUP    = 4
  FLOAT       = 5
  MAX_TYPE    = 6

  def __init__(self):
    self.buf = array.array('B')
    return

  def buffer(self):
    return self.buf

  def put8(self, v):
    if v < 0 or v >= (1<<8): raise ProtocolBufferEncodeError, "u8 too big"
    self.buf.append(v & 255)
    return

  def put16(self, v):
    if v < 0 or v >= (1<<16): raise ProtocolBufferEncodeError, "u16 too big"
    self.buf.append((v >> 0) & 255)
    self.buf.append((v >> 8) & 255)
    return

  def put32(self, v):
    if v < 0 or v >= (1L<<32): raise ProtocolBufferEncodeError, "u32 too big"
    self.buf.append((v >> 0) & 255)
    self.buf.append((v >> 8) & 255)
    self.buf.append((v >> 16) & 255)
    self.buf.append((v >> 24) & 255)
    return

  def put64(self, v):
    if v < 0 or v >= (1L<<64): raise ProtocolBufferEncodeError, "u64 too big"
    self.buf.append((v >> 0) & 255)
    self.buf.append((v >> 8) & 255)
    self.buf.append((v >> 16) & 255)
    self.buf.append((v >> 24) & 255)
    self.buf.append((v >> 32) & 255)
    self.buf.append((v >> 40) & 255)
    self.buf.append((v >> 48) & 255)
    self.buf.append((v >> 56) & 255)
    return

  def putVarInt32(self, v):

    buf_append = self.buf.append
    if v & 127 == v:
      buf_append(v)
      return
    if v >= 0x80000000 or v < -0x80000000:
      raise ProtocolBufferEncodeError, "int32 too big"
    if v < 0:
      v += 0x10000000000000000
    while True:
      bits = v & 127
      v >>= 7
      if v:
        bits |= 128
      buf_append(bits)
      if not v:
        break
    return

  def putVarInt64(self, v):
    buf_append = self.buf.append
    if v >= 0x8000000000000000 or v < -0x8000000000000000:
      raise ProtocolBufferEncodeError, "int64 too big"
    if v < 0:
      v += 0x10000000000000000
    while True:
      bits = v & 127
      v >>= 7
      if v:
        bits |= 128
      buf_append(bits)
      if not v:
        break
    return

  def putVarUint64(self, v):
    buf_append = self.buf.append
    if v < 0 or v >= 0x10000000000000000:
      raise ProtocolBufferEncodeError, "uint64 too big"
    while True:
      bits = v & 127
      v >>= 7
      if v:
        bits |= 128
      buf_append(bits)
      if not v:
        break
    return


  def putFloat(self, v):
    a = array.array('B')
    a.fromstring(struct.pack("<f", v))
    self.buf.extend(a)
    return

  def putDouble(self, v):
    a = array.array('B')
    a.fromstring(struct.pack("<d", v))
    self.buf.extend(a)
    return

  def putBoolean(self, v):
    if v:
      self.buf.append(1)
    else:
      self.buf.append(0)
    return

  def putPrefixedString(self, v):
    v = str(v)
    self.putVarInt32(len(v))
    self.buf.fromstring(v)
    return

  def putRawString(self, v):
    self.buf.fromstring(v)


class Decoder:
  def __init__(self, buf, idx, limit):
    self.buf = buf
    self.idx = idx
    self.limit = limit
    return

  def avail(self):
    return self.limit - self.idx

  def buffer(self):
    return self.buf

  def pos(self):
    return self.idx

  def skip(self, n):
    if self.idx + n > self.limit: raise ProtocolBufferDecodeError, "truncated"
    self.idx += n
    return

  def skipData(self, tag):
    t = tag & 7
    if t == Encoder.NUMERIC:
      self.getVarInt64()
    elif t == Encoder.DOUBLE:
      self.skip(8)
    elif t == Encoder.STRING:
      n = self.getVarInt32()
      self.skip(n)
    elif t == Encoder.STARTGROUP:
      while 1:
        t = self.getVarInt32()
        if (t & 7) == Encoder.ENDGROUP:
          break
        else:
          self.skipData(t)
      if (t - Encoder.ENDGROUP) != (tag - Encoder.STARTGROUP):
        raise ProtocolBufferDecodeError, "corrupted"
    elif t == Encoder.ENDGROUP:
      raise ProtocolBufferDecodeError, "corrupted"
    elif t == Encoder.FLOAT:
      self.skip(4)
    else:
      raise ProtocolBufferDecodeError, "corrupted"

  def get8(self):
    if self.idx >= self.limit: raise ProtocolBufferDecodeError, "truncated"
    c = self.buf[self.idx]
    self.idx += 1
    return c

  def get16(self):
    if self.idx + 2 > self.limit: raise ProtocolBufferDecodeError, "truncated"
    c = self.buf[self.idx]
    d = self.buf[self.idx + 1]
    self.idx += 2
    return (d << 8) | c

  def get32(self):
    if self.idx + 4 > self.limit: raise ProtocolBufferDecodeError, "truncated"
    c = self.buf[self.idx]
    d = self.buf[self.idx + 1]
    e = self.buf[self.idx + 2]
    f = long(self.buf[self.idx + 3])
    self.idx += 4
    return (f << 24) | (e << 16) | (d << 8) | c

  def get64(self):
    if self.idx + 8 > self.limit: raise ProtocolBufferDecodeError, "truncated"
    c = self.buf[self.idx]
    d = self.buf[self.idx + 1]
    e = self.buf[self.idx + 2]
    f = long(self.buf[self.idx + 3])
    g = long(self.buf[self.idx + 4])
    h = long(self.buf[self.idx + 5])
    i = long(self.buf[self.idx + 6])
    j = long(self.buf[self.idx + 7])
    self.idx += 8
    return ((j << 56) | (i << 48) | (h << 40) | (g << 32) | (f << 24)
            | (e << 16) | (d << 8) | c)

  def getVarInt32(self):
    b = self.get8()
    if not (b & 128):
      return b

    result = long(0)
    shift = 0

    while 1:
      result |= (long(b & 127) << shift)
      shift += 7
      if not (b & 128):
        if result >= 0x10000000000000000L:
          raise ProtocolBufferDecodeError, "corrupted"
        break
      if shift >= 64: raise ProtocolBufferDecodeError, "corrupted"
      b = self.get8()

    if result >= 0x8000000000000000L:
      result -= 0x10000000000000000L
    if result >= 0x80000000L or result < -0x80000000L:
      raise ProtocolBufferDecodeError, "corrupted"
    return result

  def getVarInt64(self):
    result = self.getVarUint64()
    if result >= (1L << 63):
      result -= (1L << 64)
    return result

  def getVarUint64(self):
    result = long(0)
    shift = 0
    while 1:
      if shift >= 64: raise ProtocolBufferDecodeError, "corrupted"
      b = self.get8()
      result |= (long(b & 127) << shift)
      shift += 7
      if not (b & 128):
        if result >= (1L << 64): raise ProtocolBufferDecodeError, "corrupted"
        return result
    return result

  def getFloat(self):
    if self.idx + 4 > self.limit: raise ProtocolBufferDecodeError, "truncated"
    a = self.buf[self.idx:self.idx+4]
    self.idx += 4
    return struct.unpack("<f", a)[0]

  def getDouble(self):
    if self.idx + 8 > self.limit: raise ProtocolBufferDecodeError, "truncated"
    a = self.buf[self.idx:self.idx+8]
    self.idx += 8
    return struct.unpack("<d", a)[0]

  def getBoolean(self):
    b = self.get8()
    if b != 0 and b != 1: raise ProtocolBufferDecodeError, "corrupted"
    return b

  def getPrefixedString(self):
    length = self.getVarInt32()
    if self.idx + length > self.limit:
      raise ProtocolBufferDecodeError, "truncated"
    r = self.buf[self.idx : self.idx + length]
    self.idx += length
    return r.tostring()

  def getRawString(self):
    r = self.buf[self.idx:self.limit]
    self.idx = self.limit
    return r.tostring()


class ProtocolBufferDecodeError(Exception): pass
class ProtocolBufferEncodeError(Exception): pass
class ProtocolBufferReturnError(Exception): pass
