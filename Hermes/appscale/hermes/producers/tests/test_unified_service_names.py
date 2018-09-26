import unittest

from appscale.hermes.stats.unified_service_names import (
  ServicesEnum, find_service_by_monit_name, find_service_by_pxname, Service
)


class TestMonitNames(unittest.TestCase):
  def test_search_for_known_service(self):
    monit_name_to_expectation = {
      'uaserver': ServicesEnum.UASERVER,
      'taskqueue-17448': ServicesEnum.TASKQUEUE,
      'datastore_server-4002': ServicesEnum.DATASTORE,
      'blobstore': ServicesEnum.BLOBSTORE,
      'app___superapp-20005': ServicesEnum.APPLICATION,
      'zookeeper': ServicesEnum.ZOOKEEPER,
      'rabbitmq': ServicesEnum.RABBITMQ,
      'nginx': ServicesEnum.NGINX,
      'log_service': ServicesEnum.LOG_SERVICE,
      'iaas_manager': ServicesEnum.IAAS_MANAGER,
      'hermes': ServicesEnum.HERMES,
      'haproxy': ServicesEnum.HAPROXY,
      'groomer_service': ServicesEnum.GROOMER,
      'flower': ServicesEnum.FLOWER,
      'ejabberd': ServicesEnum.EJABBERD,
      'controller': ServicesEnum.CONTROLLER,
      'celery-snowmachineapp-9999': ServicesEnum.CELERY,
      'cassandra': ServicesEnum.CASSANDRA,
      'backup_recovery_service': ServicesEnum.BACKUP_RECOVERY_SERVICE,
      'memcached': ServicesEnum.MEMCACHED,
      'appmanagerserver': ServicesEnum.APPMANAGER,
    }
    for monit_name, expected in monit_name_to_expectation.iteritems():
      self.assertEqual(find_service_by_monit_name(monit_name), expected)

  def test_search_for_unknown_service(self):
    service = find_service_by_monit_name('irrelevant-monit-process')
    self.assertEqual(service.name, 'irrelevant-monit-process')

  def test_parsing_application_id(self):
    # Celery service
    celery = ServicesEnum.CELERY
    app = celery.get_application_id_by_monit_name('celery-app-ppa-9999')
    self.assertEqual(app, 'app-ppa')
    # Application service
    application = ServicesEnum.APPLICATION
    app = application.get_application_id_by_monit_name('app___appppa-20008')
    self.assertEqual(app, 'appppa')

  def test_parsing_port(self):
    # Celery service
    celery = ServicesEnum.CELERY
    port = celery.get_port_by_monit_name('celery-app-ppa-9999')
    self.assertEqual(port, 9999)
    # Application service
    application = ServicesEnum.APPLICATION
    port = application.get_port_by_monit_name('app___appppa-20008')
    self.assertEqual(port, 20008)
    # Taskqueue service
    taskqueue = ServicesEnum.TASKQUEUE
    port = taskqueue.get_port_by_monit_name('taskqueue-17448')
    self.assertEqual(port, 17448)
    # Datastore service
    datastore = ServicesEnum.DATASTORE
    port = datastore.get_port_by_monit_name('datastore_server-4002')
    self.assertEqual(port, 4002)


class TestHAProxyNames(unittest.TestCase):
  def test_search_for_known_service(self):
    proxy_name_to_expectation = {
      'UserAppServer': ServicesEnum.UASERVER,
      'TaskQueue': ServicesEnum.TASKQUEUE,
      'appscale-datastore_server': ServicesEnum.DATASTORE,
      'as_blob_server': ServicesEnum.BLOBSTORE,
      'gae_app3-3': ServicesEnum.APPLICATION,
    }
    for proxy_name, expected in proxy_name_to_expectation.iteritems():
      self.assertEqual(find_service_by_pxname(proxy_name), expected)

  def test_search_for_unknown_service(self):
    service = find_service_by_pxname('irrelevant-haproxy-proxy')
    self.assertEqual(service.name, 'irrelevant-haproxy-proxy')

  def test_parsing_application_id(self):
    app = ServicesEnum.APPLICATION.get_application_id_by_pxname('gae_app3-3')
    self.assertEqual(app, 'app3-3')

  def test_parsing_ip_port(self):
    # IP/Port for uaserver
    ip, port = ServicesEnum.UASERVER.get_ip_port_by_svname(
      'UserAppServer-10.10.8.9:4342')
    self.assertEqual(ip, '10.10.8.9')
    self.assertEqual(port, 4342)

    # IP/Port for taskqueue
    ip, port = ServicesEnum.TASKQUEUE.get_ip_port_by_svname(
      'TaskQueue-10.10.8.9:17448')
    self.assertEqual(ip, '10.10.8.9')
    self.assertEqual(port, 17448)

    # IP/Port for datastore
    ip, port = ServicesEnum.DATASTORE.get_ip_port_by_svname(
      'appscale-datastore_server-10.10.8.9:4002')
    self.assertEqual(ip, '10.10.8.9')
    self.assertEqual(port, 4002)

    # IP/Port for blobstore
    ip, port = ServicesEnum.BLOBSTORE.get_ip_port_by_svname(
      'as_blob_server-10.10.8.9:6107')
    self.assertEqual(ip, '10.10.8.9')
    self.assertEqual(port, 6107)

    # IP/Port for application
    ip, port = ServicesEnum.APPLICATION.get_ip_port_by_svname(
      'gae_app3-3-10.10.8.9:20008')
    self.assertEqual(ip, '10.10.8.9')
    self.assertEqual(port, 20008)


class TestUnknownService(unittest.TestCase):
  def test_unknown_service(self):
    service = Service(name='smth-out-of-stats-28')
    self.assertEqual(service.name, 'smth-out-of-stats-28')
    # Application ID by unknown monit name
    app = service.get_application_id_by_monit_name('smth-out-of-stats-28')
    self.assertIsNone(app)
    # Application ID by unknown haproxy name
    app = service.get_application_id_by_pxname('smth-out-of-stats-1.1.1.1:2')
    self.assertIsNone(app)
    # Port by unknown monit name
    port = service.get_port_by_monit_name('smth-out-of-stats-28')
    self.assertIsNone(port)
    # IP/Port by unknown haproxy
    ip, port = service.get_ip_port_by_svname('smth-out-of-stats-1.1.1.1:2')
    self.assertIsNone(ip)
    self.assertIsNone(port)
