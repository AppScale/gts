# Programmer: Navraj Chohan <nlake44@gmail.com>

import os
import subprocess
import sys
import threading
import time
import unittest
import urllib2

from flexmock import flexmock
from tornado.gen import Future
from tornado.httpclient import HTTPError
from tornado.options import options
from tornado.testing import AsyncTestCase
from tornado.testing import gen_test

from appscale.common import (
  file_io,
  appscale_info,
  misc,
  monit_interface,
  testing
)
from appscale.common import monit_app_configuration
from appscale.common.monit_interface import MonitOperator

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
import app_manager_server
from app_manager_server import BadConfigurationException

options.define('login_ip', '127.0.0.1')
options.define('syslog_server', '127.0.0.1')
options.define('private_ip', '<private_ip>')
options.define('db_proxy', '<private_ip>')
options.define('tq_proxy', '<private_ip>')


class TestAppManager(AsyncTestCase):
  @gen_test
  def test_start_app_badconfig(self):
    testing.disable_logging()

    with self.assertRaises(BadConfigurationException):
      yield app_manager_server.start_app('test', {})

  @gen_test
  def test_start_app_bad_appname(self):
    configuration = {
      'app_port': 2000,
      'service_id': 'default',
      'version_id': 'v1',
      'env_vars': {}
    }

    version_manager = flexmock(version_details={'runtime': 'python27'})
    app_manager_server.projects_manager = {
      'test': {'default': {'v1': version_manager}}}

    with self.assertRaises(BadConfigurationException):
      yield app_manager_server.start_app(
        'badName!@#$%^&*([]/.,_default_v1', configuration)

  @gen_test
  def test_start_app_goodconfig_python(self):
    configuration = {
      'app_port': 2000,
      'service_id': 'default',
      'version_id': 'v1',
      'env_vars': {}
    }

    version_details = {'runtime': 'python27',
                       'revision': 1,
                       'deployment': {'zip': {'sourceUrl': 'source.tar.gz'}}}
    version_manager = flexmock(version_details=version_details)
    app_manager_server.projects_manager = {
      'test': {'default': {'v1': version_manager}}}
    app_manager_server.deployment_config = flexmock(
      get_config=lambda x: {'max_memory': 400})

    source_manager = flexmock()
    response = Future()
    response.set_result(None)
    source_manager.should_receive('ensure_source'). \
      with_args('test_default_v1_1', 'source.tar.gz', 'python27'). \
      and_return(response)
    app_manager_server.source_manager = source_manager

    flexmock(monit_app_configuration).should_receive('create_config_file').\
      and_return('fakeconfig')
    flexmock(monit_interface).should_receive('start').\
      and_return(True)
    flexmock(app_manager_server).should_receive('wait_on_app').\
      and_return(True)
    flexmock(os).should_receive('popen').\
      and_return(flexmock(read=lambda: '12345\n'))
    flexmock(file_io).should_receive('write').\
      and_return()
    flexmock(threading).should_receive('Thread').\
      and_return(flexmock(start=lambda: None))
    flexmock(app_manager_server).should_receive("setup_logrotate").and_return()

    yield app_manager_server.start_app('test_default_v1', configuration)

  @gen_test
  def test_start_app_goodconfig_java(self):
    configuration = {
      'app_port': 20000,
      'service_id': 'default',
      'version_id': 'v1',
      'env_vars': {}
    }

    version_details = {'runtime': 'java',
                       'revision': 1,
                       'deployment': {'zip': {'sourceUrl': 'source.tar.gz'}}}
    version_manager = flexmock(version_details=version_details)
    app_manager_server.projects_manager = {
      'test': {'default': {'v1': version_manager}}}
    app_manager_server.deployment_config = flexmock(
      get_config=lambda x: {'max_memory': 400})

    source_manager = flexmock()
    response = Future()
    response.set_result(None)
    source_manager.should_receive('ensure_source').\
      with_args('test_default_v1_1', 'source.tar.gz', 'java').\
      and_return(response)
    app_manager_server.source_manager = source_manager

    start_cmd = ('/root/appscale/AppServer_Java/appengine-java-repacked/bin/'
                 'dev_appserver.sh --port 20000')
    flexmock(app_manager_server).should_receive('create_java_start_cmd').\
      and_return(start_cmd)

    flexmock(monit_app_configuration).should_receive('create_config_file').\
      and_return('fakeconfig')
    flexmock(monit_interface).should_receive('start').\
      and_return(True)
    flexmock(app_manager_server).should_receive('create_java_app_env').\
      and_return({})
    flexmock(app_manager_server).should_receive('wait_on_app').\
      and_return(True)
    flexmock(app_manager_server).should_receive('locate_dir').\
      and_return('/path/to/dir/')
    flexmock(os).should_receive('popen').\
      and_return(flexmock(read=lambda: '0\n'))
    flexmock(file_io).should_receive('write').and_return()
    flexmock(subprocess).should_receive('call').and_return(0)
    flexmock(threading).should_receive('Thread').\
      and_return(flexmock(start=lambda: None))
    flexmock(app_manager_server).should_receive("setup_logrotate").and_return()
    flexmock(os).should_receive('listdir').and_return([])

    yield app_manager_server.start_app('test_default_v1', configuration)

  @gen_test
  def test_start_app_failed_copy_java(self):
    configuration = {
      'app_port': 2000,
      'service_id': 'default',
      'version_id': 'v1',
      'env_vars': {}
    }

    version_details = {'runtime': 'java',
                       'revision': 1,
                       'deployment': {'zip': {'sourceUrl': 'source.tar.gz'}}}
    version_manager = flexmock(version_details=version_details)
    app_manager_server.projects_manager = {
      'test': {'default': {'v1': version_manager}}}
    app_manager_server.deployment_config = flexmock(
      get_config=lambda x: {'max_memory': 400})

    source_manager = flexmock()
    response = Future()
    response.set_result(None)
    source_manager.should_receive('ensure_source').\
      with_args('test_default_v1_1', 'source.tar.gz', 'java').\
      and_return(response)
    app_manager_server.source_manager = source_manager

    flexmock(app_manager_server).should_receive('find_web_inf').\
      and_return('/path/to/dir/WEB-INF')
    flexmock(monit_app_configuration).should_receive('create_config_file').\
      and_raise(IOError)

    with self.assertRaises(IOError):
      yield app_manager_server.start_app('test_default_v1', configuration)

  def test_create_python_app_env(self):
    env_vars = app_manager_server.create_python_app_env('1', '2')
    self.assertEqual('1', env_vars['MY_IP_ADDRESS'])
    self.assertEqual('2', env_vars['APPNAME'])
    assert 'appscale' in env_vars['APPSCALE_HOME']
    assert 0 < int(env_vars['GOMAXPROCS'])

  def test_create_java_app_env(self):
    app_manager_server.deployment_config = flexmock(get_config=lambda x: {})
    app_name = 'foo'
    env_vars = app_manager_server.create_java_app_env(app_name)
    assert 'appscale' in env_vars['APPSCALE_HOME']

  def test_create_java_start_cmd(self):
    flexmock(app_manager_server).should_receive('find_web_inf').\
      and_return('/path/to/dir/WEB-INF')
    app_id = 'testapp'
    revision_key = 'testapp_default_v1'
    max_heap = 260
    pidfile = 'testpid'
    cmd = app_manager_server.create_java_start_cmd(
      app_id, '20000', '127.0.0.2', max_heap, pidfile, revision_key)
    assert app_id in cmd

  @gen_test
  def test_stop_app_instance(self):
    version_key = 'test_default_v1'
    port = 20000
    flexmock(misc).should_receive('is_app_name_valid').and_return(False)

    with self.assertRaises(BadConfigurationException):
      yield app_manager_server.stop_app_instance(version_key, port)

    flexmock(misc).should_receive('is_app_name_valid').and_return(True)
    flexmock(app_manager_server).should_receive('unmonitor').\
      and_raise(HTTPError)
    entries_response = Future()
    entries_response.set_result(['app___test_default_v1_revid-20000'])
    flexmock(MonitOperator).should_receive('get_entries').\
      and_return(entries_response)

    with self.assertRaises(HTTPError):
      yield app_manager_server.stop_app_instance(version_key, port)

    builtins = flexmock(sys.modules['__builtin__'])
    builtins.should_call('open')
    builtins.should_receive('open').\
      with_args('/var/run/appscale/app___test_default_v1_revid-20000.pid').\
      and_return(flexmock(read=lambda: '20000'))
    flexmock(app_manager_server).should_receive('unmonitor')
    flexmock(os).should_receive('remove')
    flexmock(monit_interface).should_receive('run_with_retry')

    response = Future()
    response.set_result(None)
    flexmock(app_manager_server).should_receive('clean_old_sources').\
      and_return(response)

    flexmock(threading.Thread).should_receive('__new__').and_return(
      flexmock(start=lambda: None))

    yield app_manager_server.stop_app_instance(version_key, port)

  def test_stop_app(self):
    flexmock(monit_interface).should_receive('stop').\
      and_return(True)
    flexmock(os).should_receive('system').\
      and_return(0)
    app_manager_server.stop_app('test')

  def test_remove_logrotate(self):
    flexmock(os).should_receive("remove").and_return()
    app_manager_server.remove_logrotate("test")

  def test_wait_on_app(self):
    port = 20000
    ip = '127.0.0.1'
    testing.disable_logging()
    fake_opener = flexmock(
      open=lambda opener: flexmock(code=200, headers=flexmock(headers=[])))
    flexmock(urllib2).should_receive('build_opener').and_return(fake_opener)
    flexmock(appscale_info).should_receive('get_private_ip').and_return(ip)
    self.assertEqual(True, app_manager_server.wait_on_app(port))

    flexmock(time).should_receive('sleep').and_return()
    fake_opener.should_receive('open').and_raise(IOError)
    self.assertEqual(False, app_manager_server.wait_on_app(port))
    
if __name__ == "__main__":
  unittest.main()
