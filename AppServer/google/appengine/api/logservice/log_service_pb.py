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
import base64
import dummy_thread as thread
try:
  from google3.net.proto import _net_proto___parse__python
except ImportError:
  _net_proto___parse__python = None
import sys
try:
  __import__('google.net.rpc.python.rpc_internals')
  __import__('google.net.rpc.python.pywraprpc')
  rpc_internals = sys.modules.get('google.net.rpc.python.rpc_internals')
  pywraprpc = sys.modules.get('google.net.rpc.python.pywraprpc')
  _client_stub_base_class = rpc_internals.StubbyRPCBaseStub
except ImportError:
  _client_stub_base_class = object
try:
  __import__('google.net.rpc.python.rpcserver')
  rpcserver = sys.modules.get('google.net.rpc.python.rpcserver')
  _server_stub_base_class = rpcserver.BaseRpcServer
except ImportError:
  _server_stub_base_class = object

__pychecker__ = """maxreturns=0 maxbranches=0 no-callinit
                   unusednames=printElemNumber,debug_strs no-special"""

from google.appengine.api.api_base_pb import *
import google.appengine.api.api_base_pb
class FlushRequest(ProtocolBuffer.ProtocolMessage):
  has_logs_ = 0
  logs_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def logs(self): return self.logs_

  def set_logs(self, x):
    self.has_logs_ = 1
    self.logs_ = x

  def clear_logs(self):
    if self.has_logs_:
      self.has_logs_ = 0
      self.logs_ = ""

  def has_logs(self): return self.has_logs_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_logs()): self.set_logs(x.logs())

  if _net_proto___parse__python is not None:
    def _CMergeFromString(self, s):
      _net_proto___parse__python.MergeFromString(self, 'apphosting.FlushRequest', s)

  if _net_proto___parse__python is not None:
    def _CEncode(self):
      return _net_proto___parse__python.Encode(self, 'apphosting.FlushRequest')

  if _net_proto___parse__python is not None:
    def _CEncodePartial(self):
      return _net_proto___parse__python.EncodePartial(self, 'apphosting.FlushRequest')

  if _net_proto___parse__python is not None:
    def _CToASCII(self, output_format):
      return _net_proto___parse__python.ToASCII(self, 'apphosting.FlushRequest', output_format)


  if _net_proto___parse__python is not None:
    def ParseASCII(self, s):
      _net_proto___parse__python.ParseASCII(self, 'apphosting.FlushRequest', s)


  if _net_proto___parse__python is not None:
    def ParseASCIIIgnoreUnknown(self, s):
      _net_proto___parse__python.ParseASCIIIgnoreUnknown(self, 'apphosting.FlushRequest', s)


  def Equals(self, x):
    if x is self: return 1
    if self.has_logs_ != x.has_logs_: return 0
    if self.has_logs_ and self.logs_ != x.logs_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    return initialized

  def ByteSize(self):
    n = 0
    if (self.has_logs_): n += 1 + self.lengthString(len(self.logs_))
    return n

  def ByteSizePartial(self):
    n = 0
    if (self.has_logs_): n += 1 + self.lengthString(len(self.logs_))
    return n

  def Clear(self):
    self.clear_logs()

  def OutputUnchecked(self, out):
    if (self.has_logs_):
      out.putVarInt32(10)
      out.putPrefixedString(self.logs_)

  def OutputPartial(self, out):
    if (self.has_logs_):
      out.putVarInt32(10)
      out.putPrefixedString(self.logs_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_logs(d.getPrefixedString())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_logs_: res+=prefix+("logs: %s\n" % self.DebugFormatString(self.logs_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  klogs = 1

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "logs",
  }, 1)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
  }, 1, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _SERIALIZED_DESCRIPTOR = array.array('B')
  _SERIALIZED_DESCRIPTOR.fromstring(base64.decodestring("WithcHBob3N0aW5nL2FwaS9sb2dzZXJ2aWNlL2xvZ19zZXJ2aWNlLnByb3RvChdhcHBob3N0aW5nLkZsdXNoUmVxdWVzdBMaBGxvZ3MgASgCMAk4ARS6AesCCithcHBob3N0aW5nL2FwaS9sb2dzZXJ2aWNlL2xvZ19zZXJ2aWNlLnByb3RvEgphcHBob3N0aW5nGh1hcHBob3N0aW5nL2FwaS9hcGlfYmFzZS5wcm90byIcCgxGbHVzaFJlcXVlc3QSDAoEbG9ncxgBIAEoDCIiChBTZXRTdGF0dXNSZXF1ZXN0Eg4KBnN0YXR1cxgBIAIoCTKSAQoKTG9nU2VydmljZRI9CgVGbHVzaBIYLmFwcGhvc3RpbmcuRmx1c2hSZXF1ZXN0GhouYXBwaG9zdGluZy5iYXNlLlZvaWRQcm90bxJFCglTZXRTdGF0dXMSHC5hcHBob3N0aW5nLlNldFN0YXR1c1JlcXVlc3QaGi5hcHBob3N0aW5nLmJhc2UuVm9pZFByb3RvQjoKJGNvbS5nb29nbGUuYXBwaG9zdGluZy5hcGkubG9nc2VydmljZRABIAEoAUIMTG9nU2VydmljZVBi"))
  if _net_proto___parse__python is not None:
    _net_proto___parse__python.RegisterType(
        _SERIALIZED_DESCRIPTOR.tostring())

class SetStatusRequest(ProtocolBuffer.ProtocolMessage):
  has_status_ = 0
  status_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def status(self): return self.status_

  def set_status(self, x):
    self.has_status_ = 1
    self.status_ = x

  def clear_status(self):
    if self.has_status_:
      self.has_status_ = 0
      self.status_ = ""

  def has_status(self): return self.has_status_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_status()): self.set_status(x.status())

  if _net_proto___parse__python is not None:
    def _CMergeFromString(self, s):
      _net_proto___parse__python.MergeFromString(self, 'apphosting.SetStatusRequest', s)

  if _net_proto___parse__python is not None:
    def _CEncode(self):
      return _net_proto___parse__python.Encode(self, 'apphosting.SetStatusRequest')

  if _net_proto___parse__python is not None:
    def _CEncodePartial(self):
      return _net_proto___parse__python.EncodePartial(self, 'apphosting.SetStatusRequest')

  if _net_proto___parse__python is not None:
    def _CToASCII(self, output_format):
      return _net_proto___parse__python.ToASCII(self, 'apphosting.SetStatusRequest', output_format)


  if _net_proto___parse__python is not None:
    def ParseASCII(self, s):
      _net_proto___parse__python.ParseASCII(self, 'apphosting.SetStatusRequest', s)


  if _net_proto___parse__python is not None:
    def ParseASCIIIgnoreUnknown(self, s):
      _net_proto___parse__python.ParseASCIIIgnoreUnknown(self, 'apphosting.SetStatusRequest', s)


  def Equals(self, x):
    if x is self: return 1
    if self.has_status_ != x.has_status_: return 0
    if self.has_status_ and self.status_ != x.status_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_status_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: status not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.status_))
    return n + 1

  def ByteSizePartial(self):
    n = 0
    if (self.has_status_):
      n += 1
      n += self.lengthString(len(self.status_))
    return n

  def Clear(self):
    self.clear_status()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.status_)

  def OutputPartial(self, out):
    if (self.has_status_):
      out.putVarInt32(10)
      out.putPrefixedString(self.status_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_status(d.getPrefixedString())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_status_: res+=prefix+("status: %s\n" % self.DebugFormatString(self.status_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kstatus = 1

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "status",
  }, 1)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
  }, 1, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _SERIALIZED_DESCRIPTOR = array.array('B')
  _SERIALIZED_DESCRIPTOR.fromstring(base64.decodestring("WithcHBob3N0aW5nL2FwaS9sb2dzZXJ2aWNlL2xvZ19zZXJ2aWNlLnByb3RvChthcHBob3N0aW5nLlNldFN0YXR1c1JlcXVlc3QTGgZzdGF0dXMgASgCMAk4AhTCARdhcHBob3N0aW5nLkZsdXNoUmVxdWVzdA=="))
  if _net_proto___parse__python is not None:
    _net_proto___parse__python.RegisterType(
        _SERIALIZED_DESCRIPTOR.tostring())



class _LogService_ClientBaseStub(_client_stub_base_class):
  """Makes Stubby RPC calls to a LogService server."""

  __slots__ = (
      '_protorpc_Flush', '_full_name_Flush',
      '_protorpc_SetStatus', '_full_name_SetStatus',
  )

  def __init__(self, rpc_stub):
    self._stub = rpc_stub

    self._protorpc_Flush = pywraprpc.RPC()
    self._full_name_Flush = self._stub.GetFullMethodName(
        'Flush')

    self._protorpc_SetStatus = pywraprpc.RPC()
    self._full_name_SetStatus = self._stub.GetFullMethodName(
        'SetStatus')

  def Flush(self, request, rpc=None, callback=None, response=None):
    """Make a Flush RPC call.

    Args:
      request: a FlushRequest instance.
      rpc: Optional RPC instance to use for the call.
      callback: Optional final callback. Will be called as
          callback(rpc, result) when the rpc completes. If None, the
          call is synchronous.
      response: Optional ProtocolMessage to be filled in with response.

    Returns:
      The google.appengine.api.api_base_pb.VoidProto if callback is None. Otherwise, returns None.
    """

    if response is None:
      response = google.appengine.api.api_base_pb.VoidProto
    return self._MakeCall(rpc,
                          self._full_name_Flush,
                          'Flush',
                          request,
                          response,
                          callback,
                          self._protorpc_Flush)

  def SetStatus(self, request, rpc=None, callback=None, response=None):
    """Make a SetStatus RPC call.

    Args:
      request: a SetStatusRequest instance.
      rpc: Optional RPC instance to use for the call.
      callback: Optional final callback. Will be called as
          callback(rpc, result) when the rpc completes. If None, the
          call is synchronous.
      response: Optional ProtocolMessage to be filled in with response.

    Returns:
      The google.appengine.api.api_base_pb.VoidProto if callback is None. Otherwise, returns None.
    """

    if response is None:
      response = google.appengine.api.api_base_pb.VoidProto
    return self._MakeCall(rpc,
                          self._full_name_SetStatus,
                          'SetStatus',
                          request,
                          response,
                          callback,
                          self._protorpc_SetStatus)


class _LogService_ClientStub(_LogService_ClientBaseStub):
  def __init__(self, rpc_stub_parameters, service_name):
    if service_name is None:
      service_name = 'LogService'
    _LogService_ClientBaseStub.__init__(self, pywraprpc.RPC_GenericStub(service_name, rpc_stub_parameters))
    self._params = rpc_stub_parameters


class _LogService_RPC2ClientStub(_LogService_ClientBaseStub):
  def __init__(self, server, channel, service_name):
    if service_name is None:
      service_name = 'LogService'
    if channel is not None:
      if channel.version() == 1:
        raise RuntimeError('Expecting an RPC2 channel to create the stub')
      _LogService_ClientBaseStub.__init__(self, pywraprpc.RPC_GenericStub(service_name, channel))
    elif server is not None:
      _LogService_ClientBaseStub.__init__(self, pywraprpc.RPC_GenericStub(service_name, pywraprpc.NewClientChannel(server)))
    else:
      raise RuntimeError('Invalid argument combination to create a stub')


class LogService(_server_stub_base_class):
  """Base class for LogService Stubby servers."""

  def __init__(self, *args, **kwargs):
    """Creates a Stubby RPC server.

    See BaseRpcServer.__init__ in rpcserver.py for detail on arguments.
    """
    if _server_stub_base_class is object:
      raise NotImplementedError('Add //net/rpc/python:rpcserver as a '
                                'dependency for Stubby server support.')
    _server_stub_base_class.__init__(self, 'apphosting.LogService', *args, **kwargs)

  @staticmethod
  def NewStub(rpc_stub_parameters, service_name=None):
    """Creates a new LogService Stubby client stub.

    Args:
      rpc_stub_parameters: an RPC_StubParameter instance.
      service_name: the service name used by the Stubby server.
    """

    if _client_stub_base_class is object:
      raise RuntimeError('Add //net/rpc/python as a dependency to use Stubby')
    return _LogService_ClientStub(rpc_stub_parameters, service_name)

  @staticmethod
  def NewRPC2Stub(server=None, channel=None, service_name=None):
    """Creates a new LogService Stubby2 client stub.

    Args:
      server: host:port or bns address.
      channel: directly use a channel to create a stub. Will ignore server
          argument if this is specified.
      service_name: the service name used by the Stubby server.
    """

    if _client_stub_base_class is object:
      raise RuntimeError('Add //net/rpc/python as a dependency to use Stubby')
    return _LogService_RPC2ClientStub(server, channel, service_name)

  def Flush(self, rpc, request, response):
    """Handles a Flush RPC call. You should override this.

    Args:
      rpc: a Stubby RPC object
      request: a FlushRequest that contains the client request
      response: a google.appengine.api.api_base_pb.VoidProto that should be modified to send the response
    """
    raise NotImplementedError


  def SetStatus(self, rpc, request, response):
    """Handles a SetStatus RPC call. You should override this.

    Args:
      rpc: a Stubby RPC object
      request: a SetStatusRequest that contains the client request
      response: a google.appengine.api.api_base_pb.VoidProto that should be modified to send the response
    """
    raise NotImplementedError

  def _AddMethodAttributes(self):
    """Sets attributes on Python RPC handlers.

    See BaseRpcServer in rpcserver.py for details.
    """
    rpcserver._GetHandlerDecorator(
        self.Flush.im_func,
        FlushRequest,
        google.appengine.api.api_base_pb.VoidProto,
        None,
        'none')
    rpcserver._GetHandlerDecorator(
        self.SetStatus.im_func,
        SetStatusRequest,
        google.appengine.api.api_base_pb.VoidProto,
        None,
        'none')


__all__ = ['FlushRequest','SetStatusRequest','LogService']
