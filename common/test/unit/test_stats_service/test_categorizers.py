import unittest

from appscale.common.service_stats import categorizers
from appscale.common.service_stats.stats_manager import UnknownRequestField


class RequestInfo(object):
  __slots__ = ["app", "service", "version", "method", "resource",
               "status", "response_size"]

  def __init__(self, **fields_dict):
    for field in self.__slots__:
      value = fields_dict.get(field)
      setattr(self, field, value)


class TestExactValueCategorizer(unittest.TestCase):
  def test_string_value(self):
    categorizer = categorizers.ExactValueCategorizer("by_method", "method")
    req_a = RequestInfo(method="HEAD", resource="/v2/endpoint/")
    req_b = RequestInfo(method="PUT")
    self.assertEqual(categorizer.category_of(req_a), "HEAD")
    self.assertEqual(categorizer.category_of(req_b), "PUT")

  def test_int_value(self):
    categorizer = categorizers.ExactValueCategorizer("by_status", "status")
    req_a = RequestInfo(method="HEAD", status=200)
    req_b = RequestInfo(method="PUT", status=302)
    self.assertEqual(categorizer.category_of(req_a), 200)
    self.assertEqual(categorizer.category_of(req_b), 302)

  def test_unknown_field(self):
    categorizer = categorizers.ExactValueCategorizer("by_mystery", "mystery")
    req = RequestInfo(method="HEAD", status=200)
    self.assertRaises(UnknownRequestField, categorizer.category_of, req)


class TestVersionCategorizer(unittest.TestCase):
  def test_normal(self):
    c = categorizers.VersionCategorizer("by_version")
    req = RequestInfo(app="ghostbook", service="default", version="v1")
    self.assertEqual(c.category_of(req), "ghostbook.default.v1")

  def test_missed_field(self):
    c = categorizers.VersionCategorizer("by_version")
    req_1 = RequestInfo(app=None, service="default", version="v1")
    req_2 = RequestInfo(app="ghostbook", service=None, version="v1")
    req_3 = RequestInfo(app="ghostbook", service="default", version=None)
    self.assertEqual(c.category_of(req_1), "None.default.v1")
    self.assertEqual(c.category_of(req_2), "ghostbook.None.v1")
    self.assertEqual(c.category_of(req_3), "ghostbook.default.None")


class TestStatusCategorizer(unittest.TestCase):
  def test_1xx_2xx_3xx_4xx_5xx_value(self):
    c = categorizers.StatusCategorizer("by_status")
    self.assertEqual(c.category_of(RequestInfo(status=100)), "1xx")
    self.assertEqual(c.category_of(RequestInfo(status=101)), "1xx")
    self.assertEqual(c.category_of(RequestInfo(status=200)), "2xx")
    self.assertEqual(c.category_of(RequestInfo(status=201)), "2xx")
    self.assertEqual(c.category_of(RequestInfo(status=300)), "3xx")
    self.assertEqual(c.category_of(RequestInfo(status=301)), "3xx")
    self.assertEqual(c.category_of(RequestInfo(status=302)), "3xx")
    self.assertEqual(c.category_of(RequestInfo(status=400)), "4xx")
    self.assertEqual(c.category_of(RequestInfo(status=401)), "4xx")
    self.assertEqual(c.category_of(RequestInfo(status=405)), "4xx")
    self.assertEqual(c.category_of(RequestInfo(status=500)), "5xx")
    self.assertEqual(c.category_of(RequestInfo(status=501)), "5xx")
    self.assertEqual(c.category_of(RequestInfo(status=599)), "5xx")

  def test_other_value(self):
    c = categorizers.StatusCategorizer("by_status")
    self.assertEqual(c.category_of(RequestInfo(status=10)), "other_xx")
    self.assertEqual(c.category_of(RequestInfo(status=None)), "other_xx")
    self.assertEqual(c.category_of(RequestInfo(status="other")), "other_xx")
    self.assertEqual(c.category_of(RequestInfo(status="")), "other_xx")


