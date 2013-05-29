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
 * Unit tests for the "memcached" PHP extension.
 *
 */

require_once 'google/appengine/api/memcache/memcache_service_pb.php';
require_once 'google/appengine/runtime/Memcached.php';
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

class MemcachedTest extends ApiProxyTestBase {

  public function setUp() {
    parent::setUp();
    $this->_SERVER = $_SERVER;
  }

  public function tearDown() {
    $_SERVER = $this->_SERVER;
    parent::tearDown();
  }

  public function testAddSuccess() {
    $memcached = new Memcached();

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
    $this->assertTrue($memcached->add("float", 2.0, 30));
    $this->apiProxyMock->verify();
  }

  public function testAddWithPrefixSuccess() {
    $memcached = new Memcached();
    $memcached->setOption(Memcached::OPT_PREFIX_KEY, "widgets_");

    $request = new MemcacheSetRequest();
    $item = $request->addItem();
    $item->setKey("widgets_float");
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
    $this->assertTrue($memcached->add("float", 2.0, 30));
    $this->assertEquals($memcached->getOption(Memcached::OPT_PREFIX_KEY),
                        "widgets_");
    $this->assertEquals($memcached->getResultCode(), Memcached::RES_SUCCESS);
    $this->assertEquals($memcached->getResultMessage(), "SUCCESS");
    $this->apiProxyMock->verify();
  }

  public function testAppend() {
    $request = new MemcacheGetRequest();
    $request->addKey("widgets_float");
    $request->setForCas(true);

    $response = new MemcacheGetResponse();
    $item = $response->addItem();
    $item->setKey("widgets_float");
    $item->setValue("bar");
    $item->setFlags(0);  // string.
    $item->setCasId(123456);

    $this->apiProxyMock->expectCall('memcache',
                                    'Get',
                                    $request,
                                    $response);

    $request = new MemcacheSetRequest();
    $item = $request->addItem();
    $item->setKey("widgets_float");
    $item->setValue("barfoo");
    $item->setFlags(0);  // string
    $item->setCasId(123456);
    $item->setSetPolicy(SetPolicy::CAS);
    $item->setExpirationTime(0);

    $response = new MemcacheSetResponse();
    $response->addSetStatus(SetStatusCode::STORED);

    $this->apiProxyMock->expectCall('memcache',
                                    'Set',
                                    $request,
                                    $response);
    $memcached = new Memcached();
    $memcached->setOption(Memcached::OPT_PREFIX_KEY, "widgets_");
    $this->assertTrue($memcached->append("float", "foo", 30));
    $this->assertEquals($memcached->getResultCode(), Memcached::RES_SUCCESS);
    $this->apiProxyMock->verify();
  }

  public function testAppendCasRaceFailed() {
    $request = new MemcacheGetRequest();
    $request->addKey("widgets_float");
    $request->setForCas(true);

    $response = new MemcacheGetResponse();
    $item = $response->addItem();
    $item->setKey("widgets_float");
    $item->setValue("bar");
    $item->setFlags(0);  // string.
    $item->setCasId(123456);

    $this->apiProxyMock->expectCall('memcache',
                                    'Get',
                                    $request,
                                    $response);

    $request = new MemcacheSetRequest();
    $item = $request->addItem();
    $item->setKey("widgets_float");
    $item->setValue("barfoo");
    $item->setFlags(0);  // string
    $item->setCasId(123456);
    $item->setSetPolicy(SetPolicy::CAS);
    $item->setExpirationTime(0);

    $response = new MemcacheSetResponse();
    $response->addSetStatus(SetStatusCode::EXISTS);

    $this->apiProxyMock->expectCall('memcache',
                                    'Set',
                                    $request,
                                    $response);

    $request = new MemcacheGetRequest();
    $request->addKey("widgets_float");
    $request->setForCas(true);

    $response = new MemcacheGetResponse();
    $item = $response->addItem();
    $item->setKey("widgets_float");
    $item->setValue("baz");
    $item->setFlags(0);  // string.
    $item->setCasId(1234567);

    $this->apiProxyMock->expectCall('memcache',
                                    'Get',
                                    $request,
                                    $response);

    $request = new MemcacheSetRequest();
    $item = $request->addItem();
    $item->setKey("widgets_float");
    $item->setValue("bazfoo");
    $item->setFlags(0);  // string
    $item->setCasId(1234567);
    $item->setSetPolicy(SetPolicy::CAS);
    $item->setExpirationTime(0);

    $response = new MemcacheSetResponse();
    $response->addSetStatus(SetStatusCode::STORED);

    $this->apiProxyMock->expectCall('memcache',
                                    'Set',
                                    $request,
                                    $response);

    $memcached = new Memcached();
    $memcached->setOption(Memcached::OPT_PREFIX_KEY, "widgets_");
    $this->assertTrue($memcached->append("float", "foo", 30));
    $this->assertEquals($memcached->getResultCode(), Memcached::RES_SUCCESS);
    $this->apiProxyMock->verify();
  }

  public function testGetSuccess() {
    $request = new MemcacheGetRequest();
    $request->addKey("widgets_key");

    $response = new MemcacheGetResponse();
    $item = $response->addItem();
    $item->setKey("widgets_key");
    $item->setValue("INF");
    $item->setFlags(6);  // float

    $this->apiProxyMock->expectCall('memcache',
                                    'Get',
                                    $request,
                                    $response);
    $memcached = new Memcached();
    $memcached->setOption(Memcached::OPT_PREFIX_KEY, "widgets_");
    $this->assertEquals(INF, $memcached->get("key"));
    $this->assertEquals($memcached->getResultCode(), Memcached::RES_SUCCESS);
    $this->apiProxyMock->verify();
  }

  public function testGetMultiSuccess() {
    $request = new MemcacheGetRequest();
    $request->addKey("key");
    $request->addKey("key1");
    $request->setForCas(true);

    $response = new MemcacheGetResponse();
    $item = $response->addItem();
    $item->setKey("key");
    $item->setValue("value");
    $item->setFlags(0);  // string.
    $item->setCasId(123456);

    $this->apiProxyMock->expectCall('memcache',
                                    'Get',
                                    $request,
                                    $response);
    $memcached = new Memcached();
    $keys = ["key", "key1"];
    $result = $memcached->getMulti($keys, $cas_tokens, Memcached::GET_PRESERVE_ORDER);
    $this->assertEquals("value", $result["key"]);
    $this->assertEquals(123456, $cas_tokens["key"]);
    $this->assertTrue(array_key_exists("key1", $result));
    $this->assertNull($result["key1"]);
    $this->assertTrue(array_key_exists("key1", $cas_tokens));
    $this->assertNull($cas_tokens["key1"]);
    $this->assertEquals($memcached->getResultCode(), Memcached::RES_SUCCESS);
    $this->apiProxyMock->verify();
  }

  public function testGetCasSuccess() {
    $request = new MemcacheGetRequest();
    $request->addKey("widgets_key");
    $request->setForCas(true);

    $response = new MemcacheGetResponse();
    $item = $response->addItem();
    $item->setKey("widgets_key");
    $item->setValue("value");
    $item->setFlags(0);  // string.
    $item->setCasId(123456);

    $this->apiProxyMock->expectCall('memcache',
                                    'Get',
                                    $request,
                                    $response);
    $memcached = new Memcached();
    $memcached->setOption(Memcached::OPT_PREFIX_KEY, "widgets_");
    $this->assertEquals("value", $memcached->get("key", null, $cas_id));
    $this->assertEquals($memcached->getResultCode(), Memcached::RES_SUCCESS);
    $this->assertEquals($cas_id, 123456);
    $this->apiProxyMock->verify();
  }

  public function testGetCasReadCacheSuccess() {
    $request = new MemcacheGetRequest();
    $request->addKey("widgets_key");
    $request->setForCas(true);

    $response = new MemcacheGetResponse();

    $this->apiProxyMock->expectCall('memcache',
                                    'Get',
                                    $request,
                                    $response);

    $request = new MemcacheSetRequest();
    $item = $request->addItem();
    $item->setKey("widgets_key");
    $item->setValue("cache_cb_value");
    $item->setFlags(0);  // string
    $item->setSetPolicy(SetPolicy::SET);
    $item->setExpirationTime(0);

    $response = new MemcacheSetResponse();
    $response->addSetStatus(SetStatusCode::STORED);
    $this->apiProxyMock->expectCall('memcache',
                                    'Set',
                                    $request,
                                    $response);

    $cache_cb = function($memcache, $key, &$value) {
      $value = 'cache_cb_value';
      return true;
    };

    $memcached = new Memcached();
    $memcached->setOption(Memcached::OPT_PREFIX_KEY, "widgets_");
    $cas_id = null;
    $this->assertEquals("cache_cb_value",
                        $memcached->get("key", $cache_cb, $cas_id));
    $this->assertEquals($memcached->getResultCode(), Memcached::RES_SUCCESS);
    $this->apiProxyMock->verify();
  }

  public function testGetMissing() {

    $request = new MemcacheGetRequest();
    $request->addKey("key");

    $response = new MemcacheGetResponse();

    $this->apiProxyMock->expectCall('memcache',
                                    'Get',
                                    $request,
                                    $response);
    $memcached = new Memcached();
    $this->assertFalse($memcached->get("key"));
    $this->assertEquals($memcached->getResultCode(), Memcached::RES_NOTFOUND);
    $this->apiProxyMock->verify();
  }

  public function testSetSuccess() {
    $request = new MemcacheSetRequest();
    $item = $request->addItem();
    $item->setKey("widgets_float");
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
    $memcached = new Memcached();
    $memcached->setOption(Memcached::OPT_PREFIX_KEY, "widgets_");
    $this->assertTrue($memcached->set("float", 2.0, 30));
    $this->assertEquals($memcached->getResultCode(), Memcached::RES_SUCCESS);
    $this->apiProxyMock->verify();
  }

  public function testSetMultiSuccess() {
    $request = new MemcacheSetRequest();
    $item = $request->addItem();
    $item->setKey("widgets_float");
    $item->setValue("2");
    $item->setFlags(6);  // float
    $item->setSetPolicy(SetPolicy::SET);
    $item->setExpirationTime(30);

    $item = $request->addItem();
    $item->setKey("widgets_str");
    $item->setValue("str_value");
    $item->setFlags(0);  // string
    $item->setSetPolicy(SetPolicy::SET);
    $item->setExpirationTime(30);

    $response = new MemcacheSetResponse();
    $response->addSetStatus(SetStatusCode::STORED);
    $response->addSetStatus(SetStatusCode::STORED);

    $this->apiProxyMock->expectCall('memcache',
                                    'Set',
                                    $request,
                                    $response);
    $memcached = new Memcached();
    $memcached->setOption(Memcached::OPT_PREFIX_KEY, "widgets_");
    $items = [ "float" => 2.0, "str" => "str_value" ];
    $this->assertTrue($memcached->setMulti($items, 30));
    $this->assertEquals($memcached->getResultCode(), Memcached::RES_SUCCESS);
    $this->apiProxyMock->verify();
  }

  public function testSetMultiFails() {
    $request = new MemcacheSetRequest();
    $item = $request->addItem();
    $item->setKey("widgets_float");
    $item->setValue("2");
    $item->setFlags(6);  // float
    $item->setSetPolicy(SetPolicy::SET);
    $item->setExpirationTime(30);

    $item = $request->addItem();
    $item->setKey("widgets_str");
    $item->setValue("str_value");
    $item->setFlags(0);  // string
    $item->setSetPolicy(SetPolicy::SET);
    $item->setExpirationTime(30);

    $response = new MemcacheSetResponse();
    $response->addSetStatus(SetStatusCode::STORED);
    $response->addSetStatus(SetStatusCode::NOT_STORED);

    $this->apiProxyMock->expectCall('memcache',
                                    'Set',
                                    $request,
                                    $response);
    $memcached = new Memcached();
    $memcached->setOption(Memcached::OPT_PREFIX_KEY, "widgets_");
    $items = [ "float" => 2.0, "str" => "str_value" ];
    $this->assertFalse($memcached->setMulti($items, 30));
    $this->assertEquals($memcached->getResultCode(), Memcached::RES_NOTSTORED);
    $this->apiProxyMock->verify();
  }

  public function testReplaceSuccess() {
    $request = new MemcacheSetRequest();
    $item = $request->addItem();
    $item->setKey("widgets_float");
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
    $memcached = new Memcached();
    $memcached->setOption(Memcached::OPT_PREFIX_KEY, "widgets_");
    $this->assertTrue($memcached->replace("float", 2.0, 30));
    $this->assertEquals($memcached->getResultCode(), Memcached::RES_SUCCESS);
    $this->apiProxyMock->verify();
  }

  public function testIncrementSuccess() {
    $request = new MemcacheIncrementRequest();
    $request->setKey("key");
    $request->setDelta(5);
    $request->setInitialValue(500);

    $response = new MemcacheIncrementResponse();
    $response->setNewValue(7);

    $this->apiProxyMock->expectCall('memcache',
                                    'Increment',
                                    $request,
                                    $response);
    $memcached = new Memcached();
    $this->assertEquals(7, $memcached->increment("key", 5, 500, 30));
    $this->apiProxyMock->verify();
  }

  public function testDecrementSuccess() {
    $request = new MemcacheIncrementRequest();
    $request->setKey("widgets_key");
    $request->setDelta(-5);
    $request->setInitialValue(500);

    $response = new MemcacheIncrementResponse();
    $response->setNewValue(7);

    $this->apiProxyMock->expectCall('memcache',
                                    'Increment',
                                    $request,
                                    $response);
    $memcached = new Memcached();
    $memcached->setOption(Memcached::OPT_PREFIX_KEY, "widgets_");
    $this->assertEquals(7, $memcached->decrement("key", 5, 500, 30));
    $this->assertEquals($memcached->getResultCode(), Memcached::RES_SUCCESS);
    $this->apiProxyMock->verify();
  }

  public function testPrependSuccess() {
    $request = new MemcacheGetRequest();
    $request->addKey("widgets_float");
    $request->setForCas(true);

    $response = new MemcacheGetResponse();
    $item = $response->addItem();
    $item->setKey("widgets_float");
    $item->setValue("bar");
    $item->setFlags(0);  // string.
    $item->setCasId(123456);

    $this->apiProxyMock->expectCall('memcache',
                                    'Get',
                                    $request,
                                    $response);

    $request = new MemcacheSetRequest();
    $item = $request->addItem();
    $item->setKey("widgets_float");
    $item->setValue("foobar");
    $item->setFlags(0);  // string
    $item->setCasId(123456);
    $item->setSetPolicy(SetPolicy::CAS);
    $item->setExpirationTime(0);

    $response = new MemcacheSetResponse();
    $response->addSetStatus(SetStatusCode::STORED);

    $this->apiProxyMock->expectCall('memcache',
                                    'Set',
                                    $request,
                                    $response);
    $memcached = new Memcached();
    $memcached->setOption(Memcached::OPT_PREFIX_KEY, "widgets_");
    $this->assertTrue($memcached->prepend("float", "foo", 30));
    $this->assertEquals($memcached->getResultCode(), Memcached::RES_SUCCESS);
    $this->apiProxyMock->verify();
  }

  public function testPrependCasRace() {
    $request = new MemcacheGetRequest();
    $request->addKey("widgets_float");
    $request->setForCas(true);

    $response = new MemcacheGetResponse();
    $item = $response->addItem();
    $item->setKey("widgets_float");
    $item->setValue("bar");
    $item->setFlags(0);  // string.
    $item->setCasId(123456);

    $this->apiProxyMock->expectCall('memcache',
                                    'Get',
                                    $request,
                                    $response);

    $request = new MemcacheSetRequest();
    $item = $request->addItem();
    $item->setKey("widgets_float");
    $item->setValue("foobar");
    $item->setFlags(0);  // string
    $item->setCasId(123456);
    $item->setSetPolicy(SetPolicy::CAS);
    $item->setExpirationTime(0);

    $response = new MemcacheSetResponse();
    $response->addSetStatus(SetStatusCode::EXISTS);

    $this->apiProxyMock->expectCall('memcache',
                                    'Set',
                                    $request,
                                    $response);

    $request = new MemcacheGetRequest();
    $request->addKey("widgets_float");
    $request->setForCas(true);

    $response = new MemcacheGetResponse();
    $item = $response->addItem();
    $item->setKey("widgets_float");
    $item->setValue("baz");
    $item->setFlags(0);  // string.
    $item->setCasId(1234567);

    $this->apiProxyMock->expectCall('memcache',
                                    'Get',
                                    $request,
                                    $response);

    $request = new MemcacheSetRequest();
    $item = $request->addItem();
    $item->setKey("widgets_float");
    $item->setValue("foobaz");
    $item->setFlags(0);  // string
    $item->setCasId(1234567);
    $item->setSetPolicy(SetPolicy::CAS);
    $item->setExpirationTime(0);

    $response = new MemcacheSetResponse();
    $response->addSetStatus(SetStatusCode::STORED);

    $this->apiProxyMock->expectCall('memcache',
                                    'Set',
                                    $request,
                                    $response);
    $memcached = new Memcached();
    $memcached->setOption(Memcached::OPT_PREFIX_KEY, "widgets_");
    $this->assertTrue($memcached->prepend("float", "foo", 30));
    $this->assertEquals($memcached->getResultCode(), Memcached::RES_SUCCESS);
    $this->apiProxyMock->verify();
  }

  public function testPrependGetFailed() {
    $request = new MemcacheGetRequest();
    $request->addKey("widgets_float");
    $request->setForCas(true);

    $response = new MemcacheGetResponse();

    $this->apiProxyMock->expectCall('memcache',
                                    'Get',
                                    $request,
                                    $response);

    $memcached = new Memcached();
    $memcached->setOption(Memcached::OPT_PREFIX_KEY, "widgets_");
    $this->assertFalse($memcached->prepend("float", "foo", 30));
    $this->assertEquals($memcached->getResultCode(), Memcached::RES_NOTSTORED);
    $this->apiProxyMock->verify();
  }

  public function testPrependReplaceFailed() {
    $request = new MemcacheGetRequest();
    $request->addKey("widgets_float");
    $request->setForCas(true);

    $response = new MemcacheGetResponse();
    $item = $response->addItem();
    $item->setKey("widgets_float");
    $item->setValue("bar");
    $item->setFlags(0);  // string.
    $item->setCasId(123456);

    $this->apiProxyMock->expectCall('memcache',
                                    'Get',
                                    $request,
                                    $response);

    $request = new MemcacheSetRequest();
    $item = $request->addItem();
    $item->setKey("widgets_float");
    $item->setValue("foobar");
    $item->setFlags(0);  // string
    $item->setCasId(123456);
    $item->setSetPolicy(SetPolicy::CAS);
    $item->setExpirationTime(0);

    $response = new MemcacheSetResponse();
    $response->addSetStatus(SetStatusCode::NOT_STORED);

    $this->apiProxyMock->expectCall('memcache',
                                    'Set',
                                    $request,
                                    $response);
    $memcached = new Memcached();
    $memcached->setOption(Memcached::OPT_PREFIX_KEY, "widgets_");
    $this->assertFalse($memcached->prepend("float", "foo", 30));
    $this->assertEquals($memcached->getResultCode(), Memcached::RES_NOTSTORED);
    $this->apiProxyMock->verify();
  }

  public function testCasSuccess() {
    $request = new MemcacheSetRequest();
    $item = $request->addItem();
    $item->setKey("widgets_float");
    $item->setValue("2");
    $item->setFlags(6);  // float
    $item->setCasId(12345);
    $item->setSetPolicy(SetPolicy::CAS);
    $item->setExpirationTime(30);

    $response = new MemcacheSetResponse();
    $response->addSetStatus(SetStatusCode::STORED);

    $this->apiProxyMock->expectCall('memcache',
                                    'Set',
                                    $request,
                                    $response);
    $memcached = new Memcached();
    $memcached->setOption(Memcached::OPT_PREFIX_KEY, "widgets_");
    $this->assertTrue($memcached->cas(12345, "float", 2.0, 30));
    $this->assertEquals($memcached->getResultCode(), Memcached::RES_SUCCESS);
    $this->apiProxyMock->verify();
  }

  public function testCasFailure() {
    $request = new MemcacheSetRequest();
    $item = $request->addItem();
    $item->setKey("widgets_float");
    $item->setValue("2");
    $item->setFlags(6);  // float
    $item->setCasId(12345);
    $item->setSetPolicy(SetPolicy::CAS);
    $item->setExpirationTime(30);

    $response = new MemcacheSetResponse();
    $response->addSetStatus(SetStatusCode::EXISTS);

    $this->apiProxyMock->expectCall('memcache',
                                    'Set',
                                    $request,
                                    $response);
    $memcached = new Memcached();
    $memcached->setOption(Memcached::OPT_PREFIX_KEY, "widgets_");
    $this->assertFalse($memcached->cas(12345, "float", 2.0, 30));
    $this->assertEquals($memcached->getResultCode(),
                        Memcached::RES_DATA_EXISTS);
    $this->apiProxyMock->verify();
  }

  public function testDeleteSuccess() {
    $request = new MemcacheDeleteRequest();
    $item = $request->addItem();
    $item->setKey("widgets_delete_key");
    $item->setDeleteTime(10);

    $response = new MemcacheDeleteResponse();
    $response->addDeleteStatus(DeleteStatusCode::DELETED);

    $this->apiProxyMock->expectCall('memcache',
                                    'Delete',
                                    $request,
                                    $response);
    $memcached = new Memcached();
    $memcached->setOption(Memcached::OPT_PREFIX_KEY, "widgets_");
    $this->assertTrue($memcached->delete("delete_key", 10));
    $this->assertEquals($memcached->getResultCode(), Memcached::RES_SUCCESS);
    $this->apiProxyMock->verify();
  }

  public function testDeleteNotThere() {
    $request = new MemcacheDeleteRequest();
    $item = $request->addItem();
    $item->setKey("widgets_delete_key");
    $item->setDeleteTime(10);

    $response = new MemcacheDeleteResponse();
    $response->addDeleteStatus(DeleteStatusCode::NOT_FOUND);

    $this->apiProxyMock->expectCall('memcache',
                                    'Delete',
                                    $request,
                                    $response);
    $memcached = new Memcached();
    $memcached->setOption(Memcached::OPT_PREFIX_KEY, "widgets_");
    $this->assertFalse($memcached->delete("delete_key", 10));
    $this->assertEquals($memcached->getResultCode(), Memcached::RES_NOTFOUND);
    $this->apiProxyMock->verify();
  }

  public function testFetchEmptyResults() {
    $memcached = new Memcached();
    $this->assertFalse($memcached->fetch());
  }

  public function testFetchAllEmptyResults() {
    $memcached = new Memcached();
    $this->assertFalse($memcached->fetchAll());
  }

  public function testGetDelayedSuccess() {
    $request = new MemcacheGetRequest();
    $request->addKey("key");
    $request->addKey("bar");
    $request->setForCas(true);

    $response = new MemcacheGetResponse();
    $item = $response->addItem();
    $item->setKey("key");
    $item->setValue("value");
    $item->setFlags(0);  // string.
    $item->setCasId(123456);

    $item = $response->addItem();
    $item->setKey("bar");
    $item->setValue("bar_value");
    $item->setFlags(0);  // string.
    $item->setCasId(2);

    $cb_count = 0;
    $cb = function($val) use (&$cb_count) {
      $cb_count++;
    };

    $this->apiProxyMock->expectCall('memcache',
                                    'Get',
                                    $request,
                                    $response);

    $memcached = new Memcached();
    $this->assertTrue($memcached->getDelayed(["key", "bar"], true, $cb));
    $this->assertEquals($memcached->getResultCode(), Memcached::RES_SUCCESS);
    $result = $memcached->fetch();
    $this->assertEquals($result["key"], "key");
    $this->assertEquals($result["value"], "value");
    $this->assertEquals($result["cas"], 123456);
    $result = $memcached->fetch();
    $this->assertEquals($result["key"], "bar");
    $this->assertEquals($result["value"], "bar_value");
    $this->assertEquals($result["cas"], 2);
    $this->assertFalse($memcached->fetch());
    $this->assertEquals($cb_count, 2);
    $this->apiProxyMock->verify();
  }

  public function testTouchSuccess() {
    $request = new MemcacheGetRequest();
    $request->addKey("key");
    $request->setForCas(true);

    $response = new MemcacheGetResponse();
    $item = $response->addItem();
    $item->setKey("key");
    $item->setValue("value");
    $item->setFlags(0);  // string.
    $item->setCasId(123456);

    $this->apiProxyMock->expectCall('memcache',
                                    'Get',
                                    $request,
                                    $response);

    $request = new MemcacheSetRequest();
    $item = $request->addItem();
    $item->setKey("key");
    $item->setValue("value");
    $item->setFlags(0);  // string
    $item->setCasId(123456);
    $item->setSetPolicy(SetPolicy::CAS);
    $item->setExpirationTime(999);

    $response = new MemcacheSetResponse();
    $response->addSetStatus(SetStatusCode::STORED);

    $this->apiProxyMock->expectCall('memcache',
                                    'Set',
                                    $request,
                                    $response);

    $memcached = new Memcached();
    $this->assertTrue($memcached->touch("key", 999));
    $this->apiProxyMock->verify();
  }

  public function testPassingNullKey() {
    $memcached = new Memcached();
    $this->assertFalse($memcached->add(null, 1));
    $this->assertFalse($memcached->replace(null, 1));
    $this->assertFalse($memcached->set(null, 1));
    $this->assertFalse($memcached->increment(null));
    $this->assertFalse($memcached->decrement(null));
  }
}
