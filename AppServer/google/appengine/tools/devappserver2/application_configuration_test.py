#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Tests for google.apphosting.tools.devappserver2.application_configuration."""


import collections
import os.path
import unittest

import google
import mox

from google.appengine.api import appinfo
from google.appengine.api import backendinfo
from google.appengine.api import dispatchinfo
from google.appengine.tools.devappserver2 import application_configuration
from google.appengine.tools.devappserver2 import errors


class TestServerConfiguration(unittest.TestCase):
  """Tests for application_configuration.ServerConfiguration."""

  def setUp(self):
    self.mox = mox.Mox()
    self.mox.StubOutWithMock(
        application_configuration.ServerConfiguration,
        '_parse_configuration')
    self.mox.StubOutWithMock(os.path, 'getmtime')

  def tearDown(self):
    self.mox.UnsetStubs()

  def test_good_app_yaml_configuration(self):
    automatic_scaling = appinfo.AutomaticScaling(min_pending_latency='1.0s',
                                                 max_pending_latency='2.0s',
                                                 min_idle_instances=1,
                                                 max_idle_instances=2)
    error_handlers = [appinfo.ErrorHandlers(file='error.html')]
    handlers = [appinfo.URLMap()]
    env_variables = appinfo.EnvironmentVariables()
    info = appinfo.AppInfoExternal(
        application='app',
        server='server1',
        version='1',
        runtime='python27',
        threadsafe=False,
        automatic_scaling=automatic_scaling,
        skip_files=r'\*.gif',
        error_handlers=error_handlers,
        handlers=handlers,
        inbound_services=['warmup'],
        env_variables=env_variables,
        )
    application_configuration.ServerConfiguration._parse_configuration(
        '/appdir/app.yaml').AndReturn((info, []))
    os.path.getmtime('/appdir/app.yaml').AndReturn(10)

    self.mox.ReplayAll()
    config = application_configuration.ServerConfiguration(
        '/appdir/app.yaml')
    self.mox.VerifyAll()

    self.assertEqual(os.path.realpath('/appdir'), config.application_root)
    self.assertEqual('dev~app', config.application)
    self.assertEqual('server1', config.server_name)
    self.assertEqual('1', config.major_version)
    self.assertRegexpMatches(config.version_id, r'server1:1\.\d+')
    self.assertEqual('python27', config.runtime)
    self.assertFalse(config.threadsafe)
    self.assertEqual(automatic_scaling, config.automatic_scaling)
    self.assertEqual(info.GetNormalizedLibraries(),
                     config.normalized_libraries)
    self.assertEqual(r'\*.gif', config.skip_files)
    self.assertEqual(error_handlers, config.error_handlers)
    self.assertEqual(handlers, config.handlers)
    self.assertEqual(['warmup'], config.inbound_services)
    self.assertEqual(env_variables, config.env_variables)
    self.assertEqual({'/appdir/app.yaml': 10}, config._mtimes)

  def test_check_for_updates_unchanged_mtime(self):
    info = appinfo.AppInfoExternal(
        application='app',
        server='default',
        version='version',
        runtime='python27',
        threadsafe=False)
    application_configuration.ServerConfiguration._parse_configuration(
        '/appdir/app.yaml').AndReturn((info, []))
    os.path.getmtime('/appdir/app.yaml').AndReturn(10)
    os.path.getmtime('/appdir/app.yaml').AndReturn(10)

    self.mox.ReplayAll()
    config = application_configuration.ServerConfiguration('/appdir/app.yaml')
    self.assertSequenceEqual(set(), config.check_for_updates())
    self.mox.VerifyAll()

  def test_check_for_updates_with_includes(self):
    info = appinfo.AppInfoExternal(
        application='app',
        server='default',
        version='version',
        runtime='python27',
        includes=['/appdir/include.yaml'],
        threadsafe=False)
    application_configuration.ServerConfiguration._parse_configuration(
        '/appdir/app.yaml').AndReturn((info, ['/appdir/include.yaml']))
    os.path.getmtime('/appdir/app.yaml').InAnyOrder().AndReturn(10)
    os.path.getmtime('/appdir/include.yaml').InAnyOrder().AndReturn(10)
    os.path.getmtime('/appdir/app.yaml').AndReturn(10)
    os.path.getmtime('/appdir/include.yaml').AndReturn(11)

    application_configuration.ServerConfiguration._parse_configuration(
        '/appdir/app.yaml').AndReturn((info, ['/appdir/include.yaml']))
    os.path.getmtime('/appdir/app.yaml').InAnyOrder().AndReturn(10)
    os.path.getmtime('/appdir/include.yaml').InAnyOrder().AndReturn(11)

    self.mox.ReplayAll()
    config = application_configuration.ServerConfiguration('/appdir/app.yaml')
    self.assertEqual({'/appdir/app.yaml': 10, '/appdir/include.yaml': 10},
                     config._mtimes)
    config._mtimes = collections.OrderedDict([('/appdir/app.yaml', 10),
                                              ('/appdir/include.yaml', 10)])
    self.assertSequenceEqual(set(), config.check_for_updates())
    self.mox.VerifyAll()
    self.assertEqual({'/appdir/app.yaml': 10, '/appdir/include.yaml': 11},
                     config._mtimes)

  def test_check_for_updates_no_changes(self):
    info = appinfo.AppInfoExternal(
        application='app',
        server='default',
        version='version',
        runtime='python27',
        threadsafe=False)
    application_configuration.ServerConfiguration._parse_configuration(
        '/appdir/app.yaml').AndReturn((info, []))
    os.path.getmtime('/appdir/app.yaml').AndReturn(10)
    os.path.getmtime('/appdir/app.yaml').AndReturn(11)
    application_configuration.ServerConfiguration._parse_configuration(
        '/appdir/app.yaml').AndReturn((info, []))
    os.path.getmtime('/appdir/app.yaml').AndReturn(11)

    self.mox.ReplayAll()
    config = application_configuration.ServerConfiguration('/appdir/app.yaml')
    self.assertSequenceEqual(set(), config.check_for_updates())
    self.mox.VerifyAll()
    self.assertEqual({'/appdir/app.yaml': 11}, config._mtimes)

  def test_check_for_updates_immutable_changes(self):
    automatic_scaling1 = appinfo.AutomaticScaling(
        min_pending_latency='0.1s',
        max_pending_latency='1.0s',
        min_idle_instances=1,
        max_idle_instances=2)
    info1 = appinfo.AppInfoExternal(
        application='app',
        server='default',
        version='version',
        runtime='python27',
        threadsafe=False,
        automatic_scaling=automatic_scaling1)

    info2 = appinfo.AppInfoExternal(
        application='app2',
        server='default2',
        version='version2',
        runtime='python',
        threadsafe=True,
        automatic_scaling=appinfo.AutomaticScaling(
            min_pending_latency='1.0s',
            max_pending_latency='2.0s',
            min_idle_instances=1,
            max_idle_instances=2))

    application_configuration.ServerConfiguration._parse_configuration(
        '/appdir/app.yaml').AndReturn((info1, []))
    os.path.getmtime('/appdir/app.yaml').AndReturn(10)
    os.path.getmtime('/appdir/app.yaml').AndReturn(11)
    application_configuration.ServerConfiguration._parse_configuration(
        '/appdir/app.yaml').AndReturn((info2, []))
    os.path.getmtime('/appdir/app.yaml').AndReturn(11)

    self.mox.ReplayAll()
    config = application_configuration.ServerConfiguration('/appdir/app.yaml')
    self.assertSequenceEqual(set(), config.check_for_updates())
    self.mox.VerifyAll()

    self.assertEqual('dev~app', config.application)
    self.assertEqual('default', config.server_name)
    self.assertEqual('version', config.major_version)
    self.assertRegexpMatches(config.version_id, r'^version\.\d+$')
    self.assertEqual('python27', config.runtime)
    self.assertFalse(config.threadsafe)
    self.assertEqual(automatic_scaling1, config.automatic_scaling)

  def test_check_for_mutable_changes(self):
    info1 = appinfo.AppInfoExternal(
        application='app',
        server='default',
        version='version',
        runtime='python27',
        threadsafe=False,
        libraries=[appinfo.Library(name='django', version='latest')],
        skip_files='.*',
        handlers=[],
        inbound_services=['warmup'],
        env_variables=appinfo.EnvironmentVariables(),
        error_handlers=[appinfo.ErrorHandlers(file='error.html')],
        )
    info2 = appinfo.AppInfoExternal(
        application='app',
        server='default',
        version='version',
        runtime='python27',
        threadsafe=False,
        libraries=[appinfo.Library(name='jinja2', version='latest')],
        skip_files=r'.*\.py',
        handlers=[appinfo.URLMap()],
        inbound_services=[],
        )

    application_configuration.ServerConfiguration._parse_configuration(
        '/appdir/app.yaml').AndReturn((info1, []))
    os.path.getmtime('/appdir/app.yaml').AndReturn(10)
    os.path.getmtime('/appdir/app.yaml').AndReturn(11)
    application_configuration.ServerConfiguration._parse_configuration(
        '/appdir/app.yaml').AndReturn((info2, []))
    os.path.getmtime('/appdir/app.yaml').AndReturn(11)

    self.mox.ReplayAll()
    config = application_configuration.ServerConfiguration('/appdir/app.yaml')
    self.assertSequenceEqual(
        set([application_configuration.NORMALIZED_LIBRARIES_CHANGED,
             application_configuration.SKIP_FILES_CHANGED,
             application_configuration.HANDLERS_CHANGED,
             application_configuration.INBOUND_SERVICES_CHANGED,
             application_configuration.ENV_VARIABLES_CHANGED,
             application_configuration.ERROR_HANDLERS_CHANGED]),
        config.check_for_updates())
    self.mox.VerifyAll()

    self.assertEqual(info2.GetNormalizedLibraries(),
                     config.normalized_libraries)
    self.assertEqual(info2.skip_files, config.skip_files)
    self.assertEqual(info2.error_handlers, config.error_handlers)
    self.assertEqual(info2.handlers, config.handlers)
    self.assertEqual(info2.inbound_services, config.inbound_services)
    self.assertEqual(info2.env_variables, config.env_variables)



class TestBackendsConfiguration(unittest.TestCase):
  def setUp(self):
    self.mox = mox.Mox()
    self.mox.StubOutWithMock(
        application_configuration.BackendsConfiguration,
        '_parse_configuration')
    self.mox.StubOutWithMock(application_configuration, 'BackendConfiguration')

  def tearDown(self):
    self.mox.UnsetStubs()

  def test_good_configuration(self):
    self.mox.StubOutWithMock(application_configuration, 'ServerConfiguration')
    static_backend_entry = backendinfo.BackendEntry(name='static')
    dynamic_backend_entry = backendinfo.BackendEntry(name='dynamic')
    backend_info = backendinfo.BackendInfoExternal(
        backends=[static_backend_entry, dynamic_backend_entry])
    server_config = object()
    application_configuration.ServerConfiguration(
        '/appdir/app.yaml').AndReturn(server_config)
    application_configuration.BackendsConfiguration._parse_configuration(
        '/appdir/backends.yaml').AndReturn(backend_info)
    static_configuration = object()
    dynamic_configuration = object()
    application_configuration.BackendConfiguration(
        server_config,
        mox.IgnoreArg(),
        static_backend_entry).InAnyOrder().AndReturn(static_configuration)
    application_configuration.BackendConfiguration(
        server_config,
        mox.IgnoreArg(),
        dynamic_backend_entry).InAnyOrder().AndReturn(dynamic_configuration)

    self.mox.ReplayAll()
    config = application_configuration.BackendsConfiguration(
        '/appdir/app.yaml',
        '/appdir/backends.yaml')
    self.assertItemsEqual([static_configuration, dynamic_configuration],
                          config.get_backend_configurations())
    self.mox.VerifyAll()

  def test_no_backends(self):
    self.mox.StubOutWithMock(application_configuration, 'ServerConfiguration')
    backend_info = backendinfo.BackendInfoExternal()
    server_config = object()
    application_configuration.ServerConfiguration(
        '/appdir/app.yaml').AndReturn(server_config)
    application_configuration.BackendsConfiguration._parse_configuration(
        '/appdir/backends.yaml').AndReturn(backend_info)

    self.mox.ReplayAll()
    config = application_configuration.BackendsConfiguration(
        '/appdir/app.yaml',
        '/appdir/backends.yaml')
    self.assertEqual([], config.get_backend_configurations())
    self.mox.VerifyAll()

  def test_check_for_changes(self):
    static_backend_entry = backendinfo.BackendEntry(name='static')
    dynamic_backend_entry = backendinfo.BackendEntry(name='dynamic')
    backend_info = backendinfo.BackendInfoExternal(
        backends=[static_backend_entry, dynamic_backend_entry])
    server_config = self.mox.CreateMock(
        application_configuration.ServerConfiguration)
    self.mox.StubOutWithMock(application_configuration, 'ServerConfiguration')
    application_configuration.ServerConfiguration(
        '/appdir/app.yaml').AndReturn(server_config)
    application_configuration.BackendsConfiguration._parse_configuration(
        '/appdir/backends.yaml').AndReturn(backend_info)
    server_config.check_for_updates().AndReturn(set())
    server_config.check_for_updates().AndReturn(set([1]))
    server_config.check_for_updates().AndReturn(set([2]))
    server_config.check_for_updates().AndReturn(set())

    self.mox.ReplayAll()
    config = application_configuration.BackendsConfiguration(
        '/appdir/app.yaml',
        '/appdir/backends.yaml')
    self.assertEqual(set(), config.check_for_updates('dynamic'))
    self.assertEqual(set([1]), config.check_for_updates('static'))
    self.assertEqual(set([1, 2]), config.check_for_updates('dynamic'))
    self.assertEqual(set([2]), config.check_for_updates('static'))
    self.mox.VerifyAll()


class TestDispatchConfiguration(unittest.TestCase):
  def setUp(self):
    self.mox = mox.Mox()
    self.mox.StubOutWithMock(os.path, 'getmtime')
    self.mox.StubOutWithMock(
        application_configuration.DispatchConfiguration,
        '_parse_configuration')

  def tearDown(self):
    self.mox.UnsetStubs()

  def test_good_configuration(self):
    info = dispatchinfo.DispatchInfoExternal(
        application='appid',
        dispatch=[
            dispatchinfo.DispatchEntry(url='*/path', server='foo'),
            dispatchinfo.DispatchEntry(url='domain.com/path', server='bar'),
            dispatchinfo.DispatchEntry(url='*/path/*', server='baz'),
            dispatchinfo.DispatchEntry(url='*.domain.com/path/*', server='foo'),
            ])

    os.path.getmtime('/appdir/dispatch.yaml').AndReturn(123.456)
    application_configuration.DispatchConfiguration._parse_configuration(
        '/appdir/dispatch.yaml').AndReturn(info)

    self.mox.ReplayAll()
    config = application_configuration.DispatchConfiguration(
        '/appdir/dispatch.yaml')
    self.mox.VerifyAll()

    self.assertEqual(123.456, config._mtime)
    self.assertEqual(2, len(config.dispatch))
    self.assertEqual(vars(dispatchinfo.ParsedURL('*/path')),
                     vars(config.dispatch[0][0]))
    self.assertEqual('foo', config.dispatch[0][1])
    self.assertEqual(vars(dispatchinfo.ParsedURL('*/path/*')),
                     vars(config.dispatch[1][0]))
    self.assertEqual('baz', config.dispatch[1][1])

  def test_check_for_updates_no_modification(self):
    info = dispatchinfo.DispatchInfoExternal(
        application='appid',
        dispatch=[])

    os.path.getmtime('/appdir/dispatch.yaml').AndReturn(123.456)
    application_configuration.DispatchConfiguration._parse_configuration(
        '/appdir/dispatch.yaml').AndReturn(info)
    os.path.getmtime('/appdir/dispatch.yaml').AndReturn(123.456)

    self.mox.ReplayAll()
    config = application_configuration.DispatchConfiguration(
        '/appdir/dispatch.yaml')
    config.check_for_updates()
    self.mox.VerifyAll()

  def test_check_for_updates_with_invalid_modification(self):
    info = dispatchinfo.DispatchInfoExternal(
        application='appid',
        dispatch=[
            dispatchinfo.DispatchEntry(url='*/path', server='bar'),
            ])

    os.path.getmtime('/appdir/dispatch.yaml').AndReturn(123.456)
    application_configuration.DispatchConfiguration._parse_configuration(
        '/appdir/dispatch.yaml').AndReturn(info)
    os.path.getmtime('/appdir/dispatch.yaml').AndReturn(124.456)
    application_configuration.DispatchConfiguration._parse_configuration(
        '/appdir/dispatch.yaml').AndRaise(Exception)

    self.mox.ReplayAll()
    config = application_configuration.DispatchConfiguration(
        '/appdir/dispatch.yaml')
    self.assertEqual('bar', config.dispatch[0][1])
    config.check_for_updates()
    self.mox.VerifyAll()
    self.assertEqual('bar', config.dispatch[0][1])

  def test_check_for_updates_with_modification(self):
    info = dispatchinfo.DispatchInfoExternal(
        application='appid',
        dispatch=[
            dispatchinfo.DispatchEntry(url='*/path', server='bar'),
            ])
    new_info = dispatchinfo.DispatchInfoExternal(
        application='appid',
        dispatch=[
            dispatchinfo.DispatchEntry(url='*/path', server='foo'),
            ])

    os.path.getmtime('/appdir/dispatch.yaml').AndReturn(123.456)
    application_configuration.DispatchConfiguration._parse_configuration(
        '/appdir/dispatch.yaml').AndReturn(info)
    os.path.getmtime('/appdir/dispatch.yaml').AndReturn(124.456)
    application_configuration.DispatchConfiguration._parse_configuration(
        '/appdir/dispatch.yaml').AndReturn(new_info)

    self.mox.ReplayAll()
    config = application_configuration.DispatchConfiguration(
        '/appdir/dispatch.yaml')
    self.assertEqual('bar', config.dispatch[0][1])
    config.check_for_updates()
    self.mox.VerifyAll()
    self.assertEqual('foo', config.dispatch[0][1])


class TestBackendConfiguration(unittest.TestCase):
  def setUp(self):
    self.mox = mox.Mox()
    self.mox.StubOutWithMock(
        application_configuration.ServerConfiguration,
        '_parse_configuration')
    self.mox.StubOutWithMock(os.path, 'getmtime')

  def tearDown(self):
    self.mox.UnsetStubs()

  def test_good_configuration(self):
    automatic_scaling = appinfo.AutomaticScaling(min_pending_latency='1.0s',
                                                 max_pending_latency='2.0s',
                                                 min_idle_instances=1,
                                                 max_idle_instances=2)
    error_handlers = [appinfo.ErrorHandlers(file='error.html')]
    handlers = [appinfo.URLMap()]
    env_variables = appinfo.EnvironmentVariables()
    info = appinfo.AppInfoExternal(
        application='app',
        server='server1',
        version='1',
        runtime='python27',
        threadsafe=False,
        automatic_scaling=automatic_scaling,
        skip_files=r'\*.gif',
        error_handlers=error_handlers,
        handlers=handlers,
        inbound_services=['warmup'],
        env_variables=env_variables,
        )
    backend_entry = backendinfo.BackendEntry(
        name='static',
        instances='3',
        options='public')

    application_configuration.ServerConfiguration._parse_configuration(
        '/appdir/app.yaml').AndReturn((info, []))
    os.path.getmtime('/appdir/app.yaml').AndReturn(10)

    self.mox.ReplayAll()
    server_config = application_configuration.ServerConfiguration(
        '/appdir/app.yaml')
    config = application_configuration.BackendConfiguration(
        server_config, None, backend_entry)
    self.mox.VerifyAll()

    self.assertEqual(os.path.realpath('/appdir'), config.application_root)
    self.assertEqual('dev~app', config.application)
    self.assertEqual('static', config.server_name)
    self.assertEqual('1', config.major_version)
    self.assertRegexpMatches(config.version_id, r'static:1\.\d+')
    self.assertEqual('python27', config.runtime)
    self.assertFalse(config.threadsafe)
    self.assertEqual(None, config.automatic_scaling)
    self.assertEqual(None, config.basic_scaling)
    self.assertEqual(appinfo.ManualScaling(instances='3'),
                     config.manual_scaling)
    self.assertEqual(info.GetNormalizedLibraries(),
                     config.normalized_libraries)
    self.assertEqual(r'\*.gif', config.skip_files)
    self.assertEqual(error_handlers, config.error_handlers)
    self.assertEqual(handlers, config.handlers)
    self.assertEqual(['warmup'], config.inbound_services)
    self.assertEqual(env_variables, config.env_variables)

    whitelist_fields = ['server_name', 'version_id', 'automatic_scaling',
                        'manual_scaling', 'basic_scaling', 'is_backend']
    # Check that all public attributes and methods in a ServerConfiguration
    # exist in a BackendConfiguration.
    for field in dir(server_config):
      if not field.startswith('_'):
        self.assertTrue(hasattr(config, field), 'Missing field: %s' % field)
        value = getattr(server_config, field)
        if field not in whitelist_fields and not callable(value):
          # Check that the attributes other than those in the whitelist have
          # equal values in the BackendConfiguration to the ServerConfiguration
          # from which it inherits.
          self.assertEqual(value, getattr(config, field))

  def test_good_configuration_dynamic_scaling(self):
    automatic_scaling = appinfo.AutomaticScaling(min_pending_latency='1.0s',
                                                 max_pending_latency='2.0s',
                                                 min_idle_instances=1,
                                                 max_idle_instances=2)
    error_handlers = [appinfo.ErrorHandlers(file='error.html')]
    handlers = [appinfo.URLMap()]
    env_variables = appinfo.EnvironmentVariables()
    info = appinfo.AppInfoExternal(
        application='app',
        server='server1',
        version='1',
        runtime='python27',
        threadsafe=False,
        automatic_scaling=automatic_scaling,
        skip_files=r'\*.gif',
        error_handlers=error_handlers,
        handlers=handlers,
        inbound_services=['warmup'],
        env_variables=env_variables,
        )
    backend_entry = backendinfo.BackendEntry(
        name='dynamic',
        instances='3',
        options='public, dynamic',
        start='handler')

    application_configuration.ServerConfiguration._parse_configuration(
        '/appdir/app.yaml').AndReturn((info, []))
    os.path.getmtime('/appdir/app.yaml').AndReturn(10)

    self.mox.ReplayAll()
    server_config = application_configuration.ServerConfiguration(
        '/appdir/app.yaml')
    config = application_configuration.BackendConfiguration(
        server_config, None, backend_entry)
    self.mox.VerifyAll()

    self.assertEqual(os.path.realpath('/appdir'), config.application_root)
    self.assertEqual('dev~app', config.application)
    self.assertEqual('dynamic', config.server_name)
    self.assertEqual('1', config.major_version)
    self.assertRegexpMatches(config.version_id, r'dynamic:1\.\d+')
    self.assertEqual('python27', config.runtime)
    self.assertFalse(config.threadsafe)
    self.assertEqual(None, config.automatic_scaling)
    self.assertEqual(None, config.manual_scaling)
    self.assertEqual(appinfo.BasicScaling(max_instances='3'),
                     config.basic_scaling)
    self.assertEqual(info.GetNormalizedLibraries(),
                     config.normalized_libraries)
    self.assertEqual(r'\*.gif', config.skip_files)
    self.assertEqual(error_handlers, config.error_handlers)
    start_handler = appinfo.URLMap(url='/_ah/start',
                                   script=backend_entry.start,
                                   login='admin')
    self.assertEqual([start_handler] + handlers, config.handlers)
    self.assertEqual(['warmup'], config.inbound_services)
    self.assertEqual(env_variables, config.env_variables)

  def test_check_for_changes(self):
    backends_config = self.mox.CreateMock(
        application_configuration.BackendsConfiguration)
    config = application_configuration.BackendConfiguration(
        None, backends_config, backendinfo.BackendEntry(name='backend'))
    changes = object()
    backends_config.check_for_updates('backend').AndReturn([])
    backends_config.check_for_updates('backend').AndReturn(changes)
    minor_version = config._minor_version_id
    self.mox.ReplayAll()
    self.assertEqual([], config.check_for_updates())
    self.assertEqual(minor_version, config._minor_version_id)
    self.assertEqual(changes, config.check_for_updates())
    self.assertNotEqual(minor_version, config._minor_version_id)
    self.mox.VerifyAll()


class ServerConfigurationStub(object):
  def __init__(self, application='myapp', server_name='server'):
    self.application = application
    self.server_name = server_name


class DispatchConfigurationStub(object):
  def __init__(self, dispatch):
    self.dispatch = dispatch


class TestApplicationConfiguration(unittest.TestCase):
  """Tests for application_configuration.ApplicationConfiguration."""

  def setUp(self):
    self.mox = mox.Mox()
    self.mox.StubOutWithMock(os.path, 'isdir')
    self.mox.StubOutWithMock(os.path, 'getmtime')
    self.mox.StubOutWithMock(os.path, 'exists')
    self.mox.StubOutWithMock(application_configuration, 'ServerConfiguration')
    self.mox.StubOutWithMock(application_configuration, 'BackendsConfiguration')
    self.mox.StubOutWithMock(application_configuration, 'DispatchConfiguration')

  def tearDown(self):
    self.mox.UnsetStubs()

  def test_yaml_files(self):
    os.path.isdir('/appdir/app.yaml').AndReturn(False)
    server_config1 = ServerConfigurationStub()
    application_configuration.ServerConfiguration(
        '/appdir/app.yaml').AndReturn(server_config1)

    os.path.isdir('/appdir/other.yaml').AndReturn(False)
    server_config2 = ServerConfigurationStub(server_name='other')
    application_configuration.ServerConfiguration(
        '/appdir/other.yaml').AndReturn(server_config2)

    self.mox.ReplayAll()
    config = application_configuration.ApplicationConfiguration(
        ['/appdir/app.yaml', '/appdir/other.yaml'])
    self.mox.VerifyAll()
    self.assertEqual('myapp', config.app_id)
    self.assertSequenceEqual([server_config1, server_config2], config.servers)

  def test_yaml_files_with_different_app_ids(self):
    os.path.isdir('/appdir/app.yaml').AndReturn(False)
    server_config1 = ServerConfigurationStub()
    application_configuration.ServerConfiguration(
        '/appdir/app.yaml').AndReturn(server_config1)

    os.path.isdir('/appdir/other.yaml').AndReturn(False)
    server_config2 = ServerConfigurationStub(application='other_app',
                                             server_name='other')
    application_configuration.ServerConfiguration(
        '/appdir/other.yaml').AndReturn(server_config2)

    self.mox.ReplayAll()
    self.assertRaises(errors.InvalidAppConfigError,
                      application_configuration.ApplicationConfiguration,
                      ['/appdir/app.yaml', '/appdir/other.yaml'])
    self.mox.VerifyAll()

  def test_yaml_files_with_duplicate_server_names(self):
    os.path.isdir('/appdir/app.yaml').AndReturn(False)
    application_configuration.ServerConfiguration(
        '/appdir/app.yaml').AndReturn(ServerConfigurationStub())

    os.path.isdir('/appdir/other.yaml').AndReturn(False)
    application_configuration.ServerConfiguration(
        '/appdir/other.yaml').AndReturn(ServerConfigurationStub())

    self.mox.ReplayAll()
    self.assertRaises(errors.InvalidAppConfigError,
                      application_configuration.ApplicationConfiguration,
                      ['/appdir/app.yaml', '/appdir/other.yaml'])
    self.mox.VerifyAll()

  def test_directory(self):
    os.path.isdir('/appdir').AndReturn(True)
    os.path.exists(os.path.join('/appdir', 'app.yaml')).AndReturn(True)
    os.path.exists(os.path.join('/appdir', 'backends.yaml')).AndReturn(False)
    os.path.exists(os.path.join('/appdir', 'backends.yml')).AndReturn(False)
    os.path.isdir(os.path.join('/appdir', 'app.yaml')).AndReturn(False)

    server_config = ServerConfigurationStub()
    application_configuration.ServerConfiguration(
        os.path.join('/appdir', 'app.yaml')).AndReturn(server_config)

    self.mox.ReplayAll()
    config = application_configuration.ApplicationConfiguration(['/appdir'])
    self.mox.VerifyAll()
    self.assertEqual('myapp', config.app_id)
    self.assertSequenceEqual([server_config], config.servers)

  def test_directory_app_yml_only(self):
    os.path.isdir('/appdir').AndReturn(True)
    os.path.exists(os.path.join('/appdir', 'app.yaml')).AndReturn(False)
    os.path.exists(os.path.join('/appdir', 'app.yml')).AndReturn(True)
    os.path.exists(os.path.join('/appdir', 'backends.yaml')).AndReturn(False)
    os.path.exists(os.path.join('/appdir', 'backends.yml')).AndReturn(False)
    os.path.isdir(os.path.join('/appdir', 'app.yml')).AndReturn(False)

    server_config = ServerConfigurationStub()
    application_configuration.ServerConfiguration(
        os.path.join('/appdir', 'app.yml')).AndReturn(server_config)

    self.mox.ReplayAll()
    config = application_configuration.ApplicationConfiguration(['/appdir'])
    self.mox.VerifyAll()
    self.assertEqual('myapp', config.app_id)
    self.assertSequenceEqual([server_config], config.servers)

  def test_directory_no_app_yamls(self):
    os.path.isdir('/appdir').AndReturn(True)
    os.path.exists(os.path.join('/appdir', 'app.yaml')).AndReturn(False)
    os.path.exists(os.path.join('/appdir', 'app.yml')).AndReturn(False)
    self.mox.ReplayAll()
    self.assertRaises(errors.AppConfigNotFoundError,
                      application_configuration.ApplicationConfiguration,
                      ['/appdir'])
    self.mox.VerifyAll()

  def test_app_yaml(self):
    os.path.isdir('/appdir/app.yaml').AndReturn(False)
    os.path.isdir('/appdir/app.yaml').AndReturn(False)

    server_config = ServerConfigurationStub()
    application_configuration.ServerConfiguration(
        '/appdir/app.yaml').AndReturn(server_config)

    self.mox.ReplayAll()
    config = application_configuration.ApplicationConfiguration(
        ['/appdir/app.yaml'])
    self.mox.VerifyAll()
    self.assertEqual('myapp', config.app_id)
    self.assertSequenceEqual([server_config], config.servers)

  def test_directory_with_backends_yaml(self):
    os.path.isdir('/appdir').AndReturn(True)
    os.path.exists(os.path.join('/appdir', 'app.yaml')).AndReturn(True)
    os.path.isdir(os.path.join('/appdir', 'app.yaml')).AndReturn(False)
    os.path.exists(os.path.join('/appdir', 'backends.yaml')).AndReturn(True)
    os.path.isdir(os.path.join('/appdir', 'backends.yaml')).AndReturn(False)

    server_config = ServerConfigurationStub()
    application_configuration.ServerConfiguration(
        os.path.join('/appdir', 'app.yaml')).AndReturn(server_config)
    backend_config = ServerConfigurationStub(server_name='backend')
    backends_config = self.mox.CreateMock(
        application_configuration.BackendsConfiguration)
    backends_config.get_backend_configurations().AndReturn([backend_config])
    application_configuration.BackendsConfiguration(
        os.path.join('/appdir', 'app.yaml'),
        os.path.join('/appdir', 'backends.yaml')).AndReturn(backends_config)

    self.mox.ReplayAll()
    config = application_configuration.ApplicationConfiguration(['/appdir'])
    self.mox.VerifyAll()
    self.assertEqual('myapp', config.app_id)
    self.assertSequenceEqual([server_config, backend_config], config.servers)

  def test_yaml_files_with_backends_yaml(self):
    os.path.isdir('/appdir/app.yaml').AndReturn(False)
    server_config = ServerConfigurationStub()
    application_configuration.ServerConfiguration(
        '/appdir/app.yaml').AndReturn(server_config)

    os.path.isdir('/appdir/backends.yaml').AndReturn(False)
    backend_config = ServerConfigurationStub(server_name='backend')
    backends_config = self.mox.CreateMock(
        application_configuration.BackendsConfiguration)
    backends_config.get_backend_configurations().AndReturn([backend_config])
    application_configuration.BackendsConfiguration(
        '/appdir/app.yaml',
        '/appdir/backends.yaml').AndReturn(backends_config)

    self.mox.ReplayAll()
    config = application_configuration.ApplicationConfiguration(
        ['/appdir/app.yaml', '/appdir/backends.yaml'])
    self.mox.VerifyAll()
    self.assertEqual('myapp', config.app_id)
    self.assertSequenceEqual([server_config, backend_config], config.servers)

  def test_yaml_files_with_backends_and_dispatch_yaml(self):
    os.path.isdir('/appdir/app.yaml').AndReturn(False)
    server_config = ServerConfigurationStub(server_name='default')
    application_configuration.ServerConfiguration(
        '/appdir/app.yaml').AndReturn(server_config)

    os.path.isdir('/appdir/backends.yaml').AndReturn(False)
    backend_config = ServerConfigurationStub(server_name='backend')
    backends_config = self.mox.CreateMock(
        application_configuration.BackendsConfiguration)
    backends_config.get_backend_configurations().AndReturn([backend_config])
    application_configuration.BackendsConfiguration(
        os.path.join('/appdir', 'app.yaml'),
        os.path.join('/appdir', 'backends.yaml')).AndReturn(backends_config)
    os.path.isdir('/appdir/dispatch.yaml').AndReturn(False)
    dispatch_config = DispatchConfigurationStub(
        [(None, 'default'), (None, 'backend')])
    application_configuration.DispatchConfiguration(
        '/appdir/dispatch.yaml').AndReturn(dispatch_config)

    self.mox.ReplayAll()
    config = application_configuration.ApplicationConfiguration(
        ['/appdir/app.yaml', '/appdir/backends.yaml', '/appdir/dispatch.yaml'])
    self.mox.VerifyAll()
    self.assertEqual('myapp', config.app_id)
    self.assertSequenceEqual([server_config, backend_config], config.servers)
    self.assertEqual(dispatch_config, config.dispatch)

  def test_yaml_files_dispatch_yaml_and_no_default_server(self):
    os.path.isdir('/appdir/app.yaml').AndReturn(False)
    server_config = ServerConfigurationStub(server_name='not-default')
    application_configuration.ServerConfiguration(
        '/appdir/app.yaml').AndReturn(server_config)

    os.path.isdir('/appdir/dispatch.yaml').AndReturn(False)
    dispatch_config = DispatchConfigurationStub([(None, 'default')])
    application_configuration.DispatchConfiguration(
        '/appdir/dispatch.yaml').AndReturn(dispatch_config)

    self.mox.ReplayAll()
    self.assertRaises(errors.InvalidAppConfigError,
                      application_configuration.ApplicationConfiguration,
                      ['/appdir/app.yaml', '/appdir/dispatch.yaml'])
    self.mox.VerifyAll()

  def test_yaml_files_dispatch_yaml_and_missing_dispatch_target(self):
    os.path.isdir('/appdir/app.yaml').AndReturn(False)
    server_config = ServerConfigurationStub(server_name='default')
    application_configuration.ServerConfiguration(
        '/appdir/app.yaml').AndReturn(server_config)

    os.path.isdir('/appdir/dispatch.yaml').AndReturn(False)
    dispatch_config = DispatchConfigurationStub(
        [(None, 'default'), (None, 'fake-server')])
    application_configuration.DispatchConfiguration(
        '/appdir/dispatch.yaml').AndReturn(dispatch_config)

    self.mox.ReplayAll()
    self.assertRaises(errors.InvalidAppConfigError,
                      application_configuration.ApplicationConfiguration,
                      ['/appdir/app.yaml', '/appdir/dispatch.yaml'])
    self.mox.VerifyAll()

if __name__ == '__main__':
  unittest.main()
