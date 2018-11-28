import unittest
from mock import patch, call

from appscale.common import retrying


class TestRetry(unittest.TestCase):

  @patch.object(retrying.time, 'sleep')
  @patch.object(retrying.logger, 'error')
  @patch.object(retrying.logger, 'warning')
  def test_no_errors(self, warning_mock, error_mock, sleep_mock):

    @retrying.retry
    def no_errors():
      return "No Errors"

    result = no_errors()

    # Assert outcomes.
    self.assertEqual(result, "No Errors")
    self.assertEqual(sleep_mock.call_args_list, [])
    self.assertEqual(warning_mock.call_args_list, [])
    self.assertEqual(error_mock.call_args_list, [])

  @patch.object(retrying.time, 'sleep')
  @patch.object(retrying.logger, 'error')
  @patch.object(retrying.logger, 'warning')
  @patch.object(retrying.random, 'random')
  def test_backoff_and_logging(self, random_mock, warning_mock, error_mock,
                               sleep_mock):
    random_value = 0.84
    random_mock.return_value = random_value

    @retrying.retry(
      backoff_base=3, backoff_multiplier=0.1, backoff_threshold=2,
      max_retries=4)
    def do_work():
      raise ValueError(u"Error \u26a0!")

    try:
      do_work()
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

  @patch.object(retrying.time, 'time')
  @patch.object(retrying.time, 'sleep')
  @patch.object(retrying.logger, 'error')
  @patch.object(retrying.logger, 'warning')
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

    @retrying.retry(
      backoff_base=3, backoff_multiplier=0.1, backoff_threshold=2,
      max_retries=10, retrying_timeout=50)
    def do_work():
      times.pop()
      raise ValueError(u"Error \u26a0!")

    try:
      do_work()
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

  @patch.object(retrying.time, 'sleep')
  def test_exception_filter(self, sleep_mock):
    @retrying.retry(retry_on_exception=ValueError)
    def func(exc_class, msg, retries_to_success):
      retries_to_success['counter'] -= 1
      if retries_to_success['counter'] <= 0:
        return "Succeeded"
      raise exc_class(msg)

    # Test retry helps.
    result = func(ValueError, "Matched", {"counter": 3})
    self.assertEqual(result, "Succeeded")

    # Test retry not applicable.
    try:
      func(IOError, "Failed", {"counter": 3})
      self.fail("Exception was expected")
    except IOError:
      pass

  @patch.object(retrying.time, 'sleep')
  def test_exception_custom_filter(self, sleep_mock):
    def err_filter(exception):
      return isinstance(exception, ValueError)

    @retrying.retry(retry_on_exception=err_filter)
    def func(exc_class, msg, retries_to_success):
      retries_to_success['counter'] -= 1
      if retries_to_success['counter'] <= 0:
        return "Succeeded"
      raise exc_class(msg)

    # Test retry helps.
    result = func(ValueError, "Matched", {"counter": 3})
    self.assertEqual(result, "Succeeded")

    # Test retry not applicable.
    try:
      func(TypeError, "Failed", {"counter": 3})
      self.fail("Exception was expected")
    except TypeError:
      pass

  @patch.object(retrying.time, 'sleep')
  def test_exception_list_filter(self, sleep_mock):
    @retrying.retry(retry_on_exception=[ValueError, TypeError])
    def func(exc_class, msg, retries_to_success):
      retries_to_success['counter'] -= 1
      if retries_to_success['counter'] <= 0:
        return "Succeeded"
      raise exc_class(msg)

    # Test retry helps.
    result = func(ValueError, "Matched", {"counter": 3})
    self.assertEqual(result, "Succeeded")
    result = func(TypeError, "Matched", {"counter": 3})
    self.assertEqual(result, "Succeeded")

    # Test retry not applicable.
    try:
      func(Exception, "Failed", {"counter": 3})
      self.fail("Exception was expected")
    except Exception:
      pass
