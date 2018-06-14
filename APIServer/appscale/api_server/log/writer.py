""" Sends request logs to the log server. """

import logging
import socket
import struct
import threading

from queue import Empty, Queue

from appscale.api_server.log.constants import ClientActions, LOG_SERVER_PORT
from appscale.common.retrying import retry

logger = logging.getLogger('appscale-api-server')


class LogWriter(object):
    """ Sends request logs to the log server. """
    # The number of seconds to keep an idle socket open.
    IDLE_SOCKET_TIMEOUT = 10

    def __init__(self, log_server_ip, project_id):
        """ Creates a new LogWriter.

        Args:
            log_server_ip: A string specifying the location of the log server.
            project_id: A string specifying the project ID.
        """
        self.log_server_ip = log_server_ip
        self.project_id = project_id

        self._queue = Queue()
        self._worker_socket = None
        self._worker_thread = threading.Thread(target=self._worker)
        self._worker_thread.setDaemon(True)
        self._worker_thread.start()

    def write_async(self, request_log):
        """ Schedule a request log to be sent to the log server.

        Args:
            request_log: A RequestLog object.
        """
        self._queue.put(request_log)

    def _worker(self):
        """ Fetches logs from the queue and sends them to the log server. """
        while True:
            try:
                self._process_logs()
            # Ensure the worker never dies. Otherwise, request logs will just
            # pile up in the queue without getting stored.
            except Exception:
                logger.exception('Unexpected exception when sending logs')

    def _process_logs(self):
        """ Fetches logs from the queue and sends them to the log server. """
        while True:
            timeout = None
            if self._worker_socket is not None:
                timeout = self.IDLE_SOCKET_TIMEOUT

            try:
                request_log = self._queue.get(timeout=timeout)
            except Empty:
                if self._worker_socket is not None:
                    self._worker_socket.close()
                    self._worker_socket = None
                continue

            message = request_log.to_capnp().to_bytes()
            self._send_message(message)

    @retry(retry_on_exception=socket.error, backoff_threshold=60,
           max_retries=None, retrying_timeout=None)
    def _send_message(self, message):
        """ Sends a log message to the log server.

        Args:
            message: A string containing the capnp-encoded request log.
        """
        if self._worker_socket is None:
            self._worker_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                self._worker_socket.connect((self.log_server_ip, LOG_SERVER_PORT))
            except socket.error:
                self._worker_socket.close()
                self._worker_socket = None
                raise

            # Set project ID for the socket.
            length = struct.pack('I', len(self.project_id))
            full_message = ''.join([ClientActions.SET_PROJECT, length,
                                    self.project_id])
            try:
                self._worker_socket.sendall(full_message)
            except socket.error:
                self._worker_socket.close()
                self._worker_socket = None
                raise

        length = struct.pack('I', len(message))
        full_message = ''.join([ClientActions.WRITE_LOG, length, message])
        try:
            self._worker_socket.sendall(full_message)
        except socket.error:
            self._worker_socket.close()
            self._worker_socket = None
            raise
