""" Stops an AppServer instance. """
import argparse
import errno
import os
import psutil
import signal

from appscale.common.constants import VAR_DIR

# The number of seconds to wait for an instance to terminate.
DEFAULT_WAIT_TIME = 20


def stop_instance(watch, timeout, force=False):
  """ Stops an AppServer process.

  Args:
    watch: A string specifying the Monit watch entry.
    timeout: An integer specifying the time to wait for requests to finish.
    force: A boolean indicating that the instance should be killed immediately
      instead of being allowed to finish ongoing requests.
  Raises:
    IOError if the pidfile does not exist.
    OSError if the process does not exist.
  """
  pidfile_location = os.path.join(VAR_DIR, '{}.pid'.format(watch))
  with open(pidfile_location) as pidfile:
    pid = int(pidfile.read().strip())

  group = os.getpgid(pid)
  if force:
    os.killpg(group, signal.SIGKILL)
    os.remove(pidfile_location)
    return

  process = psutil.Process(pid)
  process.terminate()
  try:
    process.wait(timeout)
  except psutil.TimeoutExpired:
    process.kill()

  try:
    os.killpg(group, signal.SIGKILL)
  except OSError:
    # In most cases, the group will already be gone.
    pass

  try:
    os.remove(pidfile_location)
  except OSError as e:
    # In case the pidfile has already been removed.
    if e.errno == errno.ENOENT:
      pass
    else:
      raise


def main():
  """ Stops an AppServer instance. """
  parser = argparse.ArgumentParser(description='Stops an AppServer instance')
  parser.add_argument('--watch', required=True, help='The Monit watch entry')
  parser.add_argument('--timeout', default=20,
                      help='The seconds to wait before killing the instance')
  parser.add_argument('--force', action='store_true',
                      help='Stop the process immediately')
  args = parser.parse_args()
  stop_instance(args.watch, args.timeout, args.force)
