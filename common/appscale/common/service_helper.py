import importlib
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


def __systemctl_run(args):
  """ Runs the given systemctl command.

  Args:
    args: A list of strs, where each str is an argument for systemctl.
  Raises:
    subprocess.CalledProcessError if command returned status different from 0.
  """
  subprocess.check_call([SYSTEMCTL] + args)


def __systemctl_out(args):
  """ Runs the given systemctl command, returns output.

  Args:
    args: A list of strs, where each str is an argument for systemctl.
  Returns:
    The output from the systemctl command
  Raises:
    subprocess.CalledProcessError if command returned status different from 0.
  """
  return subprocess.check_output([SYSTEMCTL] + args)


def __safe_systemctl_run(args):
  """ Runs the given systemctl command, logging any error.

  Args:
    args: A list of strs, where each str is an argument for systemctl.
  """
  try:
    __systemctl_run(args)
  except subprocess.CalledProcessError as err:
    logger.error(err)


def start(name, background=False, enable=None, wants=None, properties=None):
  """ Start the given service.

  Args:
    name: A str representing the name of the service to start.
    background: True to start without blocking
    enable: True to enable, False to start only, None for default.
    wants: services required by this service
    properties: properties to set for the service
  """
  logger.info('Starting service {0}'.format(name))
  expanded_name = __expand_name(name)

  if wants:
    logger.info('Service {0} wants {1}'.format(name, ' '.join(wants)))
    wants_args = ['--runtime', 'add-wants', expanded_name]
    wants_args.extend([__expand_name(want) for want in wants])
    __safe_systemctl_run(wants_args)

  if properties:
    logger.info('Service {0} properties {1}'.format(
      name, ' '.join('='.join(item) for item in properties.items())))
    properties_args = ['--runtime', 'set-property', expanded_name]
    properties_args.extend(['='.join(item) for item in properties.items()])
    __safe_systemctl_run(properties_args)

  __safe_systemctl_run(__build_command('start',
                                       expanded_name,
                                       background=background,
                                       enable=enable))


def stop(name, background=False):
  """ Stop the given service(s).

  Args:
    name: A str representing the name of the service(s) to stop.
    background: True to start without blocking
  """
  logger.info('Stopping service(s) {0}'.format(name))
  __safe_systemctl_run(__build_command('stop',
                                       __name_match(name),
                                       background=background))


def restart(name, background=False, start=True):
  """ Restart the given service(s).

  Args:
    name: A str representing the name of the service(s) to restart.
    background: True to start without blocking
    start: True to start services if not already running (use False with name pattern)
  """
  logger.info('Restarting service(s) {0}'.format(name))
  command = 'try-restart'
  if start:
    command = 'restart'
  __safe_systemctl_run(__build_command(command,
                                       __name_match(name),
                                       background=background))


def reload(name, background=False, start=True):
    """ Reload the given service(s).

    Args:
      name: A str representing the name of the service(s) to reload.
      background: True to start without blocking
      start: True to start services if not already running (use False with name pattern)
    """
    logger.info('Reloading service(s) {0}'.format(name))
    command = 'try-reload-or-restart'
    if start:
        command = 'reload-or-restart'
    __safe_systemctl_run(__build_command(command,
                                         __name_match(name),
                                         background=background))


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
    output = __systemctl_out(args)
    for output_line in output.split('\n'):
      if not output_line:
        continue
      service, loaded, active, remain = output_line.split(None, 3)
      if not service.endswith('.service'):
        continue
      services[service[:-8]] = STATUS_MAP.get(active, 'stopped')
    return services
  except subprocess.CalledProcessError:
    return {}


def __expand_name(name):
  """ Expand the given name by appending .service if there is no type suffix.

  Args:
    name: The unit name
  Returns:
    The name with type suffix
  """
  expanded_name = name
  if not '.' in name:
    expanded_name = '{0}.service'.format(name)
  return expanded_name


def __build_command(command, name, background=None, enable=None):
  """ Constuct args for systemctl command.

  Args:
    command: The systemctl command
    name: The unit name or name pattern
    background: True to have systemctl perform the command in the background
    enable: True to enable/disable, False to start/stop only, None for default.
  Returns:
    The name with type suffix
  """
  args = ['--quiet']
  if background:
    args.append('--no-block')
  if ((enable or name.startswith('appscale-'))
          and not enable==False
          and command in ('start', 'stop')):
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

  Args:
    name: A unit name without type suffix
  Returns:
    The name, possibly modified for matching
  """
  service_name_match = name
  if name.endswith('@'):
    service_name_match = '{0}*'.format(name)
  return service_name_match


class ServiceOperator(object):
  """ Handles Service operations. """

  def __init__(self,  thread_pool):
    """ Creates a new ServiceOperator.

    Args:
      thread_pool: A ThreadPoolExecutor.
    """
    self.thread_pool = thread_pool
    self.helper = importlib.import_module(self.__module__)

  @gen.coroutine
  def list_async(self):
    """ Retrieves the status for each service.

    Returns:
      A dictionary mapping services to their state.
    """
    listing = yield self.thread_pool.submit(self.list)
    raise gen.Return(listing)

  def list(self):
    """ Retrieves the status for each service.

    Returns:
      A dictionary mapping services to their state.
    """
    return self.helper.list()

  @gen.coroutine
  def start_async(self, name, enable=None, wants=None, properties=None):
    """ Start the given service asynchronously.

    Args:
      name: A str representing the name of the service to start.
      enable: True to enable, False to start only, None for default.
      wants: services required by this service
      properties: properties to set for the service
    """
    yield self.thread_pool.submit(self.start, name, enable=enable,
                                  wants=wants, properties=properties)

  def start(self, name, enable=None, wants=None, properties=None):
    """ Start the given service.

    Args:
      name: A str representing the name of the service to start.
      enable: True to enable, False to start only, None for default.
      wants: services required by this service
      properties: properties to set for the service
    """
    self.helper.start(name, enable=enable, wants=wants, properties=properties)

  @gen.coroutine
  def stop_async(self, name):
    """ Stop the given service(s) asynchronously.

    Args:
      name: A str representing the name of the service(s) to stop.
    """
    yield self.thread_pool.submit(self.stop, name)

  def stop(self, name):
    """ Stop the given service(s).

    Args:
      name: A str representing the name of the service(s) to stop.
    """
    self.helper.stop(name)

  @gen.coroutine
  def restart_async(self, name):
    """ Restart the given service(s) asynchronously.

    Args:
      name: A str representing the name of the service(s) to restart.
    """
    yield self.thread_pool.submit(self.restart, name)

  def restart(self, name):
    """ Restart the given service(s).

    Args:
      name: A str representing the name of the service(s) to restart.
    """
    self.helper.restart(name)