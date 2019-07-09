# Programmer: Navraj Chohan <nlake44@gmail.com>

import os
import subprocess
import time
import unittest
import urllib2

from flexmock import flexmock
from tornado import gen
from tornado.gen import Future
from tornado.httpclient import HTTPError
from tornado.options import options
from tornado.testing import AsyncTestCase
from tornado.testing import gen_test

from appscale.admin.instance_manager.constants import START_APP_TIMEOUT
from appscale.admin.instance_manager import (
  instance_manager as instance_manager_module)
from appscale.admin.instance_manager import InstanceManager
from appscale.admin.instance_manager import instance
from appscale.admin.instance_manager import utils
from appscale.common import (
  file_io,
  appscale_info,
  misc,
  monit_interface,
  testing
)
from appscale.common import monit_app_configuration
from appscale.common.monit_interface import MonitOperator

options.define('login_ip', '127.0.0.1')
options.define('syslog_server', '127.0.0.1')
if not hasattr(options, 'private_ip'):
  options.define('private_ip', '<private_ip>')

options.define('db_proxy', '<private_ip>')
options.define('load_balancer_ip', '<private_ip>')
options.define('tq_proxy', '<private_ip>')


class TestInstanceManager(AsyncTestCase):
  @gen_test
  def test_start_app_goodconfig_python(self):
    testing.disable_logging()

    version_details = {'runtime': 'python27',
                       'revision': 1,
                       'deployment': {'zip': {'sourceUrl': 'source.tar.gz'}},
                       'appscaleExtensions': {'httpPort': '8080'}}
    version_manager = flexmock(version_details=version_details,
                               project_id='test',
                               revision_key='test_default_v1_1',
                               version_key='test_default_v1')
    projects_manager = {
      'test': {'default': {'v1': version_manager}}}
    deployment_config = flexmock(
      get_config=lambda x: {'default_max_appserver_memory': 400})

    source_manager = flexmock()
    response = Future()
    response.set_result(None)
    source_manager.should_receive('ensure_source').\
      with_args('test_default_v1_1', 'source.tar.gz', 'python27').\
      and_return(response)

    instance_manager = InstanceManager(
      None, None, None, projects_manager, deployment_config,
      source_manager, None, None, None)
    instance_manager._login_server = '192.168.33.10'

    flexmock(monit_app_configuration).should_receive('create_config_file').\
      and_return('fakeconfig')

    response = Future()
    response.set_result(None)
    flexmock(instance_manager).should_receive('_ensure_api_server').\
      and_return(response)

    response = Future()
    response.set_result(None)
    flexmock(MonitOperator).should_receive('reload').\
      and_return(response)

    response = Future()
    response.set_result(None)
    flexmock(MonitOperator).should_receive('send_command_retry_process').\
      with_args('app___test_default_v1_1-20000', 'start').\
      and_return(response)

    response = Future()
    response.set_result(None)
    flexmock(instance_manager).should_receive('_add_routing').\
      and_return(response)

    flexmock(instance_manager).should_receive('_wait_for_app').\
      and_return(True)
    flexmock(os).should_receive('popen').\
      and_return(flexmock(read=lambda: '12345\n'))
    flexmock(file_io).should_receive('write').\
      and_return()
    flexmock(utils).should_receive("setup_logrotate").and_return()

    instance_manager._zk_client = flexmock()
    instance_manager._zk_client.should_receive('ensure_path')

    instance_manager._monit_operator = flexmock(
      reload=lambda x: response,
      send_command_retry_process=lambda watch, cmd: response)

    yield instance_manager._start_instance(version_manager, 20000)

  @gen_test
  def test_start_app_goodconfig_java(self):
    testing.disable_logging()

    version_details = {'runtime': 'java',
                       'revision': 1,
                       'deployment': {'zip': {'sourceUrl': 'source.tar.gz'}},
                       'appscaleExtensions': {'httpPort': '8080'}}
    version_manager = flexmock(version_details=version_details,
                               project_id='test',
                               revision_key='test_default_v1_1',
                               version_key='test_default_v1')

    instance_manager = InstanceManager(
      None, None, None, None, None, None, None, None, None)
    instance_manager._projects_manager = {
      'test': {'default': {'v1': version_manager}}}
    instance_manager._deployment_config = flexmock(
      get_config=lambda x: {'default_max_appserver_memory': 400})

    source_manager = flexmock()
    response = Future()
    response.set_result(None)
    source_manager.should_receive('ensure_source').\
      with_args('test_default_v1_1', 'source.tar.gz', 'java').\
      and_return(response)
    instance_manager._source_manager = source_manager

    start_cmd = ('/root/appscale/AppServer_Java/appengine-java-repacked/bin/'
                 'dev_appserver.sh --port 20000')
    flexmock(instance).should_receive('create_java_start_cmd').\
      and_return(start_cmd)

    flexmock(monit_app_configuration).should_receive('create_config_file').\
      and_return('fakeconfig')

    response = Future()
    response.set_result(None)
    flexmock(instance_manager).should_receive('_ensure_api_server').\
        and_return(response)

    response = Future()
    response.set_result(None)
    flexmock(MonitOperator).should_receive('reload').\
        and_return(response)

    response = Future()
    response.set_result(None)
    flexmock(MonitOperator).should_receive('send_command_retry_process').\
      with_args('app___test_default_v1_1-20000', 'start').\
      and_return(response)

    response = Future()
    response.set_result(None)
    flexmock(instance_manager).should_receive('_add_routing').\
      and_return(response)

    flexmock(instance).should_receive('create_java_app_env').\
      and_return({})
    flexmock(instance_manager_module).should_receive('create_java_start_cmd').\
      and_return('/root/appscale/AppServer_Java/appengine-java-repacked/bin/'
                 'dev_appserver.sh --port 20000')
    flexmock(instance_manager).should_receive('_wait_for_app').\
      and_return(True)
    flexmock(os).should_receive('popen').\
      and_return(flexmock(read=lambda: '0\n'))
    flexmock(file_io).should_receive('write').and_return()
    flexmock(subprocess).should_receive('call').and_return(0)
    flexmock(utils).should_receive("setup_logrotate").and_return()
    flexmock(os).should_receive('listdir').and_return([])

    instance_manager._zk_client = flexmock()
    instance_manager._zk_client.should_receive('ensure_path')

    response = Future()
    response.set_result(None)
    instance_manager._monit_operator = flexmock(
      reload=lambda x: response,
      send_command_retry_process=lambda watch, cmd: response)

    yield instance_manager._start_instance(version_manager, 20000)

  @gen_test
  def test_start_app_failed_copy_java(self):
    version_details = {'runtime': 'java',
                       'revision': 1,
                       'deployment': {'zip': {'sourceUrl': 'source.tar.gz'}},
                       'appscaleExtensions': {'httpPort': '8080'}}
    version_manager = flexmock(version_details=version_details,
                               project_id='test',
                               revision_key='test_default_v1_1',
                               version_key='test_default_v1')

    instance_manager = InstanceManager(
      None, None, None, None, None, None, None, None, None)
    instance_manager._projects_manager = {
      'test': {'default': {'v1': version_manager}}}
    instance_manager._deployment_config = flexmock(
      get_config=lambda x: {'default_max_appserver_memory': 400})

    source_manager = flexmock()
    response = Future()
    response.set_result(None)
    source_manager.should_receive('ensure_source').\
      with_args('test_default_v1_1', 'source.tar.gz', 'java').\
      and_return(response)
    instance_manager._source_manager = source_manager

    flexmock(utils).should_receive('find_web_inf').\
      and_return('/path/to/dir/WEB-INF')
    flexmock(monit_app_configuration).should_receive('create_config_file').\
      and_raise(IOError)

    with self.assertRaises(IOError):
      yield instance_manager._start_instance(version_manager, 20000)

  def test_create_python_app_env(self):
    env_vars = instance.create_python_app_env('1', '2')
    self.assertEqual('1', env_vars['MY_IP_ADDRESS'])
    self.assertEqual('2', env_vars['APPNAME'])
    assert 'appscale' in env_vars['APPSCALE_HOME']
    assert 0 < int(env_vars['GOMAXPROCS'])

  def test_create_java_app_env(self):
    deployment_config = flexmock(get_config=lambda x: {})
    env_vars = instance.create_java_app_env(deployment_config, 'java',
                                            'guestbook')
    assert 'appscale' in env_vars['APPSCALE_HOME']

  def test_create_java_start_cmd(self):
    flexmock(instance).should_receive('find_web_inf').\
      and_return('/path/to/dir/WEB-INF')
    app_id = 'testapp'
    revision_key = 'testapp_default_v1'
    max_heap = 260
    pidfile = 'testpid'
    cmd = instance.create_java_start_cmd(
      app_id, '20000', '8080', '127.0.0.2', max_heap, pidfile, revision_key,
      19999, 'java')
    assert app_id in cmd

  @gen_test
  def test_stop_app_instance(self):
    version_key = 'test_default_v1'
    port = 20000
    flexmock(misc).should_receive('is_app_name_valid').and_return(False)

    instance_manager = InstanceManager(
      None, None, None, None, None, None, None, None, None)

    flexmock(misc).should_receive('is_app_name_valid').and_return(True)
    response = Future()
    response.set_result(None)
    instance_manager._routing_client = flexmock(
      unregister_instance=lambda instance: response)
    flexmock(MonitOperator).should_receive('send_command_sync').\
      with_args('app___test_default_v1-20000', 'unmonitor').\
      and_raise(HTTPError)

    unmonitor_future = Future()
    unmonitor_future.set_exception(HTTPError(500))
    flexmock(instance_manager).should_receive('_unmonitor_and_terminate').\
      and_return(unmonitor_future)

    entries_response = Future()
    entries_response.set_result(['app___test_default_v1_revid-20000'])
    instance_manager._monit_operator = flexmock(
      get_entries=lambda: entries_response,
      reload=lambda x: response)

    with self.assertRaises(HTTPError):
      yield instance_manager._stop_app_instance(
        instance.Instance('_'.join([version_key, 'revid']), port))

    flexmock(MonitOperator).should_receive('send_command_sync').\
      with_args('app___test_default_v1-20000', 'unmonitor')
    flexmock(os).should_receive('remove')
    flexmock(monit_interface).should_receive('safe_monit_run')

    response = Future()
    response.set_result(None)
    flexmock(MonitOperator).should_receive('reload').\
      and_return(response)

    response = Future()
    response.set_result(None)
    flexmock(instance_manager).should_receive('_clean_old_sources').\
      and_return(response)

    response = Future()
    response.set_result(None)
    flexmock(instance_manager).should_receive('_unmonitor_and_terminate').\
      and_return(response)

    yield instance_manager._stop_app_instance(
      instance.Instance('_'.join([version_key, 'revid']), port))

  def test_remove_logrotate(self):
    flexmock(os).should_receive("remove").and_return()
    utils.remove_logrotate("test")

  @gen_test
  def test_wait_for_app(self):
    port = 20000
    ip = '127.0.0.1'
    testing.disable_logging()
    fake_opener = flexmock(
      open=lambda url, timeout: flexmock(code=200,
                                         headers=flexmock(headers=[])))
    flexmock(urllib2).should_receive('build_opener').and_return(fake_opener)
    flexmock(appscale_info).should_receive('get_private_ip').and_return(ip)

    instance_manager = InstanceManager(
      None, None, None, None, None, None, None, None, None)
    instance_manager._private_ip = ip
    instance_started = yield instance_manager._wait_for_app(port)
    self.assertEqual(True, instance_started)

    current_time = time.time()
    flexmock(time).should_receive('time').and_return(current_time).\
      and_return(current_time + START_APP_TIMEOUT + 1)
    response = Future()
    response.set_result(None)
    flexmock(gen).should_receive('sleep').and_return(response)
    fake_opener.should_receive('open').and_raise(IOError)
    instance_started = yield instance_manager._wait_for_app(port)
    self.assertEqual(False, instance_started)

if __name__ == "__main__":
  unittest.main()
