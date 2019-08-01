from mock import patch, MagicMock, call
from tornado import testing, gen

from appscale.common import async_retrying


class TestRetryCoroutine(testing.AsyncTestCase):

  @patch.object(async_retrying.gen, 'sleep')
  @patch.object(async_retrying.logger, 'error')
  @patch.object(async_retrying.logger, 'warning')
  @testing.gen_test
  def test_no_errors(self, warning_mock, error_mock, sleep_mock):
    sleep_mock.side_effect = testing.gen.coroutine(lambda sec: sec)

    @async_retrying.retry_coroutine
    def no_errors():
      raise gen.Return("No Errors")

    result = yield no_errors()

    # Assert outcomes.
    self.assertEqual(result, "No Errors")
    self.assertEqual(sleep_mock.call_args_list, [])
    self.assertEqual(warning_mock.call_args_list, [])
    self.assertEqual(error_mock.call_args_list, [])

  @patch.object(async_retrying.gen, 'sleep')
  @patch.object(async_retrying.logger, 'error')
  @patch.object(async_retrying.logger, 'warning')
  @patch.object(async_retrying.random, 'random')
  @testing.gen_test
  def test_backoff_and_logging(self, random_mock, warning_mock, error_mock,
                               sleep_mock):
    random_value = 0.84
    random_mock.return_value = random_value
    sleep_mock.side_effect = testing.gen.coroutine(lambda sec: None)

    @async_retrying.retry_coroutine(
      backoff_base=3, backoff_multiplier=0.1, backoff_threshold=2,
      max_retries=4)
    def do_work():
      raise ValueError(u"Error \u26a0!")

    try:
      yield do_work()
      self.fail("Exception was expected")
    except ValueError:
      pass

    # Check backoff sleep calls (0.1 * (3 ** attempt) * random_value).
    sleep_args = [args[0] for args, kwargs in sleep_mock.call_args_list]
    self.assertAlmostEqual(sleep_args[0], 0.33, 2)
    self.assertAlmostEqual(sleep_args[1], 0.99, 2)
    self.assertAlmostEqual(sleep_args[2], 2.2, 2)
    self.assertAlmostEqual(sleep_args[3], 2.2, 2)

    # Verify logged warnings.
    expected_warnings = [
      "Retry #1 in 0.3s",
      "Retry #2 in 1.0s",
      "Retry #3 in 2.2s",
      "Retry #4 in 2.2s",
    ]
    self.assertEqual(len(expected_warnings), len(warning_mock.call_args_list))
    expected_messages = iter(expected_warnings)
    for call_args_kwargs in warning_mock.call_args_list:
      error_message = expected_messages.next()
      self.assertTrue(call_args_kwargs[0][0].startswith("Traceback"))
      self.assertTrue(call_args_kwargs[0][0].endswith(error_message))
    # Verify errors
    self.assertRegexpMatches(
      error_mock.call_args_list[0][0][0],
      "Giving up retrying after 5 attempts during -?\d+\.\d+s"
    )

  @patch.object(async_retrying.monotonic, 'monotonic')
  @patch.object(async_retrying.gen, 'sleep')
  @patch.object(async_retrying.logger, 'error')
  @patch.object(async_retrying.logger, 'warning')
  @testing.gen_test
  def test_retrying_timeout(self, warning_mock, err_mock, sleep_mock,
                            time_mock):
    times = [
      100,  # Start time.
      120,  # The first retry can go (elapsed 20s less than 50s timeout).
      140,  # The second retry can go (elapsed 40s less than 50s timeout).
      160,  # Fail (elapsed 60s greater than 50s timeout).
      180,
    ]
    times.reverse()
    time_mock.side_effect = lambda : times[-1]
    sleep_mock.side_effect = testing.gen.coroutine(lambda sec: None)

    @async_retrying.retry_coroutine(
      backoff_base=3, backoff_multiplier=0.1, backoff_threshold=2,
      max_retries=10, retrying_timeout=50)
    def do_work():
      times.pop()
      raise ValueError(u"Error \u26a0!")

    try:
      yield do_work()
      self.fail("Exception was expected")
    except ValueError:
      pass

    # Check if there were 2 retries.
    sleep_args = [args[0] for args, kwargs in sleep_mock.call_args_list]
    self.assertEqual(len(sleep_args), 2)
    self.assertEqual(len(warning_mock.call_args_list), 2)
    # Verify errors
    self.assertEqual(err_mock.call_args_list,
                     [call("Giving up retrying after 3 attempts during 60.0s")])

  @patch.object(async_retrying.gen, 'sleep')
  @testing.gen_test
  def test_exception_filter(self, sleep_mock):
    sleep_mock.side_effect = testing.gen.coroutine(lambda sec: None)

    def err_filter(exception):
      return isinstance(exception, ValueError)

    @async_retrying.retry_coroutine(retry_on_exception=err_filter)
    def func(exc_class, msg, retries_to_success):
      retries_to_success['counter'] -= 1
      if retries_to_success['counter'] <= 0:
        raise gen.Return("Succeeded")
      raise exc_class(msg)

    # Test retry helps.
    result = yield func(ValueError, "Matched", {"counter": 3})
    self.assertEqual(result, "Succeeded")

    # Test retry not applicable.
    try:
      yield func(TypeError, "Failed", {"counter": 3})
      self.fail("Exception was expected")
    except TypeError:
      pass


class TestRetryWatchCoroutine(testing.AsyncTestCase):

  @patch.object(async_retrying.locks.Condition, 'wait')
  @patch.object(async_retrying.logger, 'error')
  @patch.object(async_retrying.logger, 'warning')
  @testing.gen_test
  def test_no_errors(self, warning_mock, error_mock, wait_mock):
    wait_mock.side_effect = testing.gen.coroutine(lambda sec: sec)

    # Call dummy lambda persistently.
    persistent_work = async_retrying.retry_data_watch_coroutine(
      "node", lambda: "No Errors"
    )
    result = yield persistent_work()

    # Assert outcomes.
    self.assertEqual(result, "No Errors")
    self.assertEqual(wait_mock.call_args_list, [])
    self.assertEqual(warning_mock.call_args_list, [])
    self.assertEqual(error_mock.call_args_list, [])

  @patch.object(async_retrying.IOLoop, 'current')
  @patch.object(async_retrying.locks.Condition, 'wait')
  @patch.object(async_retrying.logger, 'error')
  @patch.object(async_retrying.logger, 'warning')
  @patch.object(async_retrying.random, 'random')
  @testing.gen_test
  def test_backoff_and_logging(self, random_mock, warning_mock, error_mock,
                               wait_mock, current_io_loop_mock):
    random_value = 0.84
    random_mock.return_value = random_value
    wait_mock.side_effect = testing.gen.coroutine(lambda sec: False)
    current_io_loop_mock.return_value = MagicMock(time=lambda: 100.0)

    def do_work():
      raise ValueError(u"Error \u26a0!")

    persistent_work = async_retrying.retry_data_watch_coroutine(
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

    # Verify logged warnings.
    expected_warnings = [
      "Retry #1 in 0.3s",
      "Retry #2 in 1.0s",
      "Retry #3 in 2.2s",
      "Retry #4 in 2.2s",
    ]
    self.assertEqual(len(expected_warnings), len(warning_mock.call_args_list))
    expected_messages = iter(expected_warnings)
    for call_args_kwargs in warning_mock.call_args_list:
      error_message = expected_messages.next()
      self.assertTrue(call_args_kwargs[0][0].startswith("Traceback"))
      self.assertTrue(call_args_kwargs[0][0].endswith(error_message))
    # Verify errors
    self.assertEqual(error_mock.call_args_list,
                     [call("Giving up retrying after 5 attempts during 0.0s")])

  @patch.object(async_retrying.locks.Condition, 'wait')
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

    wrapped = async_retrying.retry_data_watch_coroutine(
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

  @patch.object(async_retrying.locks.Condition, 'wait')
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

    wrapped = async_retrying.retry_data_watch_coroutine("node", func)

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

    wrapped = async_retrying.retry_data_watch_coroutine("node", func)

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

    wrapped = async_retrying.retry_data_watch_coroutine("node", func)

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

    wrapped_1 = async_retrying.retry_data_watch_coroutine("node-1", func)
    wrapped_2 = async_retrying.retry_data_watch_coroutine("node-2", func)
    wrapped_3 = async_retrying.retry_data_watch_coroutine("node-3", func)
    wrapped_4 = async_retrying.retry_data_watch_coroutine("node-4", func)

    yield [wrapped_1(1), wrapped_2(2), wrapped_3(3), wrapped_4(4)]
    self.assertNotEqual(shared_data, [1]*20 + [2]*20 + [3]*20 + [4]*20)
