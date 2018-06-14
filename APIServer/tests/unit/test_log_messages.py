from appscale.api_server.log.messages import (AppLog, logging_capnp, LogQuery,
                                              RequestLog)
from appscale.api_server.log import log_service_pb2
import unittest
import time
import base64

LOG_LEVEL_INFO = 1
LOG_LEVEL_WARNING = 2

MESSAGE_1 = 'show me what you got'

PROJECT = 'guestbook'

TIMESTAMP = time.time()
TIMESTAMP_USEC = int(TIMESTAMP * 1000 * 1000)


class TestAppLog(unittest.TestCase):
    def test_from_pb(self):
        # Test creating an AppLog from a LogLine.
        line_pb = log_service_pb2.LogLine()
        line_pb.time = TIMESTAMP_USEC
        line_pb.level = LOG_LEVEL_INFO
        line_pb.log_message = MESSAGE_1
        app_log = AppLog.from_pb(line_pb)
        self.assertEqual(app_log.time, TIMESTAMP_USEC)
        self.assertEqual(app_log.level, LOG_LEVEL_INFO)
        self.assertEqual(app_log.message, MESSAGE_1)

        # Test creating an AppLog from a UserAppLogLine.
        line_pb = log_service_pb2.UserAppLogLine()
        line_pb.timestamp_usec = TIMESTAMP_USEC
        line_pb.level = LOG_LEVEL_WARNING
        line_pb.message = MESSAGE_1
        app_log = AppLog.from_pb(line_pb)
        self.assertEqual(app_log.time, TIMESTAMP_USEC)
        self.assertEqual(app_log.level, LOG_LEVEL_WARNING)
        self.assertEqual(app_log.message, MESSAGE_1)

    def test_from_capnp(self):
        line = logging_capnp.AppLog.new_message()
        line.time = TIMESTAMP_USEC
        line.level = LOG_LEVEL_INFO
        line.message = MESSAGE_1
        app_log = AppLog.from_capnp(line)
        self.assertEqual(app_log.time, TIMESTAMP_USEC)
        self.assertEqual(app_log.level, LOG_LEVEL_INFO)
        self.assertEqual(app_log.message, MESSAGE_1)

    def test_to_capnp(self):
        app_log = AppLog(TIMESTAMP_USEC, LOG_LEVEL_INFO, MESSAGE_1)
        line_capnp = app_log.to_capnp()
        self.assertEqual(line_capnp.time, TIMESTAMP_USEC)
        self.assertEqual(line_capnp.level, LOG_LEVEL_INFO)
        self.assertEqual(line_capnp.message, MESSAGE_1)
        # Ensure no exceptions are raised when serializing message.
        line_capnp.to_bytes()


class TestLogQuery(unittest.TestCase):
    def test_from_pb(self):
        request = log_service_pb2.LogReadRequest()
        request.app_id = PROJECT
        module_version = request.module_version.add()
        module_version.module_id = 'default'
        module_version.version_id = 'v1'
        request.start_time = TIMESTAMP_USEC
        request.end_time = TIMESTAMP_USEC
        request.offset.request_id = base64.b64encode('request1')
        request.minimum_log_level = LOG_LEVEL_INFO
        request.include_app_logs = True
        request.count = 5
        log_query = LogQuery.from_pb(request)
        self.assertEqual(log_query.service_id, 'default')
        self.assertEqual(log_query.version_id, 'v1')
        self.assertEqual(log_query.start_time, TIMESTAMP_USEC)
        self.assertEqual(log_query.end_time, TIMESTAMP_USEC)
        self.assertEqual(log_query.offset, 'request1')
        self.assertEqual(log_query.minimum_log_level, LOG_LEVEL_INFO)
        self.assertEqual(log_query.include_app_logs, True)
        self.assertListEqual(log_query.request_ids, [])
        self.assertEqual(log_query.count, 5)

    def test_to_capnp(self):
        log_query = LogQuery('default', 'v1')
        log_query.start_time = TIMESTAMP_USEC
        log_query.end_time = TIMESTAMP_USEC
        log_query.offset = 'request1'
        log_query.minimum_log_level = LOG_LEVEL_INFO
        log_query.include_app_logs = True
        log_query.count = 5
        capnp_query = log_query.to_capnp()
        self.assertEqual(capnp_query.startTime, TIMESTAMP_USEC)
        self.assertEqual(capnp_query.endTime, TIMESTAMP_USEC)
        self.assertEqual(capnp_query.offset, 'request1')
        self.assertEqual(capnp_query.minimumLogLevel, LOG_LEVEL_INFO)
        self.assertEqual(capnp_query.includeAppLogs, True)
        self.assertListEqual(list(capnp_query.versionIds),
                             [':'.join(['default', 'v1'])])
        self.assertListEqual(list(capnp_query.requestIds), [])
        self.assertEqual(capnp_query.count, 5)
        self.assertEqual(capnp_query.reverse, True)
        # Ensure no exceptions are raised when serializing message.
        capnp_query.to_bytes()

class TestRequestLog(unittest.TestCase):
    def test_from_capnp(self):
        app_log_1 = logging_capnp.AppLog.new_message()
        app_log_1.time = TIMESTAMP_USEC
        app_log_1.level = LOG_LEVEL_INFO
        app_log_1.message = MESSAGE_1

        app_log_2 = logging_capnp.AppLog.new_message()
        app_log_2.time = TIMESTAMP_USEC
        app_log_2.level = LOG_LEVEL_WARNING
        app_log_2.message = MESSAGE_1

        request_log_capnp = logging_capnp.RequestLog.new_message()
        request_log_capnp.requestId = 'request1'
        request_log_capnp.appId = PROJECT
        request_log_capnp.versionId = 'service1:v1'
        request_log_capnp.ip = '192.168.33.9'
        request_log_capnp.nickname = 'bob'
        request_log_capnp.userAgent = 'ua string'
        request_log_capnp.host = '192.168.33.10'
        request_log_capnp.method = 'GET'
        request_log_capnp.resource = '/'
        request_log_capnp.httpVersion = '1.0'
        request_log_capnp.status = 200
        request_log_capnp.responseSize = 100
        request_log_capnp.startTime = TIMESTAMP_USEC
        request_log_capnp.endTime = TIMESTAMP_USEC
        app_logs = request_log_capnp.init('appLogs', 2)
        app_logs[0] = app_log_1
        app_logs[1] = app_log_2

        request_log = RequestLog.from_capnp(request_log_capnp)
        self.assertEqual(request_log.request_id, 'request1')
        self.assertEqual(request_log.project_id, PROJECT)
        self.assertEqual(request_log.service_id, 'service1')
        self.assertEqual(request_log.version_id, 'v1')
        self.assertEqual(request_log.ip, '192.168.33.9')
        self.assertEqual(request_log.nickname, 'bob')
        self.assertEqual(request_log.user_agent, 'ua string')
        self.assertEqual(request_log.host, '192.168.33.10')
        self.assertEqual(request_log.method, 'GET')
        self.assertEqual(request_log.resource, '/')
        self.assertEqual(request_log.http_version, '1.0')
        self.assertEqual(request_log.status, 200)
        self.assertEqual(request_log.response_size, 100)
        self.assertEqual(request_log.start_time, TIMESTAMP_USEC)
        self.assertEqual(request_log.end_time, TIMESTAMP_USEC)
        self.assertEqual(request_log.offset, None)
        date_str = time.strftime('%d/%b/%Y:%H:%M:%S %z',
                                 time.localtime(TIMESTAMP_USEC / 1000 / 1000))
        combined = ('192.168.33.9 - bob [{}] "GET / HTTP/1.0" 200 100 '
                    '"ua string"').format(date_str)
        self.assertEqual(request_log.combined, combined)
        for index, capnp_line in enumerate([app_log_1, app_log_2]):
            pb_line = request_log.app_logs[index]
            self.assertEqual(pb_line.time, capnp_line.time)
            self.assertEqual(pb_line.level, capnp_line.level)
            self.assertEqual(pb_line.message, capnp_line.message)

    def test_to_capnp(self):
        app_logs = [AppLog(TIMESTAMP_USEC, LOG_LEVEL_INFO, MESSAGE_1),
                    AppLog(TIMESTAMP_USEC, LOG_LEVEL_WARNING, MESSAGE_1)]
        request_log = RequestLog(
            'request1', PROJECT, 'service1', 'v1', '192.168.33.9', 'bob',
            'ua string', '192.168.33.10', 'GET', '/', '1.0')
        request_log.status = 200
        request_log.response_size = 100
        request_log.start_time = TIMESTAMP_USEC
        request_log.end_time = TIMESTAMP_USEC
        request_log.app_logs = app_logs

        request_log_capnp = request_log.to_capnp()
        self.assertEqual(request_log_capnp.requestId, 'request1')
        self.assertEqual(request_log_capnp.appId, PROJECT)
        self.assertEqual(request_log_capnp.versionId, 'service1:v1')
        self.assertEqual(request_log_capnp.ip, '192.168.33.9')
        self.assertEqual(request_log_capnp.nickname, 'bob')
        self.assertEqual(request_log_capnp.userAgent, 'ua string')
        self.assertEqual(request_log_capnp.host, '192.168.33.10')
        self.assertEqual(request_log_capnp.method, 'GET')
        self.assertEqual(request_log_capnp.resource, '/')
        self.assertEqual(request_log_capnp.httpVersion, '1.0')
        self.assertEqual(request_log_capnp.status, 200)
        self.assertEqual(request_log_capnp.responseSize, 100)
        self.assertEqual(request_log_capnp.startTime, TIMESTAMP_USEC)
        self.assertEqual(request_log_capnp.endTime, TIMESTAMP_USEC)
        for index, line in enumerate(app_logs):
            capnp_line = request_log_capnp.appLogs[index]
            self.assertEqual(line.time, capnp_line.time)
            self.assertEqual(line.level, capnp_line.level)
            self.assertEqual(line.message, capnp_line.message)

    def test_to_pb(self):
        app_logs = [AppLog(TIMESTAMP_USEC, LOG_LEVEL_INFO, MESSAGE_1),
                    AppLog(TIMESTAMP_USEC, LOG_LEVEL_WARNING, MESSAGE_1)]
        request_log = RequestLog(
            'request1', PROJECT, 'service1', 'v1', '192.168.33.9', 'bob',
            'ua string', '192.168.33.10', 'GET', '/', '1.0')
        request_log.status = 200
        request_log.response_size = 100
        request_log.start_time = TIMESTAMP_USEC
        request_log.end_time = TIMESTAMP_USEC
        request_log.app_logs = app_logs

        request_log_pb = request_log.to_pb(include_app_logs=True)
        self.assertEqual(request_log_pb.app_id, PROJECT)
        self.assertEqual(request_log_pb.module_id, 'service1')
        self.assertEqual(request_log_pb.version_id, 'v1')
        self.assertEqual(request_log_pb.request_id, 'request1')
        self.assertEqual(request_log_pb.ip, '192.168.33.9')
        self.assertEqual(request_log_pb.nickname, 'bob')
        self.assertEqual(request_log_pb.start_time, TIMESTAMP_USEC)
        self.assertEqual(request_log_pb.end_time, TIMESTAMP_USEC)
        self.assertEqual(request_log_pb.method, 'GET')
        self.assertEqual(request_log_pb.resource, '/')
        self.assertEqual(request_log_pb.http_version, '1.0')
        self.assertEqual(request_log_pb.status, 200)
        self.assertEqual(request_log_pb.response_size, 100)
        self.assertEqual(request_log_pb.user_agent, 'ua string')
        self.assertEqual(request_log_pb.host, '192.168.33.10')
        self.assertEqual(request_log_pb.finished, True)
        for index, line in enumerate(app_logs):
            pb_line = request_log_pb.line[index]
            self.assertEqual(line.time, pb_line.time)
            self.assertEqual(line.level, pb_line.level)
            self.assertEqual(line.message, pb_line.log_message)
