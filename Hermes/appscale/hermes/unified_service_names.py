import re

import attr

UNMATCHABLE = "$."


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class Service(object):
  """
  An instance of this class correspond to specific family of AppScale services.
  e.g.: taskqueue, datastore, application (user application), cassandra, ...

  It's able to recognize itself in external name and haproxy proxy name.
  Patterns which are used for recognition should also match application id,
  port and ip when possible.

  It's aimed to centralize parsing of service names
  in systemctl show output and haproxy stats.
  It helps to define name formats in a compact way.
  """
  name = attr.ib()

  # name_matcher have to contain 'app' and 'port' groups when possible
  name_matcher = attr.ib(default=UNMATCHABLE, converter=re.compile)

  # haproxy_proxy_matcher have to contain 'app' group when possible
  haproxy_proxy_matcher = attr.ib(default=UNMATCHABLE, converter=re.compile)

  # haproxy_server_matcher have to contain 'app', 'ip' and 'port' groups when possible
  haproxy_server_matcher = attr.ib(default=UNMATCHABLE, converter=re.compile)

  def recognize_external_name(self, external_name):
    """ Checks whether the name corresponds to this service.

    Args:
      external_name: A string, name from external namespace.
    Returns:
      True if external_name corresponds to this service, False otherwise.
    """
    return self.name_matcher.match(external_name) is not None

  def recognize_haproxy_proxy(self, proxy_name):
    """ Checks whether haproxy proxy corresponds to this service.

    Args:
      proxy_name: A string, name of proxy as it's shown in haproxy stats.
    Returns:
      True if proxy_name corresponds to this service, False otherwise.
    """
    return self.haproxy_proxy_matcher.match(proxy_name) is not None

  def get_application_id_by_external_name(self, external_name):
    """ Parses external_name and returns application ID if it was found.

    Args:
      external_name: A string, name of external service/process.
    Returns:
      A string representing App ID, or None if it wasn't found.
    """
    match = self.name_matcher.match(external_name)
    if not match:
      return None
    try:
      return match.group('app') if match else None
    except IndexError:
      return None

  def get_port_by_external_name(self, external_name):
    """ Parses external_name and returns port if it was found.

    Args:
      external_name: A string, name of external service/process.
    Returns:
      An integer representing port, or None if it wasn't found.
    """
    match = self.name_matcher.match(external_name)
    try:
      port_group = match.group('port') if match else None
      return int(port_group) if port_group else None
    except IndexError:
      return None

  def get_application_id_by_pxname(self, pxname):
    """ Parses haproxy proxy and returns application ID if it was found.

    Args:
      pxname: A string, name of proxy as it's shown in haproxy stats.
    Returns:
      A string representing App ID, or None if it wasn't found.
    """
    match = self.haproxy_proxy_matcher.match(pxname)
    if not match:
      return None
    try:
      return match.group('app') if match else None
    except IndexError:
      return None

  def get_ip_port_by_svname(self, svname):
    """ Parses haproxy proxy and returns private IP and port if it was found.

    Args:
      svname: A string, name of server as it's shown in haproxy stats.
    Returns:
      A tuple (str:ip, int:port), None is used if IP or port wasn't found.
    """
    match = self.haproxy_server_matcher.match(svname)
    if not match:
      return None, None
    try:
      ip = match.group('ip')
    except IndexError:
      ip = None
    try:
      port_group = match.group('port')
      port = int(port_group) if port_group else None
    except IndexError:
      port = None
    return ip, port


class ServicesEnum(object):
  # Known by both (Systemd and HAProxy)
  UASERVER = Service(
    name='uaserver', name_matcher='^appscale-uaserver.service$',
    haproxy_proxy_matcher=r'^UserAppServer$',
    haproxy_server_matcher=r'^UserAppServer-(?P<ip>[\d.]+):(?P<port>\d+)$'
  )
  TASKQUEUE = Service(
    name='taskqueue',
    name_matcher=r'^appscale-taskqueue@(?P<port>\d+).service$',
    haproxy_proxy_matcher='^TaskQueue$',
    haproxy_server_matcher=r'^TaskQueue-(?P<ip>[\d.]+):(?P<port>\d+)$'
  )
  DATASTORE = Service(
    name='datastore', name_matcher=r'^datastore_server-(?P<port>\d+)$',
    haproxy_proxy_matcher='^appscale-datastore_server$',
    haproxy_server_matcher=r'^appscale-datastore_server-(?P<ip>[\d.]+):(?P<port>\d+)$'
  )
  BLOBSTORE = Service(
    name='blobstore', name_matcher='^appscale-blobstore.service$',
    haproxy_proxy_matcher='^as_blob_server$',
    haproxy_server_matcher=r'^as_blob_server-(?P<ip>[\d.]+):(?P<port>\d+)$'
  )
  APPLICATION = Service(
    name='application',
    name_matcher=r'^appscale-instance-run@(?P<app>[\w_-]+)-(?P<port>\d+).service$',
    haproxy_proxy_matcher=r'^gae_(?P<app>[\w_-]+)$',
    haproxy_server_matcher=r'^gae_(?P<app>[\w_-]+)-(?P<ip>[\d.]+):(?P<port>\d+)$'
  )

  # Known only on systemd side, defaults are added for each
  # appscale-XXX.service if no mapping is present
  ZOOKEEPER = Service(name='zookeeper', name_matcher='^zookeeper.service$')
  RABBITMQ = Service(name='rabbitmq', name_matcher='^rabbitmq-server.service$')
  NGINX = Service(name='nginx', name_matcher='^nginx.service$')
  LOG_SERVICE = Service(name='log_service', name_matcher='^appscale-logserver.service$')
  IAAS_MANAGER = Service(name='iaas_manager', name_matcher='^appscale-infrastructure@(basic|shadow).service$')
  EJABBERD = Service(name='ejabberd', name_matcher='^ejabberd.service$')
  ADMIN = Service(name='admin_server', name_matcher='^appscale-admin.service$')
  CELERY = Service(name='celery',
                   name_matcher=r'^appscale-celery@(?P<app>[\w_-]+).service$')
  CRON = Service(name='crond',
                 name_matcher=r'^cron.service$')
  APPMANAGER = Service(name='appmanager', name_matcher='^appscale-instance-manager.service$')
  SERVICE_HAPROXY = Service(name='service_haproxy', name_matcher='^appscale-haproxy@service.service$')


KNOWN_SERVICES = [
  value for value in ServicesEnum.__dict__.values()
  if isinstance(value, Service)
]
KNOWN_SERVICES_DICT = {
  service.name: service for service in KNOWN_SERVICES
}


def systemd_mapper(external_name):
  """ Map a systemd service name to a Hermes name.

  This will ignore instance of templated services which would require
  special handling for any instance parameters (e.g. port)

  This mapping can be used with `find_service_by_external_name`
  """
  if (external_name.startswith('appscale-') and
      external_name.endswith('.service') and
      not '@' in external_name):
    return external_name[9:-8].replace('-','_')
  return None

def find_service_by_pxname(proxy_name):
  # Try to find service corresponding to the proxy_name
  known_service = next((
    service for service in KNOWN_SERVICES
    if service.recognize_haproxy_proxy(proxy_name)
  ), None)
  if known_service:
    return known_service
  # Return new default dummy service if the proxy_name is not recognized
  return Service(name=proxy_name)


def find_service_by_external_name(external_name, default_mapper=str):
  # Try to find service corresponding to the external_name
  known_service = next((
    service for service in KNOWN_SERVICES
    if service.recognize_external_name(external_name)
  ), None)
  if known_service:
    return known_service
  # Return new default dummy service if the external_name is not recognized
  mapped_name = default_mapper(external_name)
  if mapped_name is None:
    return None
  return Service(name=mapped_name)
