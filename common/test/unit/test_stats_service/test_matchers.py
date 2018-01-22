import unittest
import re

from appscale.common.service_stats import matchers
from appscale.common.service_stats.stats_manager import (
  ServiceStats, DEFAULT_REQUEST_FIELDS
)


RequestInfo = ServiceStats.generate_request_model(DEFAULT_REQUEST_FIELDS)


class TestBuiltinMatchers(unittest.TestCase):
  def test_any(self):
    req_a = RequestInfo(method="HEAD", resource="/v2/endpoint/")
    req_b = RequestInfo(method="PUT")
    meaningless = object()
    self.assertEqual(matchers.ANY.matches(req_a), True)
    self.assertEqual(matchers.ANY.matches(req_b), True)
    self.assertEqual(matchers.ANY.matches(meaningless), True)

  def test_client_error(self):
    req_200 = RequestInfo(status=200)
    req_302 = RequestInfo(status=302)
    req_399 = RequestInfo(status=399)
    req_400 = RequestInfo(status=400)
    req_403 = RequestInfo(status=403)
    req_499 = RequestInfo(status=499)
    req_500 = RequestInfo(status=500)
    self.assertEqual(matchers.CLIENT_ERROR.matches(req_200), False)
    self.assertEqual(matchers.CLIENT_ERROR.matches(req_302), False)
    self.assertEqual(matchers.CLIENT_ERROR.matches(req_399), False)
    self.assertEqual(matchers.CLIENT_ERROR.matches(req_400), True)
    self.assertEqual(matchers.CLIENT_ERROR.matches(req_403), True)
    self.assertEqual(matchers.CLIENT_ERROR.matches(req_499), True)
    self.assertEqual(matchers.CLIENT_ERROR.matches(req_500), False)

  def test_server_error(self):
    req_200 = RequestInfo(status=200)
    req_302 = RequestInfo(status=302)
    req_399 = RequestInfo(status=399)
    req_499 = RequestInfo(status=499)
    req_500 = RequestInfo(status=500)
    req_502 = RequestInfo(status=502)
    req_599 = RequestInfo(status=599)
    self.assertEqual(matchers.SERVER_ERROR.matches(req_200), False)
    self.assertEqual(matchers.SERVER_ERROR.matches(req_302), False)
    self.assertEqual(matchers.SERVER_ERROR.matches(req_399), False)
    self.assertEqual(matchers.SERVER_ERROR.matches(req_499), False)
    self.assertEqual(matchers.SERVER_ERROR.matches(req_500), True)
    self.assertEqual(matchers.SERVER_ERROR.matches(req_502), True)
    self.assertEqual(matchers.SERVER_ERROR.matches(req_599), True)


class TestCustomMatcher(unittest.TestCase):

  CustomRequest = ServiceStats.generate_request_model([
    'action', 'status'
  ])

  class CustomMatcher(matchers.RequestMatcher):
    def __init__(self, pattern):
      self.pattern = re.compile(pattern)

    def matches(self, request_info):
      return bool(self.pattern.match(request_info.action))

  def test_custom_matcher(self):
    user_request = self.CustomMatcher("\w+_user")
    create_user = self.CustomRequest(action="create_user")
    get_user = self.CustomRequest(action="get_user")
    list_product = self.CustomRequest(action="list_product")
    self.assertEqual(user_request.matches(create_user), True)
    self.assertEqual(user_request.matches(get_user), True)
    self.assertEqual(user_request.matches(list_product), False)
