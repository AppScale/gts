#!/usr/bin/env python

import json
import logging
import os
import requests
import subprocess
import sys
import unittest
import urllib
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../backup/"))
import backup_recovery_helper
import gcs_helper

FakeInvalidGCSPath = 'gs://'
FakeGCSPath = 'gs://foo/bar/baz.tar.gz'

class FakeInvalidResponse(object):
  def __init__(self):
    self.headers = {}

class FakeResponse(object):
  def __init__(self):
    self.headers = {'Location': 'some/location'}

class TestGCSHelper(unittest.TestCase):
  """ A set of test cases for the GCS helper. """

  def test_upload_to_bucket(self):
    # Suppress logging output.
    flexmock(logging).should_receive('error').and_return()

    # Test with missing local file.
    flexmock(backup_recovery_helper).should_receive('does_file_exist').\
      and_return(False)
    self.assertEquals(False, gcs_helper.upload_to_bucket(FakeGCSPath,
      'some/file'))

    # Test with invalid GCS object name.
    flexmock(backup_recovery_helper).should_receive('does_file_exist').\
      and_return(True)
    flexmock(gcs_helper).should_receive('extract_gcs_tokens').\
      and_return(('', ''))
    self.assertEquals(False, gcs_helper.upload_to_bucket(FakeInvalidGCSPath,
      'some/file'))

    # Test with valid GCS object name.
    flexmock(gcs_helper).should_receive(
      'extract_gcs_tokens').with_args(FakeGCSPath).\
      and_return(('foo', 'bar/baz.tar.gz'))
    # Test with successful POST request.
    flexmock(gcs_helper).should_receive('gcs_post_request').\
      and_return(FakeResponse())
    flexmock(gcs_helper).should_receive('gcs_put_request').and_return()
    self.assertEquals(True, gcs_helper.upload_to_bucket(FakeGCSPath,
      'some/file'))
    # Test with HTTPError from POST request.
    flexmock(gcs_helper).should_receive('gcs_post_request').\
      and_raise(requests.HTTPError)
    self.assertEquals(False, gcs_helper.upload_to_bucket(FakeGCSPath,
      'some/file'))
    # Test with missing Location from POST response.
    flexmock(gcs_helper).should_receive('gcs_post_request').\
      and_return(FakeInvalidResponse())
    self.assertEquals(False, gcs_helper.upload_to_bucket(FakeGCSPath,
      'some/file'))

    # Test with HTTPError from PUT request.
    flexmock(gcs_helper).should_receive('gcs_put_request').\
      and_raise(requests.HTTPError)
    self.assertEquals(False, gcs_helper.upload_to_bucket(FakeGCSPath,
      'some/file'))

  def test_download_from_bucket(self):
    # Suppress logging output.
    flexmock(logging).should_receive('error').and_return()

    # Test with invalid GCS object name.
    flexmock(gcs_helper).should_receive('extract_gcs_tokens').\
      and_return(('', ''))
    self.assertEquals(False, gcs_helper.download_from_bucket(FakeInvalidGCSPath,
      'some/file'))

    # Test with valid GCS object name.
    flexmock(gcs_helper).should_receive(
      'extract_gcs_tokens').with_args(FakeGCSPath).\
      and_return(('foo', 'bar/baz.tar.gz'))
    flexmock(urllib).should_receive('quote_plus').and_return('')

    # Test with unsuccessful GET request.
    response = flexmock(status_code=404)
    flexmock(gcs_helper).should_receive('gcs_get_request').\
      and_return(response)
    self.assertEquals(False, gcs_helper.download_from_bucket(FakeInvalidGCSPath,
      'some/file'))

    # Test with HTTPError from GET request.
    flexmock(gcs_helper).should_receive('gcs_get_request').\
      and_raise(requests.HTTPError)
    self.assertEquals(False, gcs_helper.download_from_bucket(FakeGCSPath,
      'some/file'))

    # Test with successful GET request.
    response = flexmock(status_code=200,
      content=json.dumps({'size': 1024, 'mediaLink': 'some/link'}))
    flexmock(gcs_helper).should_receive('gcs_get_request').\
      and_return(response)

    # Test with insufficient disk space.
    disk_stats = flexmock(f_bavail=0, f_frsize=4096)
    flexmock(os).should_receive('statvfs').and_return(disk_stats)
    self.assertEquals(False, gcs_helper.download_from_bucket(FakeGCSPath,
      'some/file'))

    # Test with sufficient disk space.
    disk_stats = flexmock(f_bavail=1024, f_frsize=4096)
    flexmock(os).should_receive('statvfs').and_return(disk_stats)
    flexmock(subprocess).should_receive('check_output').and_return()
    self.assertEquals(True, gcs_helper.download_from_bucket(FakeGCSPath,
      'some/file'))

  def test_extract_gcs_tokens(self):
    # Test normal case.
    self.assertEquals(('foo', 'bar/baz.tar.gz'),
      gcs_helper.extract_gcs_tokens(FakeGCSPath))

    # Test with invalid GCS object name.
    self.assertEquals(('', ''),
      gcs_helper.extract_gcs_tokens(FakeInvalidGCSPath))

  def test_gcs_get_request(self):
    pass

  def test_gcs_post_request(self):
    pass

  def test_gcs_put_request(self):
    pass

if __name__ == "__main__":
  unittest.main()    
