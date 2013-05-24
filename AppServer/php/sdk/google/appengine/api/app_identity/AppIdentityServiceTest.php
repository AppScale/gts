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
 * PHP Unit tests for the AppIdentityService.
 *
 */

require_once 'google/appengine/api/app_identity/app_identity_service_pb.php';
require_once 'google/appengine/api/app_identity/AppIdentityService.php';
require_once 'google/appengine/testing/ApiProxyTestBase.php';

use \google\appengine\AppIdentityServiceError\ErrorCode;
use \google\appengine\api\app_identity\AppIdentityService;
use \google\appengine\testing\ApiProxyTestBase;

/**
 * Unittest for AppIdentityService class.
 */
class AppIdentityServiceTest extends ApiProxyTestBase {
  public function setUp() {
    parent::setUp();
    $this->_SERVER = $_SERVER;
  }

  public function testDown() {
    $_SERVER = $this->_SERVER;
    parent::tearDown();
  }

  public function testSignForApp() {
    $req = new \google\appengine\SignForAppRequest();
    $req->setBytesToSign('these are the bytes');

    $resp = new \google\appengine\SignForAppResponse();
    $resp->setSignatureBytes('signed bytes.');
    $resp->setKeyName('the key_name');

    $this->apiProxyMock->expectCall('app_identity_service',
                                    'SignForApp',
                                    $req,
                                    $resp);

    $sign_bytes = 'these are the bytes';
    $sign_result = AppIdentityService::signForApp($sign_bytes);
    $this->assertEquals($sign_result['key_name'], 'the key_name');
    $this->assertEquals($sign_result['signature'], 'signed bytes.');
    $this->apiProxyMock->verify();
  }

  public function testInvalidBytesToSign() {
    $this->setExpectedException('\InvalidArgumentException');
    $sign_result = AppIdentityService::signForApp(1.0);
  }

  public function testGetPublicCertificates() {
    $req = new \google\appengine\GetPublicCertificateForAppRequest();
    $resp = new \google\appengine\GetPublicCertificateForAppResponse();

    $cert = $resp->mutablePublicCertificateList(0);
    $cert->setKeyName('key1');
    $cert->setX509CertificatePem('cert1');
    $cert = $resp->mutablePublicCertificateList(1);
    $cert->setKeyName('key2');
    $cert->setX509CertificatePem('cert2');

    $this->apiProxyMock->expectCall('app_identity_service',
                                    'GetPublicCertificatesForApp',
                                    $req,
                                    $resp);

    $certs = AppIdentityService::getPublicCertificates();

    $cert = $certs[0];
    $this->assertEquals($cert->getCertificateName(), 'key1');
    $this->assertEquals($cert->getX509CertificateInPemFormat(), 'cert1');
    $cert = $certs[1];
    $this->assertEquals($cert->getCertificateName(), 'key2');
    $this->assertEquals($cert->getX509CertificateInPemFormat(), 'cert2');
    $this->apiProxyMock->verify();
  }

  public function testGetServiceAccountName() {
    $req = new \google\appengine\GetServiceAccountNameRequest();

    $service_account_result = 'foobar@gserviceaccount.google.com';
    $resp = new \google\appengine\GetServiceAccountNameResponse();
    $resp->setServiceAccountName($service_account_result);

    $this->apiProxyMock->expectCall('app_identity_service',
                                    'GetServiceAccountName',
                                    $req,
                                    $resp);

    $service_account = AppIdentityService::getServiceAccountName();
    $this->assertEquals($service_account, $service_account_result);
    $this->apiProxyMock->verify();
  }

  public function testGetAccessToken() {
    $req = new \google\appengine\GetAccessTokenRequest();

    $scope = 'mail.google.com/send';
    $req->addScope($scope);

    $resp = new \google\appengine\GetAccessTokenResponse();
    $resp->setAccessToken('foo token');
    $resp->setExpirationTime(12345);

    $this->apiProxyMock->expectCall('app_identity_service',
                                    'GetAccessToken',
                                    $req,
                                    $resp);

    $result = AppIdentityService::getAccessToken($scope);
    $this->assertEquals($result['access_token'], 'foo token');
    $this->assertEquals($result['expiration_time'], 12345);
    $this->apiProxyMock->verify();
  }

  public function testGetAccessTokenScopes() {
    $req = new \google\appengine\GetAccessTokenRequest();

    $scope1 = 'mail.google.com/send';
    $scope2 = 'google.cloud.scope/foo';
    $req->addScope($scope1);
    $req->addScope($scope2);

    $resp = new \google\appengine\GetAccessTokenResponse();
    $resp->setAccessToken('foo token');
    $resp->setExpirationTime(12345);

    $this->apiProxyMock->expectCall('app_identity_service',
                                    'GetAccessToken',
                                    $req,
                                    $resp);

    $result = AppIdentityService::getAccessToken([$scope1, $scope2]);
    $this->assertEquals($result['access_token'], 'foo token');
    $this->assertEquals($result['expiration_time'], 12345);
    $this->apiProxyMock->verify();
  }

  public function testGetAccessTokenInvalidScope() {
    $this->setExpectedException('\InvalidArgumentException');
    $sign_result = AppIdentityService::getAccessToken(1.0);
  }

  public function testGetAccessTokenInvalidScopeArray() {
    $this->setExpectedException('\InvalidArgumentException');
    $sign_result = AppIdentityService::getAccessToken(["foo", 1]);
  }

  public function testGetAccessTokenServiceInvalidScope() {
    $req = new \google\appengine\GetAccessTokenRequest();

    $scope = 'mail.google.com/invalid-scope';
    $req->addScope($scope);

    $exception = new \google\appengine\runtime\ApplicationError(
        ErrorCode::UNKNOWN_SCOPE, "unknown scope");

    $this->setExpectedException('\InvalidArgumentException',
                                'An unknown scope was supplied.');

    $this->apiProxyMock->expectCall('app_identity_service',
                                    'GetAccessToken',
                                    $req,
                                    $exception);

    $result = AppIdentityService::getAccessToken($scope);
  }

  public function testGetAccessTokenServiceNotAnnApp() {
    $req = new \google\appengine\GetAccessTokenRequest();

    $scope = 'mail.google.com/send';
    $req->addScope($scope);

    $exception = new \google\appengine\runtime\ApplicationError(
        ErrorCode::NOT_A_VALID_APP, "unknown scope");

    $this->setExpectedException(
      '\google\appengine\api\app_identity\AppIdentityException',
      'The application is not valid.');

    $this->apiProxyMock->expectCall('app_identity_service',
                                    'GetAccessToken',
                                    $req,
                                    $exception);

     $result = AppIdentityService::getAccessToken($scope);
  }

  public function testGetApplicationId() {
    putenv("APPLICATION_ID=simple-app-id");
    $this->assertEquals("simple-app-id",
                        AppIdentityService::getApplicationId());

    putenv("APPLICATION_ID=domain.com:domain-app-id");
    $this->assertEquals("domain.com:domain-app-id",
                        AppIdentityService::getApplicationId());

    putenv("APPLICATION_ID=part~partition-app-id");
    $this->assertEquals("partition-app-id",
                        AppIdentityService::getApplicationId());

    putenv("APPLICATION_ID=part~domain.com:display");
    $this->assertEquals("domain.com:display",
                        AppIdentityService::getApplicationId());

  }

  public function testGetDefaultVersionHostname() {
    putenv("DEFAULT_VERSION_HOSTNAME=my-app.appspot.com");
    $this->assertEquals("my-app.appspot.com",
                        AppIdentityService::getDefaultVersionHostname());
  }
}
