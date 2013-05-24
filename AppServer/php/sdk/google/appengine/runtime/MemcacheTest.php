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
 * Unit tests for the emulated "memcache" PHP extension.
 *
 */

require_once 'google/appengine/api/memcache/memcache_service_pb.php';
require_once 'google/appengine/runtime/Memcache.php';
require_once 'google/appengine/testing/ApiProxyTestBase.php';

use \google\appengine\MemcacheDeleteRequest;
use \google\appengine\MemcacheDeleteResponse;
use \google\appengine\MemcacheDeleteResponse\DeleteStatusCode;
use \google\appengine\MemcacheFlushRequest;
use \google\appengine\MemcacheFlushResponse;
use \google\appengine\MemcacheGetRequest;
use \google\appengine\MemcacheGetResponse;
use \google\appengine\MemcacheIncrementRequest;
use \google\appengine\MemcacheIncrementResponse;
use \google\appengine\MemcacheSetRequest;
use \google\appengine\MemcacheSetRequest\SetPolicy;
use \google\appengine\MemcacheSetResponse;
use \google\appengine\MemcacheSetResponse\SetStatusCode;
use \google\appengine\testing\ApiProxyTestBase;


class MemcacheTest extends ApiProxyTestBase {

  public function setUp() {
    parent::setUp();
    $this->_SERVER = $_SERVER;
  }

  public function tearDown() {
    $_SERVER = $this->_SERVER;
    parent::tearDown();
  }

  public function testAddSuccess() {
    $memcache = new Memcache();

    $request = new MemcacheSetRequest();
    $item = $request->addItem();
    $item->setKey("float");
    $item->setValue("2");
    $item->setFlags(6);  // float
    $item->setSetPolicy(SetPolicy::ADD);
    $item->setExpirationTime(30);

    $response = new MemcacheSetResponse();
    $response->addSetStatus(SetStatusCode::STORED);

    $this->apiProxyMock->expectCall('memcache',
                                    'Set',
                                    $request,
                                    $response);
    $this->assertTrue(memcache_add($memcache, "float", 2.0, null, 30));
    $this->apiProxyMock->verify();
  }

  public function testAddAlreadyThere() {
    $memcache = new Memcache();

    $request = new MemcacheSetRequest();
    $item = $request->addItem();
    $item->setKey("float");
    $item->setValue("2");
    $item->setFlags(6);   // float
    $item->setSetPolicy(SetPolicy::ADD);
    $item->setExpirationTime(30);

    $response = new MemcacheSetResponse();
    $response->addSetStatus(SetStatusCode::NOT_STORED);

    $this->apiProxyMock->expectCall('memcache',
                                    'Set',
                                    $request,
                                    $response);
    $this->assertFalse(memcache_add($memcache, "float", 2.0, null, 30));
    $this->apiProxyMock->verify();
  }

  public function testDeleteSuccess() {
    $memcache = new Memcache();

    $request = new MemcacheDeleteRequest();
    $item = $request->addItem();
    $item->setKey("delete_key");

    $response = new MemcacheDeleteResponse();
    $response->addDeleteStatus(DeleteStatusCode::DELETED);

    $this->apiProxyMock->expectCall('memcache',
                                    'Delete',
                                    $request,
                                    $response);
    $this->assertTrue(memcache_delete($memcache, "delete_key"));
    $this->apiProxyMock->verify();
  }

  public function testDeleteNotThere() {
    $memcache = new Memcache();

    $request = new MemcacheDeleteRequest();
    $item = $request->addItem();
    $item->setKey("delete_key");

    $response = new MemcacheDeleteResponse();
    $response->addDeleteStatus(DeleteStatusCode::NOT_FOUND);

    $this->apiProxyMock->expectCall('memcache',
                                    'Delete',
                                    $request,
                                    $response);
    $this->assertFalse(memcache_delete($memcache, "delete_key"));
    $this->apiProxyMock->verify();
  }

  public function testFlush() {
    $req = new MemcacheFlushRequest();
    $resp = new MemcacheFlushResponse();
    $memcache = new Memcache();

    $this->apiProxyMock->expectCall('memcache',
                                    'FlushAll',
                                    $req,
                                    $resp);
    memcache_flush($memcache);
    $this->apiProxyMock->verify();
  }

  public function testGetSuccess() {
    $memcache = new Memcache();

    $request = new MemcacheGetRequest();
    $request->addKey("key");

    $response = new MemcacheGetResponse();
    $item = $response->addItem();
    $item->setKey("key");
    $item->setValue("value");
    $item->setFlags(0);  // string.

    $this->apiProxyMock->expectCall('memcache',
                                    'Get',
                                    $request,
                                    $response);
    $this->assertEquals("value", memcache_get($memcache, "key"));
    $this->apiProxyMock->verify();
  }

  public function testGetMissing() {
    $memcache = new Memcache();

    $request = new MemcacheGetRequest();
    $request->addKey("key");

    $response = new MemcacheGetResponse();

    $this->apiProxyMock->expectCall('memcache',
                                    'Get',
                                    $request,
                                    $response);
    $this->assertFalse(memcache_get($memcache, "key"));
    $this->apiProxyMock->verify();
  }

  public function testGetMany() {
    $memcache = new Memcache();

    $request = new MemcacheGetRequest();
    $request->addKey("key1");
    $request->addKey("key2");
    $request->addKey("key3");

    $response = new MemcacheGetResponse();
    $item3 = $response->addItem();
    $item3->setKey("key3");
    $item3->setValue("value3");
    $item3->setFlags(0);  // string.
    $item1 = $response->addItem();
    $item1->setKey("key1");
    $item1->setValue("value1");
    $item1->setFlags(0);  // string.

    $this->apiProxyMock->expectCall('memcache',
                                    'Get',
                                    $request,
                                    $response);
    $this->assertEquals(array("key1" => "value1", "key3" => "value3"),
                        memcache_get($memcache, array("key1", "key2", "key3")));
    $this->apiProxyMock->verify();
  }

  public function testGetManyAllMissing() {
    $memcache = new Memcache();

    $request = new MemcacheGetRequest();
    $request->addKey("key1");
    $request->addKey("key2");
    $request->addKey("key3");

    $response = new MemcacheGetResponse();

    $this->apiProxyMock->expectCall('memcache',
                                    'Get',
                                    $request,
                                    $response);
    $this->assertFalse(memcache_get($memcache, array("key1", "key2", "key3")));
    $this->apiProxyMock->verify();
  }

  public function testIncrementSuccess() {
    $memcache = new Memcache();

    $request = new MemcacheIncrementRequest();
    $request->setKey("key");
    $request->setDelta(5);

    $response = new MemcacheIncrementResponse();
    $response->setNewValue(7);

    $this->apiProxyMock->expectCall('memcache',
                                    'Increment',
                                    $request,
                                    $response);
    $this->assertEquals(7, memcache_increment($memcache, "key", 5));
    $this->apiProxyMock->verify();
  }

  public function testIncrementNonExistingValue() {
    $memcache = new Memcache();

    $request = new MemcacheIncrementRequest();
    $request->setKey("key");
    $request->setDelta(5);

    $response = new MemcacheIncrementResponse();

    $this->apiProxyMock->expectCall('memcache',
                                    'Increment',
                                    $request,
                                    $response);
    $this->assertFalse(memcache_increment($memcache, "key", 5));
    $this->apiProxyMock->verify();
  }

  public function testReplaceSuccess() {
    $memcache = new Memcache();

    $request = new MemcacheSetRequest();
    $item = $request->addItem();
    $item->setKey("float");
    $item->setValue("2");
    $item->setFlags(6);  // float
    $item->setSetPolicy(SetPolicy::REPLACE);
    $item->setExpirationTime(30);

    $response = new MemcacheSetResponse();
    $response->addSetStatus(SetStatusCode::STORED);

    $this->apiProxyMock->expectCall('memcache',
                                    'Set',
                                    $request,
                                    $response);
    $this->assertTrue(memcache_replace($memcache, "float", 2.0, null, 30));
    $this->apiProxyMock->verify();
  }

  public function testReplaceNotThere() {
    $memcache = new Memcache();

    $request = new MemcacheSetRequest();
    $item = $request->addItem();
    $item->setKey("float");
    $item->setValue("2");
    $item->setFlags(6);  // float
    $item->setSetPolicy(SetPolicy::REPLACE);
    $item->setExpirationTime(30);

    $response = new MemcacheSetResponse();
    $response->addSetStatus(SetStatusCode::NOT_STORED);

    $this->apiProxyMock->expectCall('memcache',
                                    'Set',
                                    $request,
                                    $response);
    $this->assertFalse(memcache_replace($memcache, "float", 2.0, null, 30));
    $this->apiProxyMock->verify();
  }

  public function testSetSuccess() {
    $memcache = new Memcache();

    $request = new MemcacheSetRequest();
    $item = $request->addItem();
    $item->setKey("float");
    $item->setValue("2");
    $item->setFlags(6);  // float
    $item->setSetPolicy(SetPolicy::SET);
    $item->setExpirationTime(30);

    $response = new MemcacheSetResponse();
    $response->addSetStatus(SetStatusCode::STORED);

    $this->apiProxyMock->expectCall('memcache',
                                    'Set',
                                    $request,
                                    $response);
    $this->assertTrue(memcache_set($memcache, "float", 2.0, null, 30));
    $this->apiProxyMock->verify();
  }
}
