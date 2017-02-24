
import capnp  # pylint: disable=unused-import
import logging_capnp
import os
import re
import struct
import time

from cStringIO import StringIO
from twisted.internet import protocol
from twisted.python import log

MAX_LOG_FILE_SIZE = 1024 * 1024 * 1024

_I_SIZE = struct.calcsize('I')
_qI_SIZE = struct.calcsize('qI')
_PAGE_SIZE = 1000
_ONE_BINARY = struct.pack('I', 1)

def readLogRecord(handle, parse=False):
  buf = handle.read(_I_SIZE)
  if not buf:
    return (None, None) if parse else None
  length, = struct.unpack('I', buf)
  buf = handle.read(length)
  return (buf, logging_capnp.RequestLog.from_bytes(buf)) if parse else buf

def calculateOffset(log_file_id, position):
  return struct.pack('HI', log_file_id, position)

def parseOffset(offset):
  return struct.unpack('HI', offset)

class AppLogFile(object):
  MODE_SEARCH = 1
  MODE_WRITE = 2

  def __init__(self, root_path, app_id, log_file_id, mode):
    self.mode = mode
    self.log_file_id = log_file_id
    self._filename = os.path.join(root_path, 'logservice_%s.%s.log' % (app_id, log_file_id))
    self._requestIdIndexFilename = '%s.ridx' % self._filename
    self._pageIndexFilename = '%s.pidx' % self._filename
    if mode == AppLogFile.MODE_WRITE:
      self._handle = open(self._filename, 'ab')
      self._pageIndexHandle = open(self._pageIndexFilename, 'ab')
      self._requestIdIndexHandle = open(self._requestIdIndexFilename, 'ab')
    else:
      self._handle = open(self._filename, 'rb')
      self._pageIndexHandle = open(self._pageIndexFilename, 'rb')
      self._requestIdIndexHandle = open(self._requestIdIndexFilename, 'rb')
    self._indexSize = self._requestIdIndexHandle.tell() / 14

  def close(self):
    self._handle.close()
    self._pageIndexHandle.close()
    self._requestIdIndexHandle.close()

  def delete(self):
    os.unlink(self._filename)
    os.unlink(self._requestIdIndexFilename)
    os.unlink(self._pageIndexFilename)

  def write(self, buf):
    if self.mode != AppLogFile.MODE_WRITE:
      raise ValueError("Cannot write to AppLogFile in search mode")
    position = self._handle.tell()
    offset = calculateOffset(self.log_file_id, position)
    requestLog = logging_capnp.RequestLog.from_bytes(buf).as_builder()
    requestLog.offset = offset
    buf = requestLog.to_bytes()
    self._handle.write('%s%s' % (struct.pack('I', len(buf)), buf))
    # Index the new logline
    if requestLog.requestId:
      self._requestIdIndexHandle.write('%s%s' % (requestLog.requestId, struct.pack('I', position)))
    if self._indexSize % _PAGE_SIZE == 0:
      self._pageIndexHandle.write(struct.pack('qI', requestLog.endTime, position))
      self._pageIndexHandle.flush()
      self._handle.flush()
      self._requestIdIndexHandle.flush()
    self._indexSize += 1
    return position, requestLog

  def get(self, requestIds):
    if self.mode == AppLogFile.MODE_WRITE:
      self._requestIdIndexHandle.flush()
      self._handle.flush()
      index_handle = open(self._requestIdIndexFilename, 'rb')
      handle = open(self._filename, 'rb')
    else:
      index_handle = self._requestIdIndexHandle
      handle = self._handle
    try:
      index_handle.seek(0)
      while True:
        buf = index_handle.read(14000)
        if not buf:
          break
        i = 0
        while True:
          key = buf[i:i+10]
          if not key:
            break
          if key in requestIds:
            requestIds.remove(key)
            position, = struct.unpack('I', buf[i+10:i+14])
            handle.seek(position)
            record = readLogRecord(handle, False)
            yield key, record
            if not requestIds:
              break
          i += 14
          if not requestIds:
            break
    finally:
      if self.mode == AppLogFile.MODE_WRITE:
        handle.close()
        index_handle.close()

  def iterpages(self):
    if self.mode == AppLogFile.MODE_WRITE:
      self._pageIndexHandle.flush()
      with open(self._pageIndexFilename, 'rb') as fh:
        pages = fh.read()
    else:
      self._pageIndexHandle.seek(0)
      pages = self._pageIndexHandle.read()
    for pos in xrange(len(pages)-_qI_SIZE, -1, -_qI_SIZE):
      yield struct.unpack('qI', pages[pos:pos+_qI_SIZE])

  def iterrecords(self, start_position, end_position):
    if self.mode == AppLogFile.MODE_WRITE:
      self._handle.flush()
      handle = open(self._filename, 'rb')
    else:
      handle = self._handle
    try:
      handle.seek(start_position)
      if end_position != -1:
        buf = handle.read(end_position - start_position)
      else:
        buf = handle.read()
    finally:
      if self.mode == AppLogFile.MODE_WRITE:
        handle.close()
    pos = 0
    while pos < len(buf):
      buf2 = buf[pos:pos+_I_SIZE]
      pos += _I_SIZE
      if not buf2:
        break
      length, = struct.unpack('I', buf2)
      buf2 = buf[pos:pos+length]
      pos += length
      yield buf2, logging_capnp.RequestLog.from_bytes(buf2)

class AppRegistry(object):

  def __init__(self, root_path, app_id, factory):
    self._factory = factory
    self._followers = dict()
    self._app_id = app_id
    self._root_path = root_path
    self._log_files = list()
    ids = [0]
    for f in os.listdir(root_path):
      m = re.match('^logservice_%s\\.(\\d+)\\.log$' % app_id, f)
      if not m:
        continue
      log_file_id = int(m.groups()[0])
      ids.append(log_file_id)
      self._log_files.append(AppLogFile(root_path, app_id, log_file_id,
                                        AppLogFile.MODE_SEARCH))
    self._log_files.sort(key=lambda x: x.log_file_id)
    self._writer = AppLogFile(root_path, app_id, max(ids) + 1, AppLogFile.MODE_WRITE)

  def write(self, buf):
    position, requestLog = self._writer.write(buf)
    if position > MAX_LOG_FILE_SIZE:
      self._writer.close()
      self._log_files.append(AppLogFile(self._root_path, self._app_id,
                                        self._writer.log_file_id,
                                        AppLogFile.MODE_SEARCH))
      self._writer = AppLogFile(self._root_path, self._app_id,
                                self._writer.log_file_id + 1,
                                AppLogFile.MODE_WRITE)
      log_file_count = len(self._log_files) - 1
      if log_file_count * MAX_LOG_FILE_SIZE > self._factory.size * 1024 ** 3:
        lf = self._log_files.pop(0)
        lf.close()
        lf.delete()
    self.broadcastToFollowers(requestLog, buf)

  def iter(self):
    yield self._writer
    for alf in reversed(self._log_files):
      yield alf

  def get(self, requestIds):
    lookupRequestIds = list(requestIds)
    for alf in self.iter():
      if not lookupRequestIds:
        break
      for requestId, record in alf.get(lookupRequestIds):
        yield requestId, record

  def iterpages(self):
    for alf in self.iter():
      for endTime, position in alf.iterpages():
         yield endTime, position, alf

  def registerFollower(self, protocol, query):
    self._followers[protocol] = query

  def unregisterFollower(self, protocol):
    if protocol in self._followers:
      del self._followers[protocol]

  def broadcastToFollowers(self, record, buf):
    for protocol, query in self._followers.iteritems():
      if query.minimumLogLevel:
        include = False
        for appLog in record.appLogs:
          if appLog.level >= query.minimumLogLevel:
            include = True
            break
        if not include:
          continue
      versionIds = list(query.versionIds)
      if record.versionId and not record.versionId.split('.', 1)[0] in versionIds:
        continue
      protocol.transport.write('%s%s%s' % (_ONE_BINARY, struct.pack('I', len(buf)), buf))

class Protocol(protocol.Protocol):

  def __init__(self):
    self.buf = ''
    self.app_id = None
    self.app_registry = None

  def dataReceived(self, data):
    self.buf += data
    while self.processActions():
      continue

  def processActions(self):
    buffer_size = len(self.buf)
    if buffer_size < 5:
      return False
    action = self.buf[0]
    if not self.app_id and action != 'a': # First command should set_app_id
      log.err("Received unknown action %s", action)
      self.transport.loseConnection()
      return False
    query_length, = struct.unpack('I', self.buf[1:5])
    query_end = query_length + 5;
    if buffer_size < query_end:
      return False
    query = self.buf[5:query_end]
    processor = self.ACTIONS.get(action)
    if processor:
      processor(self, query)
    else:
      log.err("Received unknown action %s", action)
      self.transport.loseConnection()
      return False
    self.buf = self.buf[query_end:]
    return True

  def processSetAppId(self, query):
    # Set our app_id
    self.app_id = query
    if self.app_id in self.factory.apps:
      self.app_registry = self.factory.apps[self.app_id]
      return
    self.app_registry = AppRegistry(self.factory.path, self.app_id, self.factory)
    self.factory.apps[self.app_id] = self.app_registry

  def processActionLog(self, query):
    self.app_registry.write(query)

  def processActionQuery(self, query):
    query = logging_capnp.Query.from_bytes(query)
    log.msg("Received Query: {}".format(query))
    if len(query.requestIds) > 0:
      self.processActionQueryRequestIds(query.requestIds)
    else:
      self.processActionQuerySearch(query)

  def processActionQuerySearch(self, query):
    results = list()
    versionIds = list(query.versionIds)
    if query.offset:
      query_log_file_id, query_position = parseOffset(query.offset)
    oldestRecord = None
    start = time.time()
    previousALF = None
    previousPosition = -1
    for endTime, position, alf in self.app_registry.iterpages():
      if query.endTime and query.endTime < endTime:
        continue
      if query.offset:
        if alf.log_file_id > query_log_file_id:
          continue
        if alf.log_file_id == query_log_file_id and position > query_position:
          continue
      end_position = previousPosition if alf == previousALF else -1
      for buf, record in alf.iterrecords(position, end_position):
        if not oldestRecord or oldestRecord.startTime > record.startTime:
          oldestRecord = record
        if query.endTime and query.endTime < endTime:
          break
        if query.offset:
          log_file_id, position = parseOffset(record.offset)
          if log_file_id == query_log_file_id and position >= query_position:
            break
        if query.minimumLogLevel:
          include = False
          for appLog in record.appLogs:
            if appLog.level >= query.minimumLogLevel:
              include = True
              break
          if not include:
            continue
        if record.versionId and not record.versionId.split('.', 1)[0] in versionIds:
          continue
        if query.startTime and query.startTime > record.startTime:
          continue
        results.append((buf, record))
      if query.startTime and oldestRecord.endTime < query.startTime:
        break
      if len(results) >= query.count:
        break
      if results and time.time() - start > 5:
        break
      if time.time() - start > 25:
        break
      previousALF = alf
      previousPosition = position
    results.sort(key=lambda entry: entry[1].endTime, reverse=True)
    self.sendQueryResult([b for b, _ in results])

  def processActionQueryRequestIds(self, requestIds):
    results = dict()
    for requestId, record in self.app_registry.get(requestIds):
      results[requestId] = record
    self.sendQueryResult([results.get(ri) for ri in requestIds])

  def sendQueryResult(self, records):
    log.msg("Sending {} Result(s)".format(len(records)))
    stream = StringIO()
    stream.write(struct.pack('I', len(records)))
    for record in records:
      if record is None:
        stream.write(struct.pack('I', 0))
      else:
        stream.write(struct.pack('I', len(record)))
        stream.write(record)
    self.transport.write(stream.getvalue())
    stream.close()

  def getLogFile(self, log_file_id):
    return os.path.join(self.factory.path, 'logservice_%s.%s.log' % (self.app_id, log_file_id))

  def processActionFollow(self, query):
    query = logging_capnp.Query.from_bytes(query)
    self.app_registry.registerFollower(self, query)

  def connectionLost(self, reason=None):
    if self.app_registry:
      self.app_registry.unregisterFollower(self)

  ACTIONS = dict(l=processActionLog, a=processSetAppId, q=processActionQuery, f=processActionFollow)


class LogServerFactory(protocol.Factory):
    protocol = Protocol

    def __init__(self, path, size):
        self.path = path
        self.size = size
        self.apps = dict()
