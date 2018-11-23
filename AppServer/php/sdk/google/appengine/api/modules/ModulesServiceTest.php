<?php
/**
 * Copyright 2007 Google Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
/**
 * Unit tests for the Modules API.
 *
 */

namespace google\appengine\api\modules;

require_once 'google/appengine/api/modules/modules_service_pb.php';
require_once 'google/appengine/api/modules/ModulesService.php';
require_once 'google/appengine/runtime/ApplicationError.php';
require_once 'google/appengine/testing/ApiProxyTestBase.php';

use \google\appengine\runtime\ApplicationError;
use \google\appengine\testing\ApiProxyTestBase;
use \google\appengine\GetDefaultVersionRequest;
use \google\appengine\GetDefaultVersionResponse;
use \google\appengine\GetHostnameRequest;
use \google\appengine\GetHostnameResponse;
use \google\appengine\GetModulesRequest;
use \google\appengine\GetModulesResponse;
use \google\appengine\GetNumInstancesRequest;
use \google\appengine\GetNumInstancesResponse;
use \google\appengine\GetVersionsRequest;
use \google\appengine\GetVersionsResponse;
use \google\appengine\ModulesServiceError\ErrorCode;
use \google\appengine\SetNumInstancesRequest;
use \google\appengine\SetNumInstancesResponse;
use \google\appengine\StartModuleRequest;
use \google\appengine\StartModuleResponse;
use \google\appengine\StopModuleRequest;
use \google\appengine\StopModuleResponse;


class ModulesTest extends ApiProxyTestBase {

  public function setUp() {
    parent::setUp();
    $this->_SERVER = $_SERVER;
  }

  public function tearDown() {
    $_SERVER = $this->_SERVER;
    parent::tearDown();
  }

  public function testGetCurrentModuleNameWithDefaultModule() {
    $_SERVER['CURRENT_MODULE_ID'] = 'default';
    $_SERVER['CURRENT_VERSION_ID'] = 'v1.123';
    $this->assertEquals('default', ModulesService::getCurrentModuleName());
  }

  public function testGetCurrentModuleNameWithNonDefaultModule() {
    $_SERVER['CURRENT_MODULE_ID'] = 'module1';
    $_SERVER['CURRENT_VERSION_ID'] = 'v1.123';
    $this->assertEquals('module1', ModulesService::getCurrentModuleName());
  }

  public function testGetCurrentVersionName() {
    $_SERVER['CURRENT_VERSION_ID'] = 'v1.123';
    $this->assertEquals('v1', ModulesService::getCurrentVersionName());
  }

  public function testGetCurrentInstanceIdNoneSet() {
    $this->assertEquals(null, ModulesService::getCurrentInstanceId());
  }

  public function testGetCurrentInstanceId() {
    $_SERVER['INSTANCE_ID'] = '123';
    $this->assertEquals('123', ModulesService::getCurrentInstanceId());
  }

  public function testGetModules() {
    $req = new GetModulesRequest();
    $resp = new GetModulesResponse();

    $resp->addModule('module1');
    $resp->addModule('module2');

    $this->apiProxyMock->expectCall('modules', 'GetModules', $req, $resp);

    $this->assertEquals(['module1', 'module2'], ModulesService::getModules());
    $this->apiProxyMock->verify();
  }

  public function testGetVersions() {
    $req = new GetVersionsRequest();
    $resp = new GetVersionsResponse();

    $resp->addVersion('v1');
    $resp->addVersion('v2');

    $this->apiProxyMock->expectCall('modules', 'GetVersions', $req, $resp);

    $this->assertEquals(['v1', 'v2'], ModulesService::getVersions());
    $this->apiProxyMock->verify();
  }

  public function testGetVersionsWithModule() {
    $req = new GetVersionsRequest();
    $resp = new GetVersionsResponse();

    $req->setModule('module1');
    $resp->addVersion('v1');
    $resp->addVersion('v2');

    $this->apiProxyMock->expectCall('modules', 'GetVersions', $req, $resp);

    $this->assertEquals(['v1', 'v2'], ModulesService::getVersions('module1'));
    $this->apiProxyMock->verify();
  }

  public function testGetVersionsWithIntegerModule() {
    $this->setExpectedException('\InvalidArgumentException',
      '$module must be a string. Actual type: integer');
    ModulesService::getVersions(5);
  }

  public function testGetNumInstances() {
    $req = new GetNumInstancesRequest();
    $resp = new GetNumInstancesResponse();

    $resp->setInstances(3);

    $this->apiProxyMock->expectCall('modules', 'GetNumInstances', $req, $resp);

    $this->assertEquals(3, ModulesService::getNumInstances());
    $this->apiProxyMock->verify();
  }

  public function testGetNumInstancesWithModuleAndVersion() {
    $req = new GetNumInstancesRequest();
    $resp = new GetNumInstancesResponse();

    $req->setModule('module1');
    $req->setVersion('v1');
    $resp->setInstances(3);

    $this->apiProxyMock->expectCall('modules', 'GetNumInstances', $req, $resp);

    $this->assertEquals(3, ModulesService::getNumInstances('module1', 'v1'));
    $this->apiProxyMock->verify();
  }

  public function testGetNumInstancesWithIntegerModule() {
    $this->setExpectedException('\InvalidArgumentException',
      '$module must be a string. Actual type: integer');
    ModulesService::getNumInstances(5);
  }

  public function testGetNumInstancesWithIntegerVersion() {
    $this->setExpectedException('\InvalidArgumentException',
      '$version must be a string. Actual type: integer');
    ModulesService::getNumInstances('module1', 5);
  }

  public function testGetNumInstancesInvalidModule() {
    $req = new GetNumInstancesRequest();
    $resp = new ApplicationError(ErrorCode::INVALID_MODULE, 'invalid module');

    $this->setExpectedException(
        '\google\appengine\api\modules\ModulesException');
    $this->apiProxyMock->expectCall('modules', 'GetNumInstances', $req, $resp);

    $this->assertEquals(3, ModulesService::getNumInstances());
    $this->apiProxyMock->verify();
  }

  public function testSetNumInstances() {
    $req = new SetNumInstancesRequest();
    $resp = new SetNumInstancesResponse();

    $req->setInstances(3);

    $this->apiProxyMock->expectCall('modules', 'SetNumInstances', $req, $resp);

    ModulesService::setNumInstances(3);
    $this->apiProxyMock->verify();
  }

  public function testSetNumInstancesWithModuleAndVersion() {
    $req = new SetNumInstancesRequest();
    $resp = new SetNumInstancesResponse();

    $req->setInstances(3);

    $this->apiProxyMock->expectCall('modules', 'SetNumInstances', $req, $resp);

    ModulesService::setNumInstances(3);
    $this->apiProxyMock->verify();
  }

  public function testSetNumInstancesWithStringInstances() {
    $this->setExpectedException('\InvalidArgumentException',
      '$instances must be an integer. Actual type: string');
    ModulesService::setNumInstances('hello');
  }

  public function testSetNumInstancesWithIntegerModule() {
    $this->setExpectedException('\InvalidArgumentException',
      '$module must be a string. Actual type: integer');
    ModulesService::setNumInstances(5, 10);
  }

  public function testSetNumInstancesWithIntegerVersion() {
    $this->setExpectedException('\InvalidArgumentException',
      '$version must be a string. Actual type: integer');
    ModulesService::setNumInstances(5, 'module1', 5);
  }

  public function testSetNumInstancesInvalidVersion() {
    $req = new SetNumInstancesRequest();
    $resp = new ApplicationError(ErrorCode::INVALID_VERSION, 'invalid version');

    $req->setInstances(3);

    $this->setExpectedException(
        '\google\appengine\api\modules\ModulesException');
    $this->apiProxyMock->expectCall('modules', 'SetNumInstances', $req, $resp);

    ModulesService::setNumInstances(3);
    $this->apiProxyMock->verify();
  }

  public function testStartModule() {
    $req = new StartModuleRequest();
    $resp = new StartModuleResponse();

    $req->setModule('module1');
    $req->setVersion('v1');

    $this->apiProxyMock->expectCall('modules', 'StartModule', $req, $resp);

    ModulesService::startModule('module1', 'v1');
    $this->apiProxyMock->verify();
  }

  public function testStartModuleWithIntegerModule() {
    $this->setExpectedException('\InvalidArgumentException',
      '$module must be a string. Actual type: integer');
    ModulesService::startModule(5, 'v1');
  }

  public function testStartModuleWithIntegerVersion() {
    $this->setExpectedException('\InvalidArgumentException',
      '$version must be a string. Actual type: integer');
    ModulesService::startModule('module1', 5);
  }

  public function testStartModuleWithTransientError() {
    $req = new StartModuleRequest();
    $resp = new ApplicationError(ErrorCode::TRANSIENT_ERROR,
                                 'invalid version');

    $req->setModule('module1');
    $req->setVersion('v1');

    $this->setExpectedException(
        '\google\appengine\api\modules\TransientModulesException');
    $this->apiProxyMock->expectCall('modules', 'StartModule', $req, $resp);

    ModulesService::startModule('module1', 'v1');
    $this->apiProxyMock->verify();
  }

  public function testStopModule() {
    $req = new StopModuleRequest();
    $resp = new StopModuleResponse();

    $this->apiProxyMock->expectCall('modules', 'StopModule', $req, $resp);

    ModulesService::stopModule();
    $this->apiProxyMock->verify();
  }

  public function testStopModuleWithModuleAndVersion() {
    $req = new StopModuleRequest();
    $resp = new StopModuleResponse();

    $req->setModule('module1');
    $req->setVersion('v1');

    $this->apiProxyMock->expectCall('modules', 'StopModule', $req, $resp);

    ModulesService::stopModule('module1', 'v1');
    $this->apiProxyMock->verify();
  }

  public function testStopModuleWithIntegerModule() {
    $this->setExpectedException('\InvalidArgumentException',
      '$module must be a string. Actual type: integer');
    ModulesService::stopModule(5, 'v1');
  }

  public function testStopModuleWithIntegerVersion() {
    $this->setExpectedException('\InvalidArgumentException',
      '$version must be a string. Actual type: integer');
    ModulesService::stopModule('module1', 5);
  }

  public function testStopModuleWithTransientError() {
    $req = new StopModuleRequest();
    $resp = new ApplicationError(ErrorCode::TRANSIENT_ERROR,
                                 'invalid version');

    $req->setModule('module1');
    $req->setVersion('v1');

    $this->setExpectedException(
        '\google\appengine\api\modules\TransientModulesException');
    $this->apiProxyMock->expectCall('modules', 'StopModule', $req, $resp);

    ModulesService::stopModule('module1', 'v1');
    $this->apiProxyMock->verify();
  }

  public function testGetHostname() {
    $req = new GetHostnameRequest();
    $resp = new GetHostnameResponse();

    $resp->setHostname('hostname');

    $this->apiProxyMock->expectCall('modules', 'GetHostname', $req, $resp);

    $this->assertEquals('hostname', ModulesService::getHostname());
    $this->apiProxyMock->verify();
  }

  public function testGetHostnameWithModuleVersionAndIntegerInstance() {
    $req = new GetHostnameRequest();
    $resp = new GetHostnameResponse();

    $req->setModule('module1');
    $req->setVersion('v1');
    $req->setInstance('73');
    $resp->setHostname('hostname');

    $this->apiProxyMock->expectCall('modules', 'GetHostname', $req, $resp);

    $this->assertEquals('hostname',
                        ModulesService::getHostname('module1', 'v1', 73));
    $this->apiProxyMock->verify();
  }

  public function testGetHostnameWithModuleVersionAndStringInstance() {
    $req = new GetHostnameRequest();
    $resp = new GetHostnameResponse();

    $req->setModule('module1');
    $req->setVersion('v1');
    $req->setInstance('73');
    $resp->setHostname('hostname');

    $this->apiProxyMock->expectCall('modules', 'GetHostname', $req, $resp);

    $this->assertEquals('hostname',
                        ModulesService::getHostname('module1', 'v1', '73'));
    $this->apiProxyMock->verify();
  }

  public function testGetHostnameWithIntegerModule() {
    $this->setExpectedException('\InvalidArgumentException',
      '$module must be a string. Actual type: integer');
    ModulesService::getHostname(5);
  }

  public function testGetHostnameWithIntegerVersion() {
    $this->setExpectedException('\InvalidArgumentException',
      '$version must be a string. Actual type: integer');
    ModulesService::getHostname('module1', 5);
  }

  public function testGetHostnameWithArrayInstance() {
    $this->setExpectedException('\InvalidArgumentException',
      '$instance must be an integer or string. Actual type: array');
    ModulesService::getHostname('module1', 'v1', []);
  }

  public function testGetHostnameWithInvalidInstancesError() {
    $req = new GetHostnameRequest();
    $resp = new ApplicationError(ErrorCode::INVALID_INSTANCES,
                                 'invalid instances');

    $this->setExpectedException(
        '\google\appengine\api\modules\ModulesException');
    $this->apiProxyMock->expectCall('modules', 'GetHostname', $req, $resp);

    $this->assertEquals('hostname', ModulesService::getHostname());
    $this->apiProxyMock->verify();
  }
}
