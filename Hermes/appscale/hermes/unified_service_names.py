import re

import attr

UNMATCHABLE = "$."


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class Service(object):
  """
  An instance of this class correspond to specific family of AppScale services.
  e.g.: taskqueue, datastore, application (user application), cassandra, ...

  It's able to recognize itself in monit name and haproxy proxy name.
  Patterns which are used for recognition should also match application id,
  port and ip when possible.

  It's aimed to centralize parsing of service names
  in monit output and haproxy stats.
  It helps to define monit and haproxy name formats in a compact way.
  """
  name = attr.ib()

  # monit_matcher have to contain 'app' and 'port' groups when possible
  monit_matcher = attr.ib(default=UNMATCHABLE, convert=re.compile)

  # haproxy_proxy_matcher have to contain 'app' group when possible
  haproxy_proxy_matcher = attr.ib(default=UNMATCHABLE, convert=re.compile)

  # haproxy_server_matcher have to contain 'app', 'ip' and 'port' groups when possible
  haproxy_server_matcher = attr.ib(default=UNMATCHABLE, convert=re.compile)

  def recognize_monit_process(self, monit_name):
    """ Checks whether monit process corresponds to this service.

    Args:
      monit_name: A string, name of process as it's shown in monit status.
    Returns:
      True if monit_name corresponds to this service, False otherwise.
    """
    return self.monit_matcher.match(monit_name) is not None

  def recognize_haproxy_proxy(self, proxy_name):
    """ Checks whether haproxy proxy corresponds to this service.

    Args:
      proxy_name: A string, name of proxy as it's shown in haproxy stats.
    Returns:
      True if proxy_name corresponds to this service, False otherwise.
    """
    return self.haproxy_proxy_matcher.match(proxy_name) is not None

  def get_application_id_by_monit_name(self, monit_name):
    """ Parses monit_name and returns application ID if it was found.

    Args:
      monit_name: A string, name of process as it's shown in monit status.
    Returns:
      A string representing App ID, or None if it wasn't found.
    """
    match = self.monit_matcher.match(monit_name)
    if not match:
      return None
    try:
      return match.group('app') if match else None
    except IndexError:
      return None

  def get_port_by_monit_name(self, monit_name):
    """ Parses monit_name and returns port if it was found.

    Args:
      monit_name: A string, name of process as it's shown in monit status.
    Returns:
      An integer representing port, or None if it wasn't found.
    """
    match = self.monit_matcher.match(monit_name)
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
  # Known by both (Monit and HAProxy)
  UASERVER = Service(
    name='uaserver', monit_matcher='^uaserver$',
    haproxy_proxy_matcher=r'^UserAppServer$',
    haproxy_server_matcher=r'^UserAppServer-(?P<ip>[\d.]+):(?P<port>\d+)$'
  )
  TASKQUEUE = Service(
    name='taskqueue',
    monit_matcher=r'^taskqueue-(?P<port>\d+)$',
    haproxy_proxy_matcher='^TaskQueue$',
    haproxy_server_matcher=r'^TaskQueue-(?P<ip>[\d.]+):(?P<port>\d+)$'
  )
  DATASTORE = Service(
    name='datastore', monit_matcher=r'^datastore_server-(?P<port>\d+)$',
    haproxy_proxy_matcher='^appscale-datastore_server$',
    haproxy_server_matcher=r'^appscale-datastore_server-(?P<ip>[\d.]+):(?P<port>\d+)$'
  )
  BLOBSTORE = Service(
    name='blobstore', monit_matcher='^blobstore$',
    haproxy_proxy_matcher='^as_blob_server$',
    haproxy_server_matcher=r'^as_blob_server-(?P<ip>[\d.]+):(?P<port>\d+)$'
  )
  APPLICATION = Service(
    name='application',
    monit_matcher=r'^app___(?P<app>[\w_-]+)-(?P<port>\d+)$',
    haproxy_proxy_matcher=r'^gae_(?P<app>[\w_-]+)$',
    haproxy_server_matcher=r'^gae_(?P<app>[\w_-]+)-(?P<ip>[\d.]+):(?P<port>\d+)$'
  )

  # Known only on Monit side
  ZOOKEEPER = Service(name='zookeeper', monit_matcher='^zookeeper$')
  RABBITMQ = Service(name='rabbitmq', monit_matcher='^rabbitmq$')
  NGINX = Service(name='nginx', monit_matcher='^nginx$')
  LOG_SERVICE = Service(name='log_service', monit_matcher='^log_service$')
  IAAS_MANAGER = Service(name='iaas_manager', monit_matcher='^iaas_manager$')
  HERMES = Service(name='hermes', monit_matcher='^hermes$')
  HAPROXY = Service(name='haproxy', monit_matcher='^haproxy$')
  GROOMER = Service(name='groomer', monit_matcher='^groomer_service$')
  FLOWER = Service(name='flower', monit_matcher='^flower$')
  EJABBERD = Service(name='ejabberd', monit_matcher='^ejabberd$')
  CONTROLLER = Service(name='controller', monit_matcher='^controller$')
  CELERY = Service(name='celery',
                   monit_matcher=r'^celery-(?P<app>[\w_-]+)-(?P<port>\d+)$')
  CASSANDRA = Service(name='cassandra', monit_matcher='^cassandra$')
  BACKUP_RECOVERY_SERVICE = Service(name='backup_recovery_service',
                                    monit_matcher='^backup_recovery_service$')
  MEMCACHED = Service(name='memcached', monit_matcher='^memcached$')
  APPMANAGER = Service(name='appmanager', monit_matcher='^appmanagerserver$')


KNOWN_SERVICES = [
  value for value in ServicesEnum.__dict__.itervalues()
  if isinstance(value, Service)
]
KNOWN_SERVICES_DICT = {
  service.name: service for service in KNOWN_SERVICES
}


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


def find_service_by_monit_name(monit_name):
  # Try to find service corresponding to the monit_name
  known_service = next((
    service for service in KNOWN_SERVICES
    if service.recognize_monit_process(monit_name)
  ), None)
  if known_service:
    return known_service
  # Return new default dummy service if the monit_name is not recognized
  return Service(name=monit_name)
