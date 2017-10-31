import unittest

from mock import patch, MagicMock
from tornado import testing, gen

from appscale.admin import utils
from appscale.taskqueue.constants import InvalidQueueConfiguration


class TestUtils(unittest.TestCase):
  def test_apply_mask_to_version(self):
    given_version = {'runtime': 'python27',
                     'appscaleExtensions': {'httpPort': 80}}
    desired_fields = ['appscaleExtensions.httpPort']
    self.assertDictEqual(
      utils.apply_mask_to_version(given_version, desired_fields),
      {'appscaleExtensions': {'httpPort': 80}})

    given_version = {'appscaleExtensions': {'httpPort': 80, 'httpsPort': 443}}
    desired_fields = ['appscaleExtensions.httpPort',
                      'appscaleExtensions.httpsPort']
    self.assertDictEqual(
      utils.apply_mask_to_version(given_version, desired_fields),
      {'appscaleExtensions': {'httpPort': 80, 'httpsPort': 443}})

    given_version = {'runtime': 'python27'}
    desired_fields = ['appscaleExtensions.httpPort',
                      'appscaleExtensions.httpsPort']
    self.assertDictEqual(
      utils.apply_mask_to_version(given_version, desired_fields), {})

    given_version = {'runtime': 'python27',
                     'appscaleExtensions': {'httpPort': 80, 'httpsPort': 443}}
    desired_fields = ['appscaleExtensions']
    self.assertDictEqual(
      utils.apply_mask_to_version(given_version, desired_fields),
      {'appscaleExtensions': {'httpPort': 80, 'httpsPort': 443}})

  def test_validate_queue(self):
    valid_queues = [
      {'name': 'queue-1', 'rate': '5/s'},
      {'name': 'fooqueue', 'rate': '1/s',
       'retry_parameters': {'task_retry_limit': 7, 'task_age_limit': '2d'}},
      {'name': 'fooqueue', 'mode': 'pull'}
    ]
    invalid_queues = [
      {'name': 'a' * 101, 'rate': '5/s'},  # Name is too long.
      {'name': '*', 'rate': '5/s'},  # Invalid characters in name.
      {'name': 'fooqueue', 'rate': '5/y'},  # Invalid unit of time.
      {'name': 'fooqueue'},  # Push queues must specify rate.
      {'name': 'fooqueue', 'mode': 'pull',
       'retry_parameters': {'task_retry_limit': 'a'}}  # Invalid retry value.
    ]
    for queue in valid_queues:
      utils.validate_queue(queue)

    for queue in invalid_queues:
      self.assertRaises(InvalidQueueConfiguration, utils.validate_queue, queue)


class TestRetryCoroutine(testing.AsyncTestCase):

  @patch.object(utils.locks.Condition, 'wait')
  @patch.object(utils.logger, 'error')
  @testing.gen_test
  def test_no_errors(self, logger_mock, wait_mock):
    wait_mock.side_effect = testing.gen.coroutine(lambda sec: sec)

    # Call dummy lambda persistently.
    persistent_work = utils.retry_data_watch_coroutine(
      "node", lambda: "No Errors"
    )
    result = yield persistent_work()

    # Assert outcomes.
    self.assertEqual(result, "No Errors")
    self.assertEqual(wait_mock.call_args_list, [])
    self.assertEqual(logger_mock.call_args_list, [])

  @patch.object(utils.IOLoop, 'current')
  @patch.object(utils.locks.Condition, 'wait')
  @patch.object(utils.logger, 'exception')
  @patch.object(utils.random, 'random')
  @testing.gen_test
  def test_backoff_and_logging(self, gauss_mock, logger_mock, wait_mock,
                               current_io_loop_mock):
    random_value = 0.84
    gauss_mock.return_value = random_value
    wait_mock.side_effect = testing.gen.coroutine(lambda sec: False)
    current_io_loop_mock.return_value = MagicMock(time=lambda: 100.0)

    def do_work():
      raise ValueError(u"Error \u26a0!")

    persistent_work = utils.retry_data_watch_coroutine(
      "node", do_work, backoff_base=3, backoff_multiplier=0.1,
      backoff_threshold=2, max_retries=4
    )
    try:
      yield persistent_work()
      self.fail("Exception was expected")
    except ValueError:
      pass

    # Check backoff sleep calls (0.1 * (3 ** attempt) * random_value).
    sleep_args = [args[0] for args, kwargs in wait_mock.call_args_list]
    self.assertAlmostEqual(sleep_args[0], 100.33, 2)
    self.assertAlmostEqual(sleep_args[1], 100.99, 2)
    self.assertAlmostEqual(sleep_args[2], 102.2, 2)
    self.assertAlmostEqual(sleep_args[3], 102.2, 2)

    # Verify logged errors.
    expected_logs = [
      "Retry #1 in 0.3s",
      "Retry #2 in 1.0s",
      "Retry #3 in 2.2s",
      "Retry #4 in 2.2s",
    ]
    self.assertEqual(len(expected_logs), len(logger_mock.call_args_list))
    expected_messages = iter(expected_logs)
    for call_args_kwargs in logger_mock.call_args_list:
      error_message = expected_messages.next()
      self.assertEqual(call_args_kwargs[0][0], error_message)

  @patch.object(utils.locks.Condition, 'wait')
  @testing.gen_test
  def test_exception_filter(self, wait_mock):
    wait_mock.side_effect = testing.gen.coroutine(lambda sec: False)

    def func(exc_class, msg, retries_to_success):
      retries_to_success['counter'] -= 1
      if retries_to_success['counter'] <= 0:
        return "Succeeded"
      raise exc_class(msg)

    def err_filter(exception):
      return isinstance(exception, ValueError)

    wrapped = utils.retry_data_watch_coroutine(
      "node", func, retry_on_exception=err_filter
    )

    # Test retry helps.
    result = yield wrapped(ValueError, "Matched", {"counter": 3})
    self.assertEqual(result, "Succeeded")

    # Test retry not applicable.
    try:
      yield wrapped(TypeError, "Failed", {"counter": 3})
      self.fail("Exception was expected")
    except TypeError:
      pass

  @patch.object(utils.locks.Condition, 'wait')
  @testing.gen_test
  def test_wrapping_coroutine(self, wait_mock):
    wait_mock.side_effect = testing.gen.coroutine(lambda sec: False)

    attempt = {'i': 0}

    @gen.coroutine
    def func(increment):
      if attempt['i'] <= 4:
        attempt['i'] += increment
        raise ValueError("First should be greater than second")
      raise gen.Return(attempt)

    wrapped = utils.retry_data_watch_coroutine("node", func)

    # Test retry helps.
    result = yield wrapped(2)
    self.assertEqual(result, {'i': 6})

  @testing.gen_test
  def test_concurrency_without_failures(self):
    shared_data = []

    @gen.coroutine
    def func(call_arg):
      for _ in xrange(20):
        # Let tornado chance to switch to another coroutine.
        yield gen.sleep(0.001)
        shared_data.append(call_arg)

    wrapped = utils.retry_data_watch_coroutine("node", func)

    yield [wrapped(1), wrapped(2), wrapped(3), wrapped(4)]
    # We expect that calls will be handled one by one without collisions.
    self.assertEqual(shared_data, [1]*20 + [2]*20 + [3]*20 + [4]*20)

  @testing.gen_test
  def test_concurrency_with_failures(self):
    shared_data = []

    @gen.coroutine
    def func(call_arg):
      for _ in xrange(3):
        yield gen.sleep(0.001)
        shared_data.append(call_arg)
      if call_arg != 4:
        raise ValueError("Why not 4?")

    wrapped = utils.retry_data_watch_coroutine("node", func)

    yield [wrapped(1), wrapped(2), wrapped(3), wrapped(4)]
    self.assertEqual(shared_data, [1]*3 + [2]*3 + [3]*3 + [4]*3)

  @testing.gen_test
  def test_concurrency_between_different_nodes(self):
    shared_data = []

    @gen.coroutine
    def func(call_arg):
      for _ in xrange(20):
        yield gen.sleep(0.001)
        shared_data.append(call_arg)

    wrapped_1 = utils.retry_data_watch_coroutine("node-1", func)
    wrapped_2 = utils.retry_data_watch_coroutine("node-2", func)
    wrapped_3 = utils.retry_data_watch_coroutine("node-3", func)
    wrapped_4 = utils.retry_data_watch_coroutine("node-4", func)

    yield [wrapped_1(1), wrapped_2(2), wrapped_3(3), wrapped_4(4)]
    self.assertNotEqual(shared_data, [1]*20 + [2]*20 + [3]*20 + [4]*20)
