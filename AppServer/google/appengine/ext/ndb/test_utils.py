"""Test utilities for writing NDB tests.

Useful set of utilities for correctly setting up the appengine testing
environment.  Functions and test-case base classes that configure stubs
and other environment variables.
"""

import logging
import unittest

from google.appengine.ext import testbed

from . import model
from . import tasklets
from . import eventloop


class NDBTest(unittest.TestCase):
  """Base class for tests that interact with API stubs or create Models.

  NOTE: Care must be used when working with model classes using this test
  class.  The kind-map is reset on each iteration.  The general practice
  should be to declare test models in the sub-classes setUp method AFTER
  calling this classes setUp method.
  """

  APP_ID = '_'

  def setUp(self):
    """Set up test framework.

    Configures basic environment variables, stubs and creates a default
    connection.
    """
    self.testbed = testbed.Testbed()
    self.testbed.setup_env(app_id=self.APP_ID)
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()
    self.testbed.init_taskqueue_stub()

    self.conn = model.make_connection()

    self.ResetKindMap()
    self.SetupContextCache()

    self._logger = logging.getLogger()
    self._old_log_level = self._logger.getEffectiveLevel()

  def ExpectErrors(self):
    if self.DefaultLogging():
      self._logger.setLevel(logging.CRITICAL)

  def ExpectWarnings(self):
    if self.DefaultLogging():
      self._logger.setLevel(logging.ERROR)

  def DefaultLogging(self):
    return self._old_log_level == logging.WARNING

  def tearDown(self):
    """Tear down test framework."""
    self._logger.setLevel(self._old_log_level)
    ev = eventloop.get_event_loop()
    stragglers = 0
    while ev.run1():
      stragglers += 1
    if stragglers:
      logging.info('Processed %d straggler events after test completed',
                   stragglers)
    self.ResetKindMap()
    self.testbed.deactivate()

  def ResetKindMap(self):
    model.Model._reset_kind_map()

  def SetupContextCache(self):
    """Set up the context cache.

    We only need cache active when testing the cache, so the default behavior
    is to disable it to avoid misleading test results. Override this when
    needed.
    """
    ctx = tasklets.make_default_context()
    tasklets.set_context(ctx)
    ctx.set_cache_policy(False)
    ctx.set_memcache_policy(False)
