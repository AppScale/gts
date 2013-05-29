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
"""Constants used for communicating with the Python devappserver2 runtime."""


SERVER_SOFTWARE = 'Development/2.0'

INTERNAL_HEADER_PREFIX = 'X-Appengine-Internal-'
INTERNAL_ENVIRON_PREFIX = 'HTTP_X_APPENGINE_INTERNAL_'

REQUEST_ID_HEADER = 'X-Appengine-Internal-Request-Id'
REQUEST_ID_ENVIRON = 'HTTP_X_APPENGINE_INTERNAL_REQUEST_ID'

ENVIRONS_TO_PROPAGATE = set([
    'BACKEND_ID',
    'DEFAULT_VERSION_HOSTNAME',
    'USER_ID',
    'USER_IS_ADMIN',
    'USER_EMAIL',
    'USER_NICKNAME',
    'USER_ORGANIZATION',
    'REMOTE_ADDR',
    'REQUEST_ID_HASH',
    'REQUEST_LOG_ID',
    'SERVER_NAME',
    'SERVER_PORT',
    'SERVER_PROTOCOL',
    ])

SCRIPT_HEADER = INTERNAL_ENVIRON_PREFIX + 'SCRIPT'
# A request header where the value is a string containing the request type, e.g.
# background.
REQUEST_TYPE_HEADER = INTERNAL_ENVIRON_PREFIX + 'REQUEST_TYPE'

# A response header used by the runtime to indicate that an uncaught error has
# ocurred and that a user-specified error handler should be used if available.
ERROR_CODE_HEADER = '%sError-Code' % INTERNAL_HEADER_PREFIX
