import os
import sys

from appscale.common import appscale_info
from distutils.spawn import find_executable
from . import file_io
from .constants import VERSION_PATH_SEPARATOR

# Directory with the task templates.
TEMPLATE_DIR = os.path.join(
  os.path.dirname(sys.modules['appscale.common'].__file__), 'templates')

# Template used for monit configuration files.
TEMPLATE_LOCATION = os.path.join(TEMPLATE_DIR, 'monit_template.conf')

# The directory used when storing a service's config file.
MONIT_CONFIG_DIR = '/etc/monit/conf.d'


def create_config_file(watch, start_cmd, pidfile, port=None, env_vars=None,
                       max_memory=None, syslog_server=None, check_port=False,
                       check_host=None, kill_exceeded_memory=False,
                       log_tag=None, group=None):
  """ Writes a monit configuration file for a service.

  Args:
    watch: A string which identifies this process with monit.
    start_cmd: The start command to start the process.
    pidfile: The location of the pidfile that the process creates.
    port: An integer specifying the port for the process.
    env_vars: A dictionary specifying environment variables.
    max_memory: An integer that specifies the maximum amount of memory in
      megabytes that the process should use.
    syslog_server: The IP address of the remote syslog server to use.
    check_port: A boolean specifying that monit should check host and port.
    check_host: Optional host to use with check_port, defaults to private ip
    kill_exceeded_memory: A boolean indicating that a process should be killed
      (instead of terminated). This is used when the process exceeds its memory
      limit.
    log_tag: The tag to use with logging. Default is to derive from watch.
    group: The monit group for the process, defaults to group derived from
      version.
  """
  if check_port:
    assert port is not None, 'When using check_port, port must be defined'

  process_name = watch
  watch_group = watch.rsplit(VERSION_PATH_SEPARATOR, 1)[0]
  version_group = group if group is not None else watch_group
  if port is not None:
    process_name += '-{}'.format(port)

  env_vars_str = ''
  if env_vars is not None:
    for key in env_vars:
      env_vars_str += '{}="{}" '.format(key, env_vars[key])

  bash = find_executable('bash')
  start_stop_daemon = find_executable('start-stop-daemon')
  stop_instance = find_executable('appscale-stop-instance')

  # /usr/local/bin is not on the path in Trusty.
  stop_instance_script = os.path.join('/', 'usr', 'local', 'bin',
                                      'appscale-stop-instance')
  if stop_instance is None and os.path.isfile(stop_instance_script):
    stop_instance = stop_instance_script

  assert stop_instance is not None, 'Unable to find appscale-stop-instance'

  logfile = os.path.join(
    '/', 'var', 'log', 'appscale', '{}.log'.format(process_name))

  if not log_tag:
    log_tag = version_group

  if syslog_server is None:
    bash_exec = 'exec env {vars} {start_cmd} >> {log} 2>&1'.format(
      vars=env_vars_str, start_cmd=start_cmd, log=logfile)
  else:
    bash_exec = (
      'exec env {vars} {start_cmd} 2>&1 | tee -a {log} | '
      'logger -t {log_tag} -u /tmp/ignored -n {syslog_server} -P 514'
    ).format(vars=env_vars_str, start_cmd=start_cmd, log=logfile,
             log_tag=log_tag, syslog_server=syslog_server)

  start_line = ' '.join([
    start_stop_daemon,
    '--start',
    '--background',
    '--pidfile', pidfile,
    '--startas', "{} -- -c 'unset \"${{!MONIT_@}}\"; {}'".format(bash, bash_exec)
  ])
  stop_line = '{} --watch {}'.format(stop_instance, process_name)

  with open(TEMPLATE_LOCATION) as template:
    output = template.read()
    output = output.format(
      process_name=process_name, match_clause='PIDFILE "{}"'.format(pidfile),
      group=version_group, start_line=start_line, stop_line=stop_line)

  if max_memory is not None:
    if kill_exceeded_memory:
      action = 'exec "{} --watch {} --force"'.format(stop_instance, process_name)
    else:
      action = 'restart'

    output += '  if totalmem > {} MB for 10 cycles then {}\n'.format(
      max_memory, action)

  if check_port:
    check_host = check_host or appscale_info.get_private_ip()
    output += '  if failed host {} port {} for 3 cycles then restart\n'.format(
        check_host, port)

  config_file = os.path.join(MONIT_CONFIG_DIR,
                             'appscale-{}.cfg'.format(process_name))
  file_io.write(config_file, output)

  return


def create_daemon_config(watch, start_cmd, stop_cmd, pidfile, max_memory=None):
  """ Writes a monit configuration file for a daemonized service.

  Args:
    watch: A string which identifies this process with monit.
    start_cmd: A string specifying the command to start the service.
    stop_cmd: A string specifying the command to stop the service.
    pidfile: A string specifying the location of the service's pidfile.
    max_memory: An integer that specifies the maximum amount of memory in
      megabytes that the process should use.
  """
  with open(TEMPLATE_LOCATION) as template:
    output = template.read()
    output = output.format(
      process_name=watch, match_clause='PIDFILE "{}"'.format(pidfile),
      group=watch, start_line=start_cmd, stop_line=stop_cmd)

  if max_memory is not None:
    output += '  if totalmem > {} MB for 10 cycles then restart\n'.format(
      max_memory)

  config_file = os.path.join(MONIT_CONFIG_DIR, 'appscale-{}.cfg'.format(watch))
  file_io.write(config_file, output)


def create_custom_config(watch, start_cmd, stop_cmd, match_cmd):
  """ Writes a monit configuration for a service without a pidfile.

  Args:
    watch: A string which identifies this process with monit.
    start_cmd: A string specifying the command to start the service.
    stop_cmd: A string specifying the command to stop the service.
    match_cmd: The string monit should use to check if the process is running.
  """
  with open(TEMPLATE_LOCATION) as template:
    output = template.read()
    output = output.format(
      process_name=watch, match_clause='MATCHING {}'.format(match_cmd),
      group=watch, start_line=start_cmd, stop_line=stop_cmd)

  config_file = os.path.join(MONIT_CONFIG_DIR, 'appscale-{}.cfg'.format(watch))
  file_io.write(config_file, output)
