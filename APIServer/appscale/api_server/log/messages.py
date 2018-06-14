""" LogService message containers. """

from __future__ import division

import base64
import time
from collections import deque

import capnp

from appscale.api_server.log import log_service_pb2
from appscale.api_server.log.constants import InvalidRequest
from appscale.common.constants import LOGGING_CAPNP

capnp.remove_import_hook()
logging_capnp = capnp.load(LOGGING_CAPNP)


class LogQuery(object):
    """ Represents a query to the LogService. """
    # The number of request logs to fetch by default.
    DEFAULT_READ_COUNT = 20

    # Protobuffer fields that are named differently than the attributes.
    PROTO_FIELDS = {'request_id': 'request_ids'}

    # Cap'n Proto fields that are named differently than the attributes.
    CAPNP_FIELDS = {'startTime': 'start_time',
                    'endTime': 'end_time',
                    'minimumLogLevel': 'minimum_log_level',
                    'includeAppLogs': 'include_app_logs',
                    'requestIds': 'request_ids'}

    def __init__(self, service_id, version_id):
        """ Creates a new LogQuery object.

        Args:
            service_id: A string specifying the service ID.
            version_id: A string specifying the version ID.
        """
        self.service_id = service_id
        self.version_id = version_id
        self.start_time = None  # Unix timestamp in microseconds
        self.end_time = None  # Unix timestamp in microseconds
        self.offset = None
        self.minimum_log_level = None
        self.include_app_logs = False
        self.request_ids = []
        self.count = self.DEFAULT_READ_COUNT

    @classmethod
    def from_pb(cls, request):
        """ Creates a new LogQuery from a LogReadRequest. """
        try:
            module_version = request.module_version[0]
        except IndexError:
            raise InvalidRequest('Request must contain module_version field')

        if not module_version.version_id:
            raise InvalidRequest('Request must set module_version.version_id')

        # A request list conflicts with other filters.
        conflicting_fields = ['start_time', 'end_time', 'offset']
        for field in conflicting_fields:
            if request.request_id and request.HasField(field):
                raise InvalidRequest(
                    "request_id and {} can't both be specified".format(field))

        query = LogQuery(module_version.module_id, module_version.version_id)
        for pb_field in ['start_time', 'end_time', 'minimum_log_level',
                         'include_app_logs', 'count']:
            field = cls.PROTO_FIELDS.get(pb_field, pb_field)
            if request.HasField(pb_field):
                setattr(query, field, getattr(request, pb_field))

        if request.request_id:
            query.request_ids = request.request_id

        if request.HasField('offset'):
            query.offset = base64.b64decode(request.offset.request_id)

        return query

    def to_capnp(self):
        """ Creates a new capnp Query object. """
        query = logging_capnp.Query.new_message()
        query.versionIds = [':'.join([self.service_id, self.version_id])]

        for capnp_field in ['startTime', 'endTime', 'offset',
                            'minimumLogLevel', 'includeAppLogs']:
            field = self.CAPNP_FIELDS.get(capnp_field, capnp_field)
            value = getattr(self, field)
            if value is not None:
                setattr(query, capnp_field, value)

        if self.request_ids:
            query.requestIds = self.request_ids
        else:
            query.count = self.count

        # GAE presents logs in reverse chronological order. This is not an
        # option available to users in GAE, so we always set it to True.
        query.reverse = True

        return query


class AppLog(object):
    """ Represents an application log line. """
    __slots__ = ['time', 'level', 'message']

    def __init__(self, timestamp, level, message):
        """ Creates a new AppLog object.

        Args:
            timestamp: An integer specifying a unix timestamp in microseconds.
            level: An integer specifying a logging level.
            message: A string containing the log line.
        """
        self.time = timestamp  # Unix timestamp in microseconds
        self.level = level
        self.message = message

    @staticmethod
    def from_pb(app_log_pb):
        """ Creates a new AppLog from a LogLine. """
        if isinstance(app_log_pb, log_service_pb2.LogLine):
            time = app_log_pb.time
            message = app_log_pb.log_message
        elif isinstance(app_log_pb, log_service_pb2.UserAppLogLine):
            time = app_log_pb.timestamp_usec
            message = app_log_pb.message
        else:
            raise InvalidRequest('Incompatible protobuffer type')

        return AppLog(time, app_log_pb.level, message)

    @staticmethod
    def from_capnp(capnp_line):
        """ Creates a new AppLog from a capnp AppLog. """
        return AppLog(capnp_line.time, capnp_line.level, capnp_line.message)

    def to_capnp(self):
        """ Creates a new capnp AppLog object. """
        log_line = logging_capnp.AppLog.new_message()
        log_line.time = self.time
        log_line.level = self.level
        log_line.message = self.message
        return log_line


class RequestLog(object):
    """ Represents an application request log. """
    # The maximum number of application logs for a given request.
    MAX_APP_LOGS = 1000

    # Protobuffer fields that are named differently than the attributes.
    PROTO_FIELDS = {'app_id': 'project_id',
                    'module_id': 'service_id'}

    # Cap'n Proto fields that are named differently than the attributes.
    CAPNP_FIELDS = {'appId': 'project_id',
                    'moduleId': 'service_id',
                    'versionId': 'version_id',
                    'requestId': 'request_id',
                    'startTime': 'start_time',
                    'endTime': 'end_time',
                    'httpVersion': 'http_version',
                    'responseSize': 'response_size',
                    'userAgent': 'user_agent',
                    'appLogs': 'app_logs'}

    def __init__(self, request_id, project_id, service_id, version_id, ip,
                 nickname, user_agent, host, method, resource, http_version):
        """ Creates a new RequestLog object.

        Args:
            request_id: A string specifying the request ID.
            project_id: A string specifying the project ID.
            service_id: A string specifying the service ID.
            version_id: A string specifying the version ID.
            ip: A string specifying the user's IP address.
            nickname: A string representing the user that made the request.
            user_agent: A string specifying the user agent.
            host: A string specifying the host that received the request.
            method: A string specifying the HTTP method.
            resource: A string specifying the path and parameters.
            http_version: A string specifying the HTTP version.
        """
        self.request_id = request_id
        self.project_id = project_id
        self.service_id = service_id
        self.version_id = version_id
        self.ip = ip
        self.nickname = nickname
        self.user_agent = user_agent
        self.host = host
        self.method = method
        self.resource = resource
        self.http_version = http_version

        self.status = None
        self.response_size = None

        # Unix timestamps in microseconds
        self.start_time = int(time.time() * 1000 * 1000)
        self.end_time = None

        self.offset = None
        self.app_logs = deque(maxlen=self.MAX_APP_LOGS)

    @property
    def combined(self):
        """ A string representing the request as a combined log entry. """
        timestamp = time.localtime(self.end_time / 1000 / 1000)
        date = time.strftime('%d/%b/%Y:%H:%M:%S %z', timestamp)
        return ('{ip} - {nickname} [{date}] "{method} {resource} HTTP/{ver}" '
                '{status} {size} "{ua}"').format(
            ip=self.ip, nickname=self.nickname, date=date, method=self.method,
            resource=self.resource, ver=self.http_version, status=self.status,
            size=self.response_size, ua=self.user_agent)

    @staticmethod
    def from_capnp(log):
        """ Creates a RequestLog from a capnp RequestLog. """
        service_id = 'default'
        if ':' in log.versionId:
            service_id, version_id = log.versionId.split(':')
        else:
            version_id = log.versionId

        request_log = RequestLog(
            log.requestId, log.appId, service_id, version_id, log.ip, log.nickname,
            log.userAgent, log.host, log.method, log.resource, log.httpVersion)

        request_log.status = log.status
        request_log.response_size = log.responseSize
        request_log.start_time = log.startTime
        request_log.end_time = log.endTime
        if log.offset:
            request_log.offset = log.offset

        request_log.app_logs.extend(
            [AppLog.from_capnp(line) for line in log.appLogs])
        return request_log

    def to_capnp(self):
        """ Creates a capnp RequestLog. """
        request_log = logging_capnp.RequestLog.new_message()
        for capnp_field in ['requestId', 'appId', 'ip', 'nickname', 'userAgent',
                            'host', 'method', 'resource', 'httpVersion', 'status',
                            'responseSize', 'offset', 'startTime', 'endTime']:
            field = self.CAPNP_FIELDS.get(capnp_field, capnp_field)
            value = getattr(self, field)
            if value is not None:
                setattr(request_log, capnp_field, value)

        request_log.versionId = ':'.join([self.service_id, self.version_id])
        app_logs = request_log.init('appLogs', len(self.app_logs))
        for index, line in enumerate(self.app_logs):
            app_logs[index] = line.to_capnp()

        return request_log

    def to_pb(self, include_app_logs):
        """ Creates a protocol buffer RequestLog. """
        request_log = log_service_pb2.RequestLog()
        for pb_field in ['request_id', 'app_id', 'module_id', 'version_id', 'ip',
                         'nickname', 'user_agent', 'host', 'method', 'resource',
                         'http_version', 'status', 'response_size', 'combined',
                         'start_time', 'end_time']:
            field = self.PROTO_FIELDS.get(pb_field, pb_field)
            value = getattr(self, field)
            if value is not None:
                setattr(request_log, pb_field, value)

        if self.offset:
            request_log.offset.request_id = base64.b64encode(self.offset)

        # TODO: Implement the following fields.
        request_log.latency = 0
        request_log.mcycles = 0
        request_log.url_map_entry = ''

        if include_app_logs:
            for line in self.app_logs:
                log_line = request_log.line.add()
                log_line.time = line.time
                log_line.level = line.level
                log_line.log_message = line.message

        return request_log
