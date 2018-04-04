import logging
import subprocess
import time
import urllib
from datetime import timedelta
from xml.etree import ElementTree

from tornado import gen
from tornado.httpclient import AsyncHTTPClient
from tornado.httpclient import HTTPError
from tornado.ioloop import IOLoop

from appscale.common.async_retrying import retry_coroutine
from appscale.common.retrying import retry
from . import constants
from . import misc
from .constants import MonitStates

"""
This file contains top level functions for starting and stopping
monitoring of processes using monit. Each component is in
charge of creating configuration files for the process they want started.
"""

MONIT = "/usr/bin/monit"

NUM_RETRIES = 10

SMALL_WAIT = 3
RETRYING_TIMEOUT = 60


class ProcessNotFound(Exception):
  """ Indicates that Monit has no entry for a process. """
  pass


class NotMonitCommand(Exception):
  """ Indicates that wrong command was asked to be run """
  pass


class NonZeroReturnStatus(Exception):
  """ Indicates that command returned non-zero return status """
  pass


@retry(retrying_timeout=RETRYING_TIMEOUT, backoff_multiplier=0.5,
       retry_on_exception=lambda err: not isinstance(err, NotMonitCommand))
def monit_run(args):
  """ Runs the given monit command, retrying it if it fails (which can occur if
  monit is busy servicing other requests).

  Args:
    args: A list of strs, where each str is a command-line argument for monit.
  Raises:
    NonZeroReturnStatus if command returned status different from 0.
  """
  return_status = subprocess.call([MONIT] + args)
  if return_status != 0:
    raise NonZeroReturnStatus("Command `{}` return non-zero status: {}"
                              .format(' '.join(args), return_status))


def safe_monit_run(args):
  """ Runs the given monit command, retrying it if it fails.

  Args:
    args: A list of strs, where each str is a command-line argument for monit.
  Returns:
    True if command succeeded, False otherwise.
  """
  try:
    monit_run(args)
    return True
  except NonZeroReturnStatus as err:
    logging.error(err)
    return False


def start(watch, is_group=True):
  """ Instructs monit to start the given program, assuming that a configuration
  file has already been written for it.

  Args:
    watch: A str representing the name of the program to start up and monitor.
    is_group: A bool that indicates if we want to stop a group of programs, or
      only a single program.
  Returns:
    True if the program was started, or False if (1) the named program is not a
    valid program name, (2) if monit could not be reloaded to read the new
    configuration file, or (3) monit could not start the new program.
  """
  if not misc.is_string_secure(watch):
    logging.error("Watch string [{0}] is a possible security violation".format(
      watch))
    return False

  logging.info("Reloading monit.")
  if not safe_monit_run(['reload']):
    return False

  logging.info("Starting watch {0}".format(watch))
  if is_group:
    safe_monit_run(['monitor', '-g', watch])
    return safe_monit_run(['start', '-g', watch])
  else:
    safe_monit_run(['monitor', watch])
    return safe_monit_run(['start', watch])


def stop(watch, is_group=True):
  """ Shut down the named programs monit is watching, and stop monitoring it.

  Args:
    watch: The name of the group of programs that monit is watching, that should
      no longer be watched.
    is_group: A bool that indicates if we want to stop a group of programs, or
      only a single program.
  Returns:
    True if the named programs were stopped and no longer monitored, and False
    if either (1) the named watch is not valid, (2) the programs could not be
    stopped, or (3) the programs could not be unmonitored.
  """
  if not misc.is_string_secure(watch):
    logging.error("Watch string (%s) is a possible security violation" % watch)
    return False

  logging.info("Stopping watch {0}".format(watch))
  if is_group:
    stop_command = ['stop', '-g', watch]
  else:
    stop_command = ['stop', watch]

  return safe_monit_run(stop_command)


def restart(watch):
  """ Instructs monit to restart all processes hosting the given watch.

  Args:
    watch: A str representing the name of the programs to restart.
  Returns:
    True if the programs were restarted, or False if (1) the watch is not a
    valid program name, (2) monit could not restart the new program.
  """
  if not misc.is_string_secure(watch):
    logging.error("Watch string [{0}] is a possible security violation".format(
      watch))
    return False

  logging.info("Restarting watch {0}".format(watch))
  return safe_monit_run(['restart', '-g', watch])


def parse_entries(response):
  """ Extracts each watch's status from a Monit response.

  Args:
    response: An XML string.
  Returns:
    A dictionary mapping Monit entries to their state.
  """
  root = ElementTree.XML(response)
  entries = {}
  for service in root.iter('service'):
    name = service.find('name').text
    monitored = int(service.find('monitor').text)
    status = int(service.find('status').text)
    if monitored == 0:
      entries[name] = MonitStates.UNMONITORED
    elif monitored == 1:
      if status == 0:
        entries[name] = MonitStates.RUNNING
      else:
        entries[name] = MonitStates.STOPPED
    else:
      entries[name] = MonitStates.PENDING

  return entries


class MonitOperator(object):
  """ Handles Monit operations. """

  # The location of Monit's XML API.
  LOCATION = 'http://localhost:2812'

  # The number of seconds to wait between each reload operation.
  RELOAD_COOLDOWN = 1

  def __init__(self):
    """ Creates a new MonitOperator. There should only be one. """
    self.reload_future = None
    self.client = AsyncHTTPClient()
    self.last_reload = time.time()

  @gen.coroutine
  def reload(self):
    """ Groups closely-timed reload operations. """
    if self.reload_future is None or self.reload_future.done():
      self.reload_future = self._reload()

    yield self.reload_future

  @retry_coroutine(retrying_timeout=RETRYING_TIMEOUT)
  def get_entries(self):
    """ Retrieves the status for each Monit entry.

    Returns:
      A dictionary mapping Monit entries to their state.
    """
    status_url = '{}/_status?format=xml'.format(self.LOCATION)
    response = yield self.client.fetch(status_url)
    monit_entries = parse_entries(response.body)
    raise gen.Return(monit_entries)

  @retry_coroutine(
    retrying_timeout=RETRYING_TIMEOUT,
    retry_on_exception=lambda err: not isinstance(err, ProcessNotFound))
  def send_command(self, process_name, command):
    """ Sends a command to the Monit API.

    Args:
      process_name: A string specifying a monit watch.
      command: A string specifying the command to send.
    """
    process_url = '{}/{}'.format(self.LOCATION, process_name)
    payload = urllib.urlencode({'action': command})
    try:
      yield self.client.fetch(process_url, method='POST', body=payload)
    except HTTPError as error:
      if error.code == 404:
        raise ProcessNotFound('{} is not monitored'.format(process_name))
      raise

  @gen.coroutine
  def wait_for_status(self, process_name, acceptable_states):
    """ Waits until a process is in a desired state.

    Args:
      process_name: A string specifying a monit watch.
      acceptable_states: An iterable of strings specifying states.
    """
    logging.info(
      "Waiting until process '{}' gets to one of acceptable states: {}"
       .format(process_name, acceptable_states)
    )
    start_time = time.time()
    backoff = 0.1

    while True:
      entries = yield self.get_entries()
      status = entries.get(process_name, MonitStates.MISSING)
      elapsed = time.time() - start_time

      if status in acceptable_states:
        logging.info("Status of '{}' became '{}' after {:0.1f}s"
                     .format(process_name, status, elapsed))
        raise gen.Return(status)

      if elapsed > 1:
        # Keep logs informative and don't report too early
        logging.info("Status of '{}' is not acceptable ('{}') after {:0.1f}s."
                     "Checking again in {:0.1f}s."
                     .format(process_name, status, elapsed, backoff))

      yield gen.sleep(backoff)
      backoff = min(backoff * 1.5, 5)  # Increase backoff slowly up to 5 sec.

  @gen.coroutine
  def ensure_running(self, process_name):
    """ Waits for a process to finish starting.

    Args:
      process_name: A string specifying a monit watch.
    """
    while True:
      non_missing_states = (
        MonitStates.RUNNING, MonitStates.UNMONITORED, MonitStates.PENDING,
        MonitStates.STOPPED)
      status_future = self.wait_for_status(process_name, non_missing_states)
      status = yield gen.with_timeout(timedelta(seconds=5), status_future,
                                      IOLoop.current())

      if status == constants.MonitStates.RUNNING:
        return

      if status == constants.MonitStates.UNMONITORED:
        yield self.send_command(process_name, 'start')

      yield gen.sleep(1)

  @retry_coroutine(
    retrying_timeout=RETRYING_TIMEOUT,
    retry_on_exception=[subprocess.CalledProcessError])
  def _reload(self):
    """ Reloads Monit. """
    time_since_reload = time.time() - self.last_reload
    wait_time = max(self.RELOAD_COOLDOWN - time_since_reload, 0)
    yield gen.sleep(wait_time)
    self.last_reload = time.time()
    subprocess.check_call(['monit', 'reload'])
