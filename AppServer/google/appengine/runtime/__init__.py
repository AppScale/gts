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




"""Define the DeadlineExceededError exception."""




try:
  BaseException
except NameError:
  BaseException = Exception


class DeadlineExceededError(BaseException):
  """Exception raised when the request reaches its overall time limit.

  Not to be confused with runtime.apiproxy_errors.DeadlineExceededError.
  That one is raised when individual API calls take too long.
  """
