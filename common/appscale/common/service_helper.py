import logging
import subprocess

from tornado import gen

"""
This file contains top level functions for starting and stopping
services using systemctl. Service names can be prefixes for template
services or else are the unit names but without the type suffix.
"""


SYSTEMCTL = '/bin/systemctl'


STATUS_MAP = {
  'active': 'running',
  'activating': 'pending',
  'deactivating' : 'pending',
  'reloading': 'running',
}

logger = logging.getLogger(__name__)

# TODO:STEVE: more docstrings

class NonZeroReturnStatus(Exception):
  """ Indicates that command returned non-zero return status """
  pass


def systemctl_run(args):
  """ Runs the given systemctl command.

  Args:
    args: A list of strs, where each str is an argument for systemctl.
  Raises:
    NonZeroReturnStatus if command returned status different from 0.
  """
  return_status = subprocess.call([SYSTEMCTL] + args)
  if return_status != 0:
    raise NonZeroReturnStatus('Command {0} return non-zero status: {1}'
                              .format(' '.join(args), return_status))


def systemctl_out(args):
  """ Runs the given systemctl command, returns output.

  Args:
    args: A list of strs, where each str is an argument for systemctl.
  Returns:
    The output from the systemctl command
  Raises:
    NonZeroReturnStatus if command returned status different from 0.
  """
  try:
    return subprocess.check_output([SYSTEMCTL] + args)
  except subprocess.CalledProcessError as err:
    raise NonZeroReturnStatus('Command {0} return non-zero status: {1}'
                              .format(' '.join(args), err.returncode))

def safe_systemctl_run(args):
  """ Runs the given systemctl command, logging any error.

  Args:
    args: A list of strs, where each str is an argument for systemctl.
  Returns:
    True if command succeeded, False otherwise.
  """
  try:
    systemctl_run(args)
    return True
  except NonZeroReturnStatus as err:
    logger.error(err)
    return False


def start(name, background=False, wants=None):
  """ Start the given service.

  Args:
    name: A str representing the name of the service to start.
    background: True to start without blocking
    wants: services required by this service
  Returns:
    True if the service was started, else False.
  """
  logger.info('Starting service {0}'.format(name))
  expanded_name = __expand_name(name)
  if wants:
    logger.info('Service {0} wants {1}'.format(name, ', '.join(wants)))
    wants_args = ['--runtime', 'add-wants', expanded_name]
    wants_args.extend([__expand_name(want) for want in wants])
    safe_systemctl_run(wants_args)

  return safe_systemctl_run(__build_command('start',
                                            background,
                                            expanded_name))


def stop(name, background=False):
  """ Stop the given service(s).

  Args:
    name: A str representing the name of the service(s) to stop.
    background: True to start without blocking
  Returns:
    True if the named services were stopped.
  """
  logger.info('Stopping service(s) {0}'.format(name))
  return safe_systemctl_run(__build_command('stop',
                                            background,
                                            __name_match(name)))


def restart(name, background=False, start=True):
  """ Restart the given service(s).

  Args:
    name: A str representing the name of the service(s) to restart.
    background: True to start without blocking
    start: True to start services if not already running (use False with name pattern)
  Returns:
    True if services were restarted.
  """
  logger.info('Restarting service(s) {0}'.format(name))
  command = 'try-restart'
  if start:
    command = 'restart'
  return safe_systemctl_run(__build_command(command,
                                            background,
                                            __name_match(name)))


def list(running=False):
  """ List appscale service(s).

  Args:
    running: True to only report active services
  Returns:
    Dict of services and their status (pending|running|stopped)
  """
  args = ['--plain', '--no-pager', '--no-legend']
  if running:
    args.append('--state=active')
  args.extend(['list-units', 'appscale-*.service'])

  try:
    services = {}
    output = systemctl_out(args)
    for output_line in output.split('\n'):
      if not output_line:
        continue
      service, loaded, active, remain = output_line.split(None, 3)
      if not service.endswith('.service'):
        continue
      services[service[:-8]] = STATUS_MAP.get(active, 'stopped')
    return services
  except NonZeroReturnStatus:
    return {}


def __expand_name(name):
  expanded_name = name
  if not '.' in name:
    expanded_name = '{0}.service'.format(name)
  return expanded_name


def __build_command(command, background, name):
  args = ['--quiet']
  if background:
    args.append('--no-block')
  if name.startswith('appscale-') and command in ('start', 'stop'):
    args.append('--now')
    args.append('--runtime')
    if command == 'start':
      args.append('enable')
    else:
      args.append('disable')
  else:
    args.append(command)
  args.append(__expand_name(name))
  return args


def __name_match(name):
  """ Convert a template name to a pattern matching all instances of the
      service.
  """
  service_name_match = name
  if name.endswith('@'):
    service_name_match = '{0}*'.format(name)
  return service_name_match


class ServiceOperator(object):
  """ Handles Service operations. """

  @gen.coroutine
  def list_async(self):
    """ Retrieves the status for each service.

    Returns:
      A dictionary mapping services to their state.
    """
    raise gen.Return(self.list())

  def list(self):
    """ Retrieves the status for each service.

    Returns:
      A dictionary mapping services to their state.
    """
    return list()

  @gen.coroutine
  def start_async(self, name, wants=None):
    raise gen.Return(self.start(name, wants=wants))

  def start(self, name, wants=None):
    return start(name, wants=wants)

  @gen.coroutine
  def stop_async(self, name):
    raise gen.Return(self.stop(name))

  def stop(self, name):
    return stop(name)

  @gen.coroutine
  def restart_async(self, name):
    raise gen.Return(self.restart(name))

  def restart(self, name):
    return restart(name)