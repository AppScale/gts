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
require_once 'google/appengine/runtime/Memcache.php';
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

  private function expectGetAccessTokenRequest($scopes, $cached,
      $exception = null) {
    $req = new \google\appengine\MemcacheGetRequest();
    $memcache_key = AppIdentityService::MEMCACHE_KEY_PREFIX .
        AppIdentityService::DOMAIN_SEPARATOR .
        implode(AppIdentityService::DOMAIN_SEPARATOR, $scopes);
    $req->addKey($memcache_key);
    $resp = new \google\appengine\MemcacheGetResponse();

    if ($cached) {
      $item = $resp->addItem();
      $item->setKey($memcache_key);
      $item->setValue(serialize([
          'access_token' => 'foo token',
          'expiration_time' => 12345,
      ]));
      $item->setFlags(
          \google\appengine\runtime\MemcacheUtils::TYPE_PHP_SERIALIZED);
    }

    $this->apiProxyMock->expectCall('memcache',
                                    'Get',
                                    $req,
                                    $resp);
    if ($cached) return;
    $req = new \google\appengine\GetAccessTokenRequest();
    foreach ($scopes as $scope) {
      $req->addScope($scope);
    }

    if (is_null($exception)) {
      $resp = new \google\appengine\GetAccessTokenResponse();
      $resp->setAccessToken('foo token');
      $resp->setExpirationTime(12345);
    } else {
      $resp = $exception;
    }

    $this->apiProxyMock->expectCall('app_identity_service',
                                    'GetAccessToken',
                                    $req,
                                    $resp);

    if (!is_null($exception)) return;

    $req = new \google\appengine\MemcacheSetRequest();
    $item = $req->addItem();
    $item->setKey($memcache_key);
    $item->setValue(serialize([
        'access_token' => $resp->getAccessToken(),
        'expiration_time' => $resp->getExpirationTime(),
    ]));
    $item->setExpirationTime($resp->getExpirationTime() - 300);
    $item->setFlags(
        \google\appengine\runtime\MemcacheUtils::TYPE_PHP_SERIALIZED);
    $item->setSetPolicy(1); // Add
    $resp = new \google\appengine\MemcacheSetResponse();
    $resp->addSetStatus(1); // Stored

    $this->apiProxyMock->expectCall('memcache',
                                    'Set',
                                    $req,
                                    $resp);
  }

  public function testGetAccessTokenCacheHit() {
    $scope = 'mail.google.com/send';

    self::expectGetAccessTokenRequest(array($scope), true);

    $result = AppIdentityService::getAccessToken($scope);

    $this->assertEquals($result['access_token'], 'foo token');
    $this->assertEquals($result['expiration_time'], 12345);
    $this->apiProxyMock->verify();
  }

  public function testGetAccessTokenCacheMiss() {
    $scope = 'mail.google.com/send';

    self::expectGetAccessTokenRequest(array($scope), false);

    $result = AppIdentityService::getAccessToken($scope);

    $this->assertEquals($result['access_token'], 'foo token');
    $this->assertEquals($result['expiration_time'], 12345);
    $this->apiProxyMock->verify();
  }

  public function testGetAccessTokenScopes() {
    $scope1 = 'mail.google.com/send';
    $scope2 = 'google.cloud.scope/foo';

    self::expectGetAccessTokenRequest(array($scope1, $scope2), false);

    $result = AppIdentityService::getAccessToken([$scope1, $scope2]);
    $this->assertEquals($result['access_token'], 'foo token');
    $this->assertEquals($result['expiration_time'], 12345);
    $this->apiProxyMock->verify();
  }

  public function testGetAccessTokenInvalidScope() {
    $this->setExpectedException('\InvalidArgumentException');
    $sign_result = AppIdentityService::getAccessToken(1.0);
  }

  private function expectMemcacheGetRequest($scopes) {
    $req = new \google\appengine\MemcacheGetRequest();
    $memcache_key = AppIdentityService::MEMCACHE_KEY_PREFIX .
        AppIdentityService::DOMAIN_SEPARATOR .
        implode(AppIdentityService::DOMAIN_SEPARATOR, $scopes);
    $req->addKey($memcache_key);
    $resp = new \google\appengine\MemcacheGetResponse();
    $this->apiProxyMock->expectCall('memcache',
                                    'Get',
                                    $req,
                                    $resp);
  }

  public function testGetAccessTokenInvalidScopeArray() {
    $scopes = ["foo", 1];
    self::expectMemcacheGetRequest($scopes);
    $this->setExpectedException('\InvalidArgumentException');
    $sign_result = AppIdentityService::getAccessToken($scopes);
  }

  public function testGetAccessTokenServiceInvalidScope() {
    $req = new \google\appengine\GetAccessTokenRequest();

    $scope = 'mail.google.com/invalid-scope';
    $req->addScope($scope);

    $exception = new \google\appengine\runtime\ApplicationError(
        ErrorCode::UNKNOWN_SCOPE, "unknown scope");

    $this->setExpectedException('\InvalidArgumentException',
                                'An unknown scope was supplied.');

    self::expectGetAccessTokenRequest(array($scope), false, $exception);

    $result = AppIdentityService::getAccessToken($scope);
  }
  public function testGetAccessTokenGaiaMintNotInitialized() {
    $this->executeServiceErrorTest(
        ErrorCode::GAIAMINT_NOT_INITIAILIZED,
        'There was a GAIA error using the AppIdentity service.');
  }

  public function testGetAccessTokenServiceNotAnnApp() {
    $this->executeServiceErrorTest(ErrorCode::NOT_A_VALID_APP,
                                   'The application is not valid.');
  }

  public function testGetAccessTokenServiceUnknownError() {
    $this->executeServiceErrorTest(
        ErrorCode::UNKNOWN_ERROR,
        'There was an unknown error using the AppIdentity service.');
  }

  public function testGetAccessTokenServiceNotAllowed() {
    $this->executeServiceErrorTest(ErrorCode::NOT_ALLOWED,
                                   'The call is not allowed.');
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

  private function executeServiceErrorTest($error, $expected_response) {
    $req = new \google\appengine\GetAccessTokenRequest();

    $scope = 'mail.google.com/invalid-scope';
    $req->addScope($scope);

    $exception = new \google\appengine\runtime\ApplicationError(
        $error, "not initialized");

    $this->setExpectedException(
        '\google\appengine\api\app_identity\AppIdentityException',
        $expected_response);

    self::expectGetAccessTokenRequest(array($scope), false, $exception);

    $result = AppIdentityService::getAccessToken($scope);
  }
}
