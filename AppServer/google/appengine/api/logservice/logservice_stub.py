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
"""Stub implementation for Log Service that uses sqlite."""


import base64
from logging.handlers import WatchedFileHandler

import capnp # pylint: disable=unused-import
import logging

import json
import logging_capnp
import socket
import struct
import time

from collections import defaultdict

import os

from datetime import datetime

import threading
from google.appengine.api import apiproxy_stub
from google.appengine.api.logservice import log_service_pb
from google.appengine.api.modules import (
  get_current_module_name, get_current_version_name
)
from google.appengine.runtime import apiproxy_errors
from Queue import Queue, Empty, Full

# Add path to import file_io
from appscale.common import file_io


_I_SIZE = struct.calcsize('I')

LEVELS = {
  0: 'DEBUG',
  1: 'INFO',
  2: 'WARNING',
  3: 'ERROR',
  4: 'CRITICAL',
}


class RequestsLogger(threading.Thread):

  FILENAME_TEMPLATE = (
    '/opt/appscale/logserver/requests-{app}-{service}-{version}-{port}.log'
  )
  QUEUE_SIZE = 1024 * 16

  def __init__(self):
    super(RequestsLogger, self).__init__()
    self.setDaemon(True)
    self._logs_queue = Queue(self.QUEUE_SIZE)
    self._logger = None
    self._shutting_down = False

  def _init_logger(self, request_info):
    # Init logger lazily when application info is available
    app_id = request_info['appId']
    service_id = request_info['serviceName']
    version_id = request_info['versionName']
    port = request_info['port']
    # Prepare filename
    filename = self.FILENAME_TEMPLATE.format(
      app=app_id, service=service_id, version=version_id, port=port)
    # Initialize logger
    formatter = logging.Formatter('%(message)s')
    file_handler = WatchedFileHandler(filename)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    self._logger = logging.Logger('request-logger', logging.INFO)
    self._logger.addHandler(file_handler)

  def run(self):
    request_info = None
    while True:
      if not request_info:
        # Get new info from the queue if previous has been saved
        request_info = self._logs_queue.get()
      if not request_info and self._shutting_down:
        return
      try:
        if not self._logger:
          self._init_logger(request_info)
        self._logger.info(json.dumps(request_info))
        request_info = None
      except Exception:
        try:
          logging.exception(
            'Failed to write request_info to log file\n  Request info: {}'
            .format(request_info or "-"))
        except Exception:
          # There were cases where exception was thrown at writing error
          pass
        time.sleep(5)

  def stop(self):
    self._shutting_down = True
    self._logs_queue.put(None)

  def write(self, requests_info):
    try:
      # Put an item on the queue if a free slot is immediately available
      self._logs_queue.put(requests_info, block=False)
    except Full:
      logging.error('Request logs queue is crowded')


def _cleanup_logserver_connection(connection):
  try:
    connection.close()
  except socket.error:
    pass


def _fill_request_log(requestLog, log, include_app_logs):
  log.set_request_id(requestLog.requestId)
  log.set_app_id(requestLog.appId)
  log.set_version_id(requestLog.versionId)
  log.set_ip(requestLog.ip)
  log.set_nickname(requestLog.nickname)
  log.set_start_time(requestLog.startTime)
  log.set_host(requestLog.host)
  log.set_end_time(requestLog.endTime)
  log.set_method(requestLog.method)
  log.set_resource(requestLog.resource)
  log.set_status(requestLog.status)
  log.set_response_size(requestLog.responseSize)
  log.set_http_version(requestLog.httpVersion)
  log.set_user_agent(requestLog.userAgent)
  log.set_url_map_entry(requestLog.urlMapEntry)
  log.set_latency(requestLog.latency)
  log.set_mcycles(requestLog.mcycles)
  log.set_finished(requestLog.finished)

  log.mutable_offset().set_request_id(base64.b64encode(requestLog.offset))
  time_seconds = (requestLog.endTime or requestLog.startTime) / 10**6
  date_string = time.strftime('%d/%b/%Y:%H:%M:%S %z',
                              time.localtime(time_seconds))
  log.set_combined('%s - %s [%s] "%s %s %s" %d %d - "%s"' %
                   (requestLog.ip, requestLog.nickname, date_string,
                    requestLog.method, requestLog.resource,
                    requestLog.httpVersion, requestLog.status or 0,
                    requestLog.responseSize or 0, requestLog.userAgent))
  if include_app_logs:
    for appLog in requestLog.appLogs:
      line = log.add_line()
      line.set_time(appLog.time)
      line.set_level(appLog.level)
      line.set_log_message(appLog.message)


class LogServiceStub(apiproxy_stub.APIProxyStub):
  """Python stub for Log Service service."""

  THREADSAFE = True

  _ACCEPTS_REQUEST_ID = True

  _DEFAULT_READ_COUNT = 20

  def __init__(self, persist=False, logs_path=None, request_data=None):
    """Initializer.

    Args:
      persist: For backwards compatability. Has no effect.
      logs_path: A str containing the filename to use for logs storage. Defaults
        to in-memory if unset.
      request_data: A apiproxy_stub.RequestData instance used to look up state
        associated with the request that generated an API call.
    """

    super(LogServiceStub, self).__init__('logservice',
                                         request_data=request_data)
    self._pending_requests = defaultdict(logging_capnp.RequestLog.new_message)
    self._pending_requests_applogs = dict()
    self._log_server = defaultdict(Queue)
    # get head node_private ip from /etc/appscale/head_node_private_ip
    self._log_server_ip = file_io.read("/etc/appscale/head_node_private_ip").rstrip()

    if os.path.exists('/etc/appscale/elk-enabled'):
      self._requests_logger = RequestsLogger()
      self._requests_logger.start()
      self.is_elk_enabled = True
    else:
      self._requests_logger = None
      self.is_elk_enabled = False

  def stop_requests_logger(self):
    self._requests_logger.stop()

  def is_requests_logger_alive(self):
    return self._requests_logger.is_alive()

  def save_to_file_for_elk(self, request_id, end_time, request_log):
    start_time = request_log.startTime
    start_time_ms = float(start_time) / 1000
    end_time_ms = float(end_time) / 1000

    # Render app logs:
    app_logs_str = '\n'.join([
      '{} {} {}'.format(
        LEVELS[log.level],
        datetime.utcfromtimestamp(log.time/1000000)
          .strftime('%Y-%m-%d %H:%M:%S'),
        log.message
      )
      for log in request_log.appLogs
    ])

    request_info = {
      'generated_id': '{}-{}'.format(start_time, request_id),
      'serviceName': get_current_module_name(),
      'versionName': get_current_version_name(),
      'startTime': start_time_ms,
      'endTime': end_time_ms,
      'latency': int(end_time_ms - start_time_ms),
      'level': max(0, 0, *[
         log.level for log in request_log.appLogs
       ]),
      'appId': request_log.appId,
      'appscale-host': os.environ['MY_IP_ADDRESS'],
      'port': int(os.environ['MY_PORT']),
      'ip': request_log.ip,
      'method': request_log.method,
      'requestId': request_id,
      'resource': request_log.resource,
      'responseSize': request_log.responseSize,
      'status': request_log.status,
      'userAgent': request_log.userAgent,
      'appLogs': app_logs_str
    }

    self._requests_logger.write(request_info)

  def _get_log_server(self, app_id, blocking):
    key = (blocking, app_id)
    queue = self._log_server[key]
    try:
      return key, queue.get(False)
    except Empty:
      pass
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
      client.connect((self._log_server_ip, 7422))
      client.setblocking(blocking)
      client.send('a%s%s' % (struct.pack('I', len(app_id)), app_id))
      return key, client
    except socket.error:
      logging.exception(
        "Log Server at {ip} refused connection".format(ip=self._log_server_ip))
      return None, None

  def _release_logserver_connection(self, key, connection):
    queue = self._log_server[key]
    queue.put(connection)

  def _send_to_logserver(self, app_id, packet):
    key, log_server = self._get_log_server(app_id, False)
    if log_server:
      try:
        log_server.send(packet)
        self._release_logserver_connection(key, log_server)
      except socket.error, e:
        _cleanup_logserver_connection(log_server)
        self._send_to_logserver(app_id, packet)

  def _query_log_server(self, app_id, packet):
    key, log_server = self._get_log_server(app_id, True)
    if not log_server:
      raise apiproxy_errors.ApplicationError(
        log_service_pb.LogServiceError.STORAGE_ERROR)
    try:
      log_server.send(packet)
      fh = log_server.makefile('rb')
      try:
        buf = fh.read(_I_SIZE)
        count, = struct.unpack('I', buf)
        for _ in xrange(count):
          buf = fh.read(_I_SIZE)
          length, = struct.unpack('I', buf)
          yield fh.read(length)
      finally:
        fh.close()
      self._release_logserver_connection(key, log_server)
    except socket.error, e:
      _cleanup_logserver_connection(log_server)
      raise

  @staticmethod
  def _get_time_usec():
    return int(time.time() * 1e6)

  @apiproxy_stub.Synchronized
  def start_request(self, request_id, user_request_id, ip, app_id, version_id,
                    nickname, user_agent, host, method, resource, http_version,
                    start_time=None):
    """Starts logging for a request.

    Each start_request call must be followed by a corresponding end_request call
    to cleanup resources allocated in start_request.

    Args:
      request_id: A unique string identifying the request associated with the
        API call.
      user_request_id: A user-visible unique string for retrieving the request
        log at a later time.
      ip: The user's IP address.
      app_id: A string representing the application ID that this request
        corresponds to.
      version_id: A string representing the version ID that this request
        corresponds to.
      nickname: A string representing the user that has made this request (that
        is, the user's nickname, e.g., 'foobar' for a user logged in as
        'foobar@gmail.com').
      user_agent: A string representing the agent used to make this request.
      host: A string representing the host that received this request.
      method: A string containing the HTTP method of this request.
      resource: A string containing the path and query string of this request.
      http_version: A string containing the HTTP version of this request.
      start_time: An int containing the start time in micro-seconds. If unset,
        the current time is used.
    """
    if start_time is None:
      start_time = self._get_time_usec()

    rl = self._pending_requests[request_id]
    rl.appId = app_id
    rl.versionId = version_id
    rl.requestId = request_id
    rl.ip = ip
    rl.nickname = nickname
    rl.startTime = start_time
    rl.method = method
    rl.resource = resource
    rl.httpVersion = http_version
    rl.userAgent = user_agent
    rl.host = host
    self._pending_requests_applogs[request_id] = rl.init_resizable_list('appLogs')

  @apiproxy_stub.Synchronized
  def end_request(self, request_id, status, response_size, end_time=None):
    """Ends logging for a request.

    Args:
      request_id: A unique string identifying the request associated with the
        API call.
      status: An int containing the HTTP status code for this request.
      response_size: An int containing the content length of the response.
      end_time: An int containing the end time in micro-seconds. If unset, the
        current time is used.
    """
    if end_time is None:
      end_time = self._get_time_usec()
    rl = self._pending_requests.get(request_id, None)
    if rl is None:
      return
    rl.status = status
    rl.responseSize = response_size
    rl.endTime = end_time
    self._pending_requests_applogs[request_id].finish()

    if self.is_elk_enabled:
      self.save_to_file_for_elk(request_id, end_time, rl)

    buf = rl.to_bytes()
    packet = 'l%s%s' % (struct.pack('I', len(buf)), buf)
    self._send_to_logserver(rl.appId, packet)
    del self._pending_requests_applogs[request_id]
    del self._pending_requests[request_id]

  def _Dynamic_Flush(self, request, unused_response, request_id):
    """Writes application-level log messages for a request."""
    rl = self._pending_requests.get(request_id, None)
    if rl is None:
      return
    group = log_service_pb.UserAppLogGroup(request.logs())
    logs = group.log_line_list()
    for log in logs:
      al = self._pending_requests_applogs[request_id].add()
      al.time = log.timestamp_usec()
      al.level = log.level()
      al.message = log.message()

  @apiproxy_stub.Synchronized
  def _Dynamic_Read(self, request, response, request_id):
    try:
      if (request.module_version_size() < 1 and
              request.version_id_size() < 1 and
              request.request_id_size() < 1):
        raise apiproxy_errors.ApplicationError(
          log_service_pb.LogServiceError.INVALID_REQUEST)

      if request.module_version_size() > 0 and request.version_id_size() > 0:
        raise apiproxy_errors.ApplicationError(
          log_service_pb.LogServiceError.INVALID_REQUEST)
      if (request.request_id_size() and
            (request.has_start_time() or request.has_end_time() or
               request.has_offset())):
        raise apiproxy_errors.ApplicationError(
          log_service_pb.LogServiceError.INVALID_REQUEST)

      rl = self._pending_requests.get(request_id, None)
      if rl is None:
        raise apiproxy_errors.ApplicationError(
          log_service_pb.LogServiceError.INVALID_REQUEST)

      query = logging_capnp.Query.new_message()
      if request.module_version(0).has_module_id():
        module_version = ':'.join([request.module_version(0).module_id(),
                                   request.module_version(0).version_id()])
      else:
        module_version = request.module_version(0).version_id()
      query.versionIds = [module_version]
      if request.has_start_time():
        query.startTime = request.start_time()
      if request.has_end_time():
        query.endTime = request.end_time()
      if request.has_offset() and request.offset().has_request_id():
        query.offset = base64.b64decode(request.offset().request_id())
      if request.has_minimum_log_level():
        query.minimumLogLevel = request.minimum_log_level()
      query.includeAppLogs = bool(request.include_app_logs())
      if request.request_id_size():
        query.requestIds = request.request_id_list()
      if request.has_count() and request.count() < self._DEFAULT_READ_COUNT:
        count = request.count()
      else:
        count = self._DEFAULT_READ_COUNT
      query.count = count
      # GAE presents logs in reverse chronological order. This is not an
      # option available to users in GAE, so we always set it to True.
      query.reverse = True
      # Perform query to logserver
      buf = query.to_bytes()
      packet = 'q%s%s' % (struct.pack('I', len(buf)), buf)
      result_count = 0
      for rlBytes in self._query_log_server(rl.appId, packet):
        requestLog = logging_capnp.RequestLog.from_bytes(rlBytes)
        log = response.add_log()
        _fill_request_log(requestLog, log, request.include_app_logs())
        result_count += 1

        if result_count == count:
          response.mutable_offset().set_request_id(requestLog.offset)
    except:
      logging.exception("Failed to retrieve logs")
      raise apiproxy_errors.ApplicationError(
        log_service_pb.LogServiceError.INVALID_REQUEST)

  def _Dynamic_SetStatus(self, unused_request, unused_response,
                         unused_request_id):
    raise NotImplementedError

  def _Dynamic_Usage(self, unused_request, unused_response, unused_request_id):
    raise apiproxy_errors.CapabilityDisabledError('Usage not allowed in tests.')
