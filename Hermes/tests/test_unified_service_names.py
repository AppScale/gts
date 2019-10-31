from appscale.hermes.unified_service_names import (
  ServicesEnum, find_service_by_external_name, find_service_by_pxname, Service
)


class TestExternalNames:
  def test_search_for_known_service(self):
    external_name_to_expectation = {
      'appscale-admin.service': ServicesEnum.ADMIN,
      'appscale-uaserver.service': ServicesEnum.UASERVER,
      'appscale-taskqueue@17448.service': ServicesEnum.TASKQUEUE,
      'datastore_server-4002': ServicesEnum.DATASTORE,
      'appscale-blobstore.service': ServicesEnum.BLOBSTORE,
      'appscale-instance-run@superapp-20005.service': ServicesEnum.APPLICATION,
      'zookeeper.service': ServicesEnum.ZOOKEEPER,
      'rabbitmq-server.service': ServicesEnum.RABBITMQ,
      'nginx.service': ServicesEnum.NGINX,
      'appscale-logserver.service': ServicesEnum.LOG_SERVICE,
      'appscale-infrastructure@basic.service': ServicesEnum.IAAS_MANAGER,
      'appscale-infrastructure@shadow.service': ServicesEnum.IAAS_MANAGER,
      'appscale-haproxy@service.service': ServicesEnum.SERVICE_HAPROXY,
      'ejabberd.service': ServicesEnum.EJABBERD,
      'appscale-celery@snowmachineapp.service': ServicesEnum.CELERY,
      'appscale-instance-manager.service': ServicesEnum.APPMANAGER,
    }
    for external_name, expected in external_name_to_expectation.items():
      assert find_service_by_external_name(external_name) == expected

  def test_search_for_unknown_service(self):
    service = find_service_by_external_name('irrelevant-process')
    assert service.name == 'irrelevant-process'

  def test_parsing_application_id(self):
    # Celery service
    celery = ServicesEnum.CELERY
    app = celery.get_application_id_by_external_name('appscale-celery@app-ppa.service')
    assert app == 'app-ppa'
    # Application service
    application = ServicesEnum.APPLICATION
    app = application.get_application_id_by_external_name('appscale-instance-run@appppa-20008.service')
    assert app == 'appppa'

  def test_parsing_port(self):
    # Application service
    application = ServicesEnum.APPLICATION
    port = application.get_port_by_external_name('appscale-instance-run@appppa-20008.service')
    assert port == 20008
    # Taskqueue service
    taskqueue = ServicesEnum.TASKQUEUE
    port = taskqueue.get_port_by_external_name('appscale-taskqueue@17448.service')
    assert port == 17448
    # Datastore service
    datastore = ServicesEnum.DATASTORE
    port = datastore.get_port_by_external_name('datastore_server-4002')
    assert port == 4002


class TestHAProxyNames:
  def test_search_for_known_service(self):
    proxy_name_to_expectation = {
      'UserAppServer': ServicesEnum.UASERVER,
      'TaskQueue': ServicesEnum.TASKQUEUE,
      'appscale-datastore_server': ServicesEnum.DATASTORE,
      'as_blob_server': ServicesEnum.BLOBSTORE,
      'gae_app3-3': ServicesEnum.APPLICATION,
    }
    for proxy_name, expected in proxy_name_to_expectation.items():
      assert find_service_by_pxname(proxy_name) == expected

  def test_search_for_unknown_service(self):
    service = find_service_by_pxname('irrelevant-haproxy-proxy')
    assert service.name == 'irrelevant-haproxy-proxy'

  def test_parsing_application_id(self):
    app = ServicesEnum.APPLICATION.get_application_id_by_pxname('gae_app3-3')
    assert app == 'app3-3'

  def test_parsing_ip_port(self):
    # IP/Port for uaserver
    ip, port = ServicesEnum.UASERVER.get_ip_port_by_svname(
      'UserAppServer-10.10.8.9:4342')
    assert ip == '10.10.8.9'
    assert port == 4342

    # IP/Port for taskqueue
    ip, port = ServicesEnum.TASKQUEUE.get_ip_port_by_svname(
      'TaskQueue-10.10.8.9:17448')
    assert ip == '10.10.8.9'
    assert port == 17448

    # IP/Port for datastore
    ip, port = ServicesEnum.DATASTORE.get_ip_port_by_svname(
      'appscale-datastore_server-10.10.8.9:4002')
    assert ip == '10.10.8.9'
    assert port == 4002

    # IP/Port for blobstore
    ip, port = ServicesEnum.BLOBSTORE.get_ip_port_by_svname(
      'as_blob_server-10.10.8.9:6107')
    assert ip == '10.10.8.9'
    assert port == 6107

    # IP/Port for application
    ip, port = ServicesEnum.APPLICATION.get_ip_port_by_svname(
      'gae_app3-3-10.10.8.9:20008')
    assert ip == '10.10.8.9'
    assert port == 20008


class TestUnknownService:
  def test_unknown_service(self):
    service = Service(name='smth-out-of-stats-28')
    assert service.name == 'smth-out-of-stats-28'
    # Application ID by unknown external name
    app = service.get_application_id_by_external_name('smth-out-of-stats-28')
    assert app is None
    # Application ID by unknown haproxy name
    app = service.get_application_id_by_pxname('smth-out-of-stats-1.1.1.1:2')
    assert app is None
    # Port by unknown external name
    port = service.get_port_by_external_name('smth-out-of-stats-28')
    assert port is None
    # IP/Port by unknown haproxy
    ip, port = service.get_ip_port_by_svname('smth-out-of-stats-1.1.1.1:2')
    assert ip is None
    assert port is None
