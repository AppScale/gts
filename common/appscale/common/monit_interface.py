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

def run_with_retry(args):
  """ Runs the given monit command, retrying it if it fails (which can occur if
  monit is busy servicing other requests).

  Args:
    args: A list of strs, where each str is a command-line argument composing
      the command to execute.
  Returns:
    True on success, and False otherwise.
  """
  if args[0] != MONIT:
    logging.error("Cannot execute command {0}, as it is not a monit command." \
      .format(args))
    return False

  retries_left = NUM_RETRIES
  while retries_left:
    return_status = subprocess.call(args)
    if return_status == 0:
      logging.info("Monit command {0} returned successfully!".format(args))
      return True

    retries_left -= 1

    logging.warning("Monit command {0} returned with status {1}, {2} retries " \
      "left.".format(args, return_status, retries_left))
    time.sleep(SMALL_WAIT)

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
  if not run_with_retry([MONIT, 'reload']):
    return False

  logging.info("Starting watch {0}".format(watch))
  if is_group:
    run_with_retry([MONIT, 'monitor', '-g', watch])
    return run_with_retry([MONIT, 'start', '-g', watch])
  else:
    run_with_retry([MONIT, 'monitor',  watch])
    return run_with_retry([MONIT, 'start', watch])


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
    stop_command = [MONIT, 'stop', '-g', watch]
  else:
    stop_command = [MONIT, 'stop', watch]

  return run_with_retry(stop_command)


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
  return run_with_retry([MONIT, 'restart', '-g', watch])


def process_status(response, process_name):
  """ Extracts a watch's status from a Monit response.

  Args:
    response: An XML string
  """
  root = ElementTree.XML(response)
  for service in root.iter('service'):
    name = service.find('name').text
    if name != process_name:
      continue

    monitored = int(service.find('monitor').text)
    status = int(service.find('status').text)
    if monitored == 0:
      return constants.MonitStates.UNMONITORED
    elif monitored == 1:
      if status == 0:
       return constants.MonitStates.RUNNING
      else:
        return constants.MonitStates.STOPPED
    else:
      return constants.MonitStates.PENDING

  return constants.MonitStates.MISSING


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

  @gen.coroutine
  def get_status(self, process_name):
    """ Retrieves the status of a given process.

    Args:
      process_name: A string specifying a monit watch.
    Returns:
      A string specifying the current status.
    """
    status_url = '{}/_status?format=xml'.format(self.LOCATION)
    response = yield self.client.fetch(status_url)
    raise gen.Return(process_status(response.body, process_name))

  @gen.coroutine
  def send_command(self, process_name, command):
    """ Sends a command to the Monit API.

    Args:
      process_name: A string specifying a monit watch.
      command: A string specifying the command to send.
    """
    process_url = '{}/{}'.format(self.LOCATION, process_name)
    payload = urllib.urlencode({'action': command})
    while True:
      try:
        yield self.client.fetch(process_url, method='POST', body=payload)
        return
      except HTTPError:
        yield gen.sleep(.2)

  @gen.coroutine
  def wait_for_status(self, process_name, acceptable_states):
    """ Waits until a process is in a desired state.

    Args:
      process_name: A string specifying a monit watch.
      acceptable_states: An iterable of strings specifying states.
    """
    while True:
      status = yield self.get_status(process_name)
      if status in acceptable_states:
        raise gen.Return(status)
      yield gen.sleep(.2)

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
        raise gen.Return()

      if status == constants.MonitStates.UNMONITORED:
        yield self.send_command(process_name, 'start')

      yield gen.sleep(1)

  @gen.coroutine
  def _reload(self):
    """ Reloads Monit. """
    time_since_reload = time.time() - self.last_reload
    wait_time = max(self.RELOAD_COOLDOWN - time_since_reload, 0)
    yield gen.sleep(wait_time)
    self.last_reload = time.time()
    subprocess.check_call(['monit', 'reload'])
