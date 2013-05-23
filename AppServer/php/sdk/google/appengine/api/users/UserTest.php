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
 */

require_once 'google/appengine/api/users/User.php';
require_once 'google/appengine/api/users/UserService.php';
require_once 'google/appengine/testing/ApiProxyTestBase.php';

use google\appengine\api\users\User;
use google\appengine\api\users\UserService;
use google\appengine\testing\ApiProxyTestBase;
use \google\appengine\UserServiceError;

/**
 * Unittest for User class.
 */
class UserTest extends ApiProxyTestBase {
  public function setUp() {
    parent::setUp();
    putenv('AUTH_DOMAIN=gmail.com');
  }

  public function tearDown() {
    putenv('AUTH_DOMAIN');
    parent::tearDown();
  }

  public function testException() {
    $this->setExpectedException(
        '\google\appengine\api\users\UserNotFoundError');
    new User();
  }

  public function testGetFederatedIdentity() {
    $bill = new User(null, 'http://www.google.com/bill', null, '100001');

    $this->assertEquals(
        'http://www.google.com/bill', $bill->getFederatedIdentity());
    $this->assertEquals(null, $bill->getEmail());

    $bill = new User('bill@example.com', 'http://www.google.com/bill', null,
        '100001');

    $this->assertEquals(
        'http://www.google.com/bill', $bill->getFederatedIdentity());
    $this->assertEquals('bill@example.com', $bill->getEmail());
  }

  public function testGetNickname() {
    $jon = new User('jonmac@gmail.com', null, null, '11444');
    $this->assertEquals('jonmac', $jon->getNickname());

    $jon = new User('jonmac@example.com', null, null, '11555');
    $this->assertEquals('jonmac@example.com', $jon->getNickname());

    # nickname for federated user.
    putenv('AUTH_DOMAIN=example.com');
    $bill = new User(
        'bill@example.com', 'http://example.com/bill', null, '22772');
    putenv('AUTH_DOMAIN=gmail.com');
    $this->assertEquals('bill', $bill->getNickname());

    $bill = new User('bill@example.com', 'http://google.com/bill', null,
        '22772');
    $this->assertEquals('http://google.com/bill', $bill->getNickname());

    $bill = new User('bill@example.com', null, null, '22772');
    $this->assertEquals('bill@example.com', $bill->getNickname());

    $bill = new User('', 'http://google.com/bill', null, '22772');
    $this->assertEquals('http://google.com/bill', $bill->getNickname());

    $bill = new User(null, 'http://google.com/bill', null, '22772');
    $this->assertEquals('http://google.com/bill', $bill->getNickname());
  }

  public function testToString() {
    $bill = new User(
        'bill@example.com', 'http://google.com/bill', null, '22772');
    $this->assertEquals(
        "User(email='bill@example.com',federatedIdentity=" .
        "'http://google.com/bill',userId='22772')", (string)$bill);
  }
}
