""" Implements the LogService API. """

import logging
import socket
import struct
import time

from concurrent.futures import ThreadPoolExecutor
from tornado import gen

from appscale.api_server.base_service import BaseService
from appscale.api_server.constants import CallNotFound
from appscale.api_server.log.constants import (ClientActions, InvalidRequest,
                                               LOG_SERVER_PORT, StorageError)
from appscale.api_server.log.log_service_pb2 import (
    FlushRequest,
    LogReadRequest,
    LogReadResponse,
    UserAppLogGroup)
from appscale.api_server.log.messages import (AppLog, logging_capnp, LogQuery,
                                              RequestLog)
from appscale.api_server.log.writer import LogWriter

logger = logging.getLogger('appscale-api-server')


class LogService(BaseService):
    """ Implements the LogService API. """
    SERVICE_NAME = 'logservice'

    # The appropriate messages for each API call.
    METHODS = {'Flush': (FlushRequest, lambda: None),
               'Read': (LogReadRequest, LogReadResponse)}

    def __init__(self, project_id, log_server_ip):
        """ Creates a new LogService.

        Args:
            project_id: A string specifying the project ID.
            log_server_ip: A string specifying the log server location.
        """
        super(LogService, self).__init__(self.SERVICE_NAME)

        self.project_id = project_id
        self.log_server_ip = log_server_ip
        self.requests = {}

        self._writer = LogWriter(self.log_server_ip, self.project_id)
        self._thread_pool = ThreadPoolExecutor(4)

    def start_request(self, request_log):
        """ Starts logging for a request.

        Each start_request call must be followed by a corresponding end_request
        call to cleanup resources allocated in start_request.

        Args:
            request_log = A RequestLog object.
        Raises:
            InvalidRequest when the request already exists.
        """
        if request_log.request_id in self.requests:
            raise InvalidRequest('Request is already in progress')

        self.requests[request_log.request_id] = request_log

    def end_request(self, request_id, status, response_size):
        """ Ends logging for a request.

        Args:
            request_id: A string specifying the request ID.
            status: An integer specifying the HTTP status code.
            response_size: An integer specifying the response length.
        Raises:
            InvalidRequest when the request does not exist.
        """
        try:
            request_log = self.requests.pop(request_id)
        except KeyError:
            raise InvalidRequest('Request not found')

        request_log.status = status
        request_log.response_size = response_size
        request_log.end_time = int(time.time() * 1000 * 1000)
        self._writer.write_async(request_log)

    @gen.coroutine
    def fetch(self, query):
        """ Runs a query against the log server.

        Args:
            query: A LogQuery object.
        Raises:
            StorageError when unable to communicate with the log server.
        """
        connection = yield self._connect()
        try:
            # Define the project for messages on this connection.
            yield self._send(ClientActions.SET_PROJECT, self.project_id,
                             connection)

            yield self._send(ClientActions.QUERY, query.to_capnp().to_bytes(),
                             connection)
            request_logs = yield self._receive(connection)
        finally:
            connection.close()

        raise gen.Return(request_logs)

    @gen.coroutine
    def make_call(self, method, encoded_request, request_id):
        """ Makes the appropriate API call for a given request.

        Args:
            method: A string specifying the API method.
            encoded_request: A binary type containing the request details.
            request_id: A string specifying the request ID.
        Returns:
            A binary type containing the response details.
        Raises:
            InvalidRequest when the request is invalid.
            StorageError when unable to communicate with the log server.
        """
        if method not in self.METHODS:
            raise CallNotFound(
                '{}.{} does not exist'.format(self.SERVICE_NAME, method))

        request = self.METHODS[method][0]()
        request.ParseFromString(encoded_request)

        response = self.METHODS[method][1]()

        if method == 'Flush':
            log_group = UserAppLogGroup()
            log_group.ParseFromString(request.logs)
            try:
                self.requests[request_id].app_logs.extend(
                    [AppLog.from_pb(line) for line in log_group.log_line])
            except KeyError:
                raise InvalidRequest('Request not found: {}'.format(request_id))
        elif method == 'Read':
            query = LogQuery.from_pb(request)
            request_logs = yield self.fetch(query)
            response.log.extend([log.to_pb(query.include_app_logs)
                                 for log in request_logs])

            # TODO: Only include offset if there are more results.
            if len(response.log) == query.count and request_logs:
                response.offset.request_id = request_logs[-1].offset

        if response is None:
            raise gen.Return(response)
        else:
            raise gen.Return(response.SerializeToString())

    @gen.coroutine
    def _connect(self):
        """ Opens a socket connection to the log server.

        Returns:
            A socket object.
        Raises:
            StorageError when unable to connect to the server.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            yield self._thread_pool.submit(
                sock.connect, (self.log_server_ip, LOG_SERVER_PORT))
        except socket.error:
            raise StorageError('Unable to connect to log server')

        raise gen.Return(sock)

    @gen.coroutine
    def _send(self, action, message, sock):
        """ Sends a message to the log server.

        Args:
            action: A string specifying the message type.
            message: A string containing the encoded message.
            sock: A socket object.
        Raises:
            StorageError when unable to send the message.
        """
        message_length = struct.pack('I', len(message))
        full_message = ''.join([action, message_length, message])
        try:
            yield self._thread_pool.submit(sock.sendall, full_message)
        except socket.error:
            raise StorageError('Unable to send message to log server')

    @gen.coroutine
    def _receive(self, sock):
        """ Reads the log server's response to a query.

        Args:
            sock: A socket object.
        Returns:
            A list of RequestLog objects.
        Raises:
            StorageError when unable to read response.
        """
        request_logs = []
        handle = sock.makefile('rb')
        metadata_length = struct.calcsize('I')
        try:
            metadata = yield self._thread_pool.submit(handle.read, metadata_length)
            message_count, = struct.unpack('I', metadata)
            for _ in range(message_count):
                metadata = yield self._thread_pool.submit(handle.read,
                                                          metadata_length)
                size, = struct.unpack('I', metadata)
                message = yield self._thread_pool.submit(handle.read, size)
                request_log = logging_capnp.RequestLog.from_bytes(message)
                request_logs.append(RequestLog.from_capnp(request_log))
        except socket.error:
            raise StorageError('Unable to read response from log server')
        finally:
            handle.close()

        raise gen.Return(request_logs)
