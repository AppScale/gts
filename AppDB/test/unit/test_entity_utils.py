#!/usr/bin/env python

""" Unit tests for entity_utils.py """

import os
import sys
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../AppServer"))
from google.appengine.datastore import entity_pb

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
import entity_utils

class FakeDatastore(object):
  def __init__(self):
    pass
  def batch_get_entity(self, table, keys, schema):
    return {}

FAKE_SERIALIZED_ENTITY = \
  {'guestbook27\x00\x00Guestbook:default_guestbook\x01Greeting:1\x01':
    {
      'txnID': '1',
      'entity': 'j@j\x0bguestbook27r1\x0b\x12\tGuestbook"\x11default_guestbook\x0c\x0b\x12\x08Greeting\x18\xaa\xe7\xfb\x18\x0cr=\x1a\x06author \x00*1CJ\x07a@a.comR\tgmail.com\x90\x01\x00\x9a\x01\x15120912168209190119424Dr\x15\x08\x07\x1a\x04date \x00*\t\x08\xf6\xfc\xd2\x92\xa4\xa3\xc3\x02z\x17\x08\x0f\x1a\x07content \x00*\x08\x1a\x06111111\x82\x01 \x0b\x12\tGuestbook"\x11default_guestbook\x0c'
    }
  }

class TestEntityUtils(unittest.TestCase):
  """
  A set of test cases for the datastore backup thread.
  """
  def test_get_root_key_from_entity_key(self):
    self.assertEquals("hi/bye\x01", entity_utils.\
      get_root_key_from_entity_key("hi/bye\x01otherstuff\x01moar"))

    self.assertEquals("hi/\x01", entity_utils.\
      get_root_key_from_entity_key("hi/\x01otherstuff\x01moar"))

  def test_get_prefix_from_entity(self):
    self.assertEquals("hi\x00bye", entity_utils.\
      get_prefix_from_entity_key("hi\x00bye\x00some\x00other\x00stuff"))

    # Test empty namespace (very common).
    self.assertEquals("hi\x00", entity_utils.\
      get_prefix_from_entity_key("hi\x00\x00some\x00other\x00stuff"))

  def test_fetch_journal_entry(self):
    flexmock(FakeDatastore()).should_receive('batch_get_entity').and_return({})
    self.assertEquals(None,
      entity_utils.fetch_journal_entry(FakeDatastore(), 'key'))

    flexmock(FakeDatastore()).should_receive('batch_get_entity').\
      and_return(FAKE_SERIALIZED_ENTITY)
    flexmock(entity_pb).should_receive('EntityProto').\
      and_return()

if __name__ == "__main__":
  unittest.main()
