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
 * Implementation of the interface for the "memcached" PHP extension (see
 * http://php.net/manual/en/book.memcached.php) using the App Engine memcache
 * API).
 *
 * Methods that deal with adding/removing/list of memcache servers are no-ops.
 *
 */

use \google\appengine\MemcacheDeleteRequest;
use \google\appengine\MemcacheDeleteResponse;
use \google\appengine\MemcacheDeleteResponse\DeleteStatusCode;
use \google\appengine\MemcacheGetRequest;
use \google\appengine\MemcacheGetResponse;
use \google\appengine\MemcacheIncrementRequest;
use \google\appengine\MemcacheIncrementResponse;
use \google\appengine\MemcacheSetRequest;
use \google\appengine\MemcacheSetRequest\SetPolicy;
use \google\appengine\MemcacheSetResponse;
use \google\appengine\MemcacheSetResponse\SetStatusCode;
use \google\appengine\runtime\ApiProxy;
use \google\appengine\runtime\Error;
use \google\appengine\runtime\MemcacheUtils;

require_once 'google/appengine/api/memcache/memcache_service_pb.php';
require_once 'google/appengine/runtime/MemcacheUtils.php';
require_once 'google/appengine/runtime/Memcache.php';
require_once 'google/appengine/runtime/ApiProxy.php';
require_once 'google/appengine/runtime/Error.php';

class Memcached {

  /**
   * Constants taken from http://www.php.net/manual/en/memcached.constants.php
   */
  const OPT_PREFIX_KEY = 1;
  const OPT_COMPRESSION = 2;
  const OPT_HASH = 3;
  const OPT_DISTRIBUTION = 4;
  const OPT_BUFFER_WRITES = 5;
  const OPT_BINARY_PROTOCOL = 6;
  const OPT_NO_BLOCK = 7;
  const OPT_TCP_NODELAY = 8;
  const OPT_SOCKET_SEND_SIZE = 9;
  const OPT_SOCKET_RECV_SIZE = 10;
  const OPT_CONNECT_TIMEOUT = 11;
  const OPT_RETRY_TIMEOUT = 12;
  const OPT_SEND_TIMEOUT = 13;
  const OPT_RECV_TIMEOUT = 14;
  const OPT_POLL_TIMEOUT = 15;
  const OPT_CACHE_LOOKUPS = 16;
  const OPT_SERVER_FAILURE_LIMIT = 17;
  const OPT_SERIALIZER = 18;
  const HAVE_IGBINARY = 20;
  const HAVE_JSON = 21;

  // SERIALIZER constants
  const SERIALIZER_PHP = 100;
  const SERIALIZER_IGBINARY = 101;
  const SERIALIZER_JSON = 102;

  // HASH constants
  const HASH_DEFAULT = 200;
  const HASH_MD5 = 201;
  const HASH_CRC = 202;
  const HASH_FNV1_64 = 203;
  const HASH_FNV1A_64 = 204;
  const HASH_FNV1_32 = 205;
  const HASH_FNV1A_32 = 206;
  const HASH_HSIEH = 207;
  const HASH_MURMUR = 208;

  // DISTRIBUTION constants
  const DISTRIBUTION_MODULA = 300;
  const DISTRIBUTION_CONSISTENT = 301;
  const OPT_LIBKETAMA_COMPATIBLE = 302;

  const GET_PRESERVE_ORDER = 10;

  const RES_SUCCESS = 0;
  const RES_FAILURE = 1;
  const RES_HOST_LOOKUP_FAILURE = 2;
  const RES_UNKNOWN_READ_FAILURE = 7;
  const RES_PROTOCOL_ERROR = 8;
  const RES_CLIENT_ERROR = 9;
  const RES_SERVER_ERROR = 10;
  const RES_WRITE_FAILURE = 5;
  const RES_DATA_EXISTS = 12;
  const RES_NOTSTORED = 14;
  const RES_NOTFOUND = 16;
  const RES_PARTIAL_READ = 18;
  const RES_SOME_ERRORS = 19;
  const RES_NO_SERVERS = 20;
  const RES_END = 21;
  const RES_ERRNO = 26;
  const RES_BUFFERED = 32;
  const RES_TIMEOUT = 31;
  const RES_BAD_KEY_PROVIDED = 33;
  const RES_CONNECTION_SOCKET_CREATE_FAILURE = 11;
  const RES_PAYLOAD_FAILURE = -1001;

  private $result_code;
  private $memcache;
  private $options;
  private $delayed_results;

  public function __construct($persistent_id = null) {
    $this->result_code = self::RES_SUCCESS;
    $this->memcache = new Memcache();
    $this->options = [self::OPT_COMPRESSION => false];
    $this->delayed_results = array();
  }

  /**
   * add is similar to set(), but the operation fails if the key already exists
   * on the server.
   *
   * @see Memcached::set()
   *
   * @param string $key The key under which to store the value.
   * @param mixed $value The value to store.
   * @param int $expiration The expiration time, defaults to 0.
   *
   * @return bool true on success, false on failure.
   */
  public function add($key, $value, $expiration = 0) {
    $key = $this->getPrefixKey($key);
    $result = $this->memcache->add($key, $value, null, $expiration);
    $this->result_code = $result ? self::RES_SUCCESS : self::RES_NOTSTORED;
    return $result;
  }

  /**
   * Memcached::addByKey() is functionally equivalent to Memcached::add(),
   * except that the free-form server_key can be used to map the key to a
   * specific server. This is useful if you need to keep a bunch of related keys
   * on a certain server.
   *
   * @see Memcached::add()
   *
   * @param string $server_key This parameter is ignored.
   * @param string $key The key under which to store the value.
   * @param mixed $value The value to store.
   * @param int $expiration The expiration time, defaults to 0.
   *
   * @return bool true on success, false on failure.
   */
  public function addByKey($server_key,
                           $key,
                           $value,
                           $expiration = 0) {
    return $this->add($key, $value, $expiration);
  }

  /**
   * This function is present only for compatibility and does nothing.
   */
  public function addServer($host, $port, $weight = 0) {
    return true;
  }

  /**
   * This function is present only for compatibility and does nothing.
   */
  public function addServers($servers) {
    return true;
  }

  /**
   * Memcached::append() appends the given value string to the value of an
   * existing item. The reason that value is forced to be a string is that
   * appending mixed types is not well-defined.
   *
   * @param string $key The key under which to append the value.
   * @param string $value The value to append
   *
   * @result bool Returns true on success or false on failure.
   */
  public function append($key, $value) {
    do {
      $result = $this->get($key, null, $cas_token);
      if (!$result || !is_string($result)) {
        $this->result_code = self::RES_NOTSTORED;
        return false;
      }

      $result = $result . $value;
      $result = $this->cas($cas_token, $key, $result);
    } while (!$result && $this->result_code == self::RES_DATA_EXISTS);
    $this->result_code = $result ? self::RES_SUCCESS : self::RES_NOTSTORED;
    return $result;
  }

  /**
   * @see Memcached::append().
   *
   * @param string $server_key This parameter is ignored.
   * @param string $key The key under which to append the value.
   * @param string $value The value to append
   *
   * @result bool Returns true on success or false on failure.
   */
  public function appendByKey(string $server_key, string $key, string $value) {
    return $this->append($key, $value);
  }

  /**
   * Performs a set and check operation, so that the item will be stored only
   * if no other client has updated it since it was last fetched by this
   * client.
   *
   * @param mixed $cas_token Unique memcached assigned value.
   * @param string $key The key under which to store the value.
   * @param mixed $value The value to store.
   * @param int $expiration The expiration time, defaults to 0.
   *
   * @return bool True on success, or false on failure.
   */
  public function cas($cas_token, $key, $value, $expiration = 0) {
    $key = $this->getPrefixKey($key);
    $request = new MemcacheSetRequest();
    $response = new MemcacheSetResponse();

    $memcache_flag = 0;
    $serialized_value = MemcacheUtils::serializeValue($value, $memcache_flag);

    $item = $request->addItem();
    $item->setKey($key);
    $item->setValue($serialized_value);
    $item->setFlags($memcache_flag);
    $item->setSetPolicy(SetPolicy::CAS);
    $item->setCasId($cas_token);
    $item->setExpirationTime($expiration);

    try {
      ApiProxy::makeSyncCall('memcache', 'Set', $request, $response);
    } catch (Error $e) {
      $this->result_code = self::RES_FAILURE;
      return false;
    }

    switch ($response->getSetStatusList()[0]) {
      case SetStatusCode::STORED:
        $this->result_code = self::RES_SUCCESS;
        return true;
      case SetStatusCode::NOT_STORED:
        $this->result_code = self::RES_NOTSTORED;
        return false;
      case SetStatusCode::EXISTS:
        $this->result_code = self::RES_DATA_EXISTS;
        return false;
      default:
        $this->result_code = self::RES_FAILURE;
        return false;
    }
  }

  /**
   * @see Memcached::cas().
   *
   * @param mixed $cas_token Unique memcached assigned value.
   * @param string $server_key Ignored.
   * @param string $key The key under which to store the value.
   * @param mixed $value The value to store.
   * @param int $expiration The expiration time, defaults to 0.
   *
   * @return bool True on success, or false on failure.
   */
  public function casByKey($cas_token,
                           $server_key,
                           $key,
                           $value,
                           $expiration = 0) {
    return cas($cas_token, $key, $value, $expiration);
  }

  /**
   * Decrements a numeric item's value by $offset.
   *
   * @param string $key The key under which to store the value.
   * @param int $offset The amount by which to decrement the item's value.
   * @param int $initial_value The value to set the item to if it does not
   * currently exist.
   * @param int $expiration The expiration time, defaults to 0.
   *
   * @return bool True on success, or false on failure.
   */
  public function decrement($key,
                            $offset = 1,
                            $initial_value = 0,
                            $expiration = 0) {
    return $this->increment($key, -$offset, $initial_value, $expiration);
  }

  /**
   * @see Memcached::decrement().
   *
   * @param string $server_key This parameter is ignored.
   * @param string $key The key under which to store the value.
   * @param int $offset The amount by which to decrement the item's value.
   * @param int $initial_value The value to set the item to if it does not
   * currently exist.
   * @param int $expiration The expiration time, defaults to 0.
   *
   * @return bool True on success, or false on failure.
   */
  public function decrementByKey($server_key,
                                 $key,
                                 $offset = 1,
                                 $initial_value = 0,
                                 $expiration = 0) {
    return decrement($key, $offset, $initial_value, $expiration);
  }

  /**
   * deletes the $key from the server.
   *
   * @param string $key The key to delete from the server.
   * @param int $time The time parameter is the amount of time in seconds the
   * client wishes the server to refuse add and replace commands for this key.
   *
   * @return bool true on success or false on failure.
   */
  public function delete($key, $time = 0) {
    return $this->deleteMulti([$key], $time);
  }

  /**
   * @see Memcached::delete().
   *
   * @param string $server_key This parameter is ignored.
   * @param string $key The key to delete from the server.
   * @param int $time The time parameter is the amount of time in seconds the
   * client wishes the server to refuse add and replace commands for this key.
   *
   * @return bool true on success or false on failure.
   */
  public function deleteByKey($server_key, $key, $time = 0) {
    return $this->delete($key, $time);
  }

  /**
   * deletes an array of $keys from the server.
   *
   * @param array $keys The keys to delete from the server.
   * @param int $time The time parameter is the amount of time in seconds the
   * client wishes the server to refuse add and replace commands for this key.
   *
   * @return bool true on success or false on failure.
   */
  public function deleteMulti($keys, $time = 0) {
    $request = new MemcacheDeleteRequest();
    $response = new MemcacheDeleteResponse();

    foreach($keys as $key) {
      $key = $this->getPrefixKey($key);
      $item = $request->addItem();
      $item->setKey($key);
      $item->setDeleteTime($time);
    }

    try {
      ApiProxy::makeSyncCall('memcache', 'Delete', $request, $response);
    } catch (Error $e) {
      $this->result_code = self::RES_FAILURE;
      return false;
    }

    foreach($response->getDeleteStatusList() as $status) {
      if ($status == DeleteStatusCode::NOT_FOUND) {
        $this->result_code = self::RES_NOTFOUND;
        return false;
      }
    }

    $this->result_code = self::RES_SUCCESS;
    return true;
  }

  /**
   * @see Memcache::deleteMulti().
   *
   * @param string $server_key This parameter is ignored.
   * @param array $keys The keys to delete from the server.
   * @param int $time The time parameter is the amount of time in seconds the
   * client wishes the server to refuse add and replace commands for this key.
   *
   * @return bool true on success or false on failure.
   */
  public function deleteMultiByKey($server_key, $keys, $time = 0) {
    return $this->deleteMulti($keys, $time);
  }

  /**
   * fetch retrieves the next result from the last getDelayed() request.
   *
   * Note that currently getDelayed is a synchronous call.
   *
   * @return The next result, or false if there are no more results.
   */
  public function fetch() {
    if (!empty($this->delayed_results)) {
      return array_shift($this->delayed_results);
    } else {
      return false;
    }
  }

  /**
   * Fetch all of the remaining results from the last getDelayed() request.
   *
   * Note that currently getDelayed is a synchronous call.
   *
   * @return array The remaining results, or false if there are no results.
   */
  public function fetchAll() {
    if (!empty($this->delayed_results)) {
      $result = $this->delayed_results;
      $this->delayed_results = array();
      return $result;
    } else {
      return false;
    }
  }

  /**
   * Invalidates all existing cache items immediately.
   *
   * @param int $delay This parameter is ignored.
   *
   * @return bool true on success, or false on failure.
   */
  public function flush($delay = 0) {
    $result = $this->memcache->flush();
    $this->result_code = $result ? self::RES_SUCCESS : self::RES_NOTSTORED;
    return $result;
  }

  /**
   * Returns the item that was previously stored under the $key.
   *
   * @param string $key The key under which to store the value.
   * @param callable $cache_cb Read through caching callback.
   * @param mixed $cas_token The variable to store the CAS token in. This value
   * is opaque to the application.
   *
   * @return the value stored in the cache of false if there was a failure.
   */
  public function get($key, $cache_cb = null, &$cas_token = null) {
    // Not re-using getMulti to avoid messing with multiple result arrays for
    // cas tokens.
    $request = new MemcacheGetRequest();
    $response = new MemcacheGetResponse();

    $key = $this->getPrefixKey($key);
    $request->addKey($key);
    // Only way to check if we were passed a $cas_token is checking the number
    // of passed in arguments.
    if (func_num_args() == 3) {
      $request->setForCas(true);
    }

    try {
      ApiProxy::makeSyncCall('memcache', 'Get', $request, $response);
    } catch (Error $e) {
      $this->result_code = self::RES_FAILURE;
      return false;
    }

    $result = $response->getItemList();
    // If the get failed, and if a read through cache callback has been set
    // then call it now. $result is pass-by-ref and will contain the new value.
    if (empty($result) && !is_null($cache_cb) && is_null($cas_token)) {
      $cb_result = $cache_cb($this, $key, $new_result);
      if ($cb_result) {
        // TODO: What to do if this set fails?
        $this->memcache->set($key, $new_result);
        $this->result_code = self::RES_SUCCESS;
        return $new_result;
      } else {
        $this->result_code = self::RES_FAILURE;
        return false;
      }
    } else if (!empty($result)) {
      $item = $result[0];
      if ($item->hasCasId()) {
        $cas_token = $item->getCasId();
      }
      $this->result_code = self::RES_SUCCESS;
      return MemcacheUtils::deserializeValue($item->getValue(),
                                             $item->getFlags());
    } else {
      $this->result_code = self::RES_NOTFOUND;
      return false;
    }
  }

  /**
   * This function is present only for compatibility and does nothing.
   */
  public function getAllKeys() {
    return array();
  }

  /**
   * @see Memcache::get().
   *
   * @param string $server_key This parameter is ignored.
   * @param string $key The key under which to store the value.
   * @param callable $cache_cb Read through caching callback.
   * @param mixed $cas_token The variable to store the CAS token in. This value
   * is opaque to the application.
   *
   * @return the value stored in the cache of false if there was a failure.
   */
  public function getByKey($server_key, $key, $cache_cb, &$cas_token) {
    return $this->get($key, $cache_cb, $cas_token);
  }

  /**
   * Issues a request to memcache for multiple items the keys of which are
   * specified in the keys array.
   * Currently this method executes synchronously.
   *
   * @param array $keys Array of keys to retrieve.
   * @param bool $with_cas If true, retrieve the CAS tokens for the keys.
   * @param callable $value_cb The result callback.
   *
   * @return bool true on success, or false on failure.
   */
  public function getDelayed($keys, $with_cas=false, $value_cb=null) {
    // Clear any previous delayed results.
    $this->delayed_results = array();

    $cas_tokens = null;
    if ($with_cas) {
      $results = $this->getMulti($keys, $cas_tokens);
    } else {
      $results = $this->getMulti($keys);
    }

    if (!$results) {
      return false;
    }

    foreach($results as $key => $value) {
      $val = ['key' => $key, 'value' => $value];
      if (!empty($cas_tokens)) {
        $cas = array_shift($cas_tokens);
        $val['cas'] = $cas;
      }
      $this->delayed_results[] = $val;
    }

    if (isset($value_cb)) {
      foreach($this->delayed_results as $result) {
        $value_cb($result);
      }
    }

    return true;
  }

  /**
   * @see getDelayedByKey.
   *
   * @param string $server_key This parameter is ignored.
   * @param array $keys Array of keys to retrieve.
   * @param bool $with_cas If true, retrieve the CAS tokens for the keys.
   * @param callable $value_cb The result callback.
   *
   * @return bool true on success, or false on failure.
   */
  public function getDelayedByKey($server_key,
                                  $keys,
                                  $with_cas = false,
                                  $value_cb = null) {
    return $this->getDelayed($keys, $with_cas, $value_cb);
  }

  /**
   * Similar to Memcached::get(), but instead of a single key item, it retrieves
   * multiple items the keys of which are specified in the keys array.
   *
   * @see Memcached::get()
   *
   * @param array $keys Array of keys to retrieve.
   * @param array $cas_tokens The variable to store the CAS tokens for found
   * items.
   * @param int $flags The flags for the get operation.
   *
   * @return array The array of found items for false on failure.
   */
  public function getMulti($keys, &$cas_tokens = null, $flags = 0) {
    $request = new MemcacheGetRequest();
    $response = new MemcacheGetResponse();

    foreach ($keys as $key) {
      $key = $this->getPrefixKey($key);
      $request->addKey($key);
    }

    // Need to check the number of arguments passed to the function to see if
    // the user wants cas_tokens.
    if (func_num_args() > 1) {
      $request->setForCas(true);
    }

    try {
      ApiProxy::makeSyncCall('memcache', 'Get', $request, $response);
    } catch (Error $e) {
      $this->result_code = self::RES_FAILURE;
      return false;
    }

    $return_value = array();
    foreach ($response->getItemList() as $item) {
      $return_value[$item->getKey()] = MemcacheUtils::deserializeValue(
          $item->getValue(), $item->getFlags());
      if ($item->hasCasId()) {
        $cas_tokens[$item->getKey()] = $item->getCasId();
      }
    }
    // If GET_PRESERVE_ORDER was set then we need to ensure that
    // a. Keys are returned in the order that they we asked for.
    // b. If a key has no value then return null for that key.
    if ($flags == self::GET_PRESERVE_ORDER) {
      $ordered_result = [];
      $ordered_cas_tokens = [];
      foreach ($keys as $key) {
        if (array_key_exists($key, $return_value)) {
          $ordered_result[$key] = $return_value[$key];
          if (array_key_exists($key, $cas_tokens)) {
            $ordered_cas_tokens[$key] = $cas_tokens[$key];
          } else {
            $ordered_cas_tokens[$key] = null;
          }
        } else {
          $ordered_result[$key] = null;
          $ordered_cas_tokens[$key] = null;
        }
      }
      $return_value = $ordered_result;
      if (func_num_args() > 1) {
        $cas_tokens = $ordered_cas_tokens;
      }
    }
    return $return_value;
  }

  /**
   * @see Memcached::getMulti()
   *
   * @param string $server_key This parameter is ignored.
   * @param array $keys Array of keys to retrieve.
   * @param array $cas_tokens The variable to store the CAS tokens for found
   * items.
   * @param int $flags The flags for the get operation.
   *
   * @return array The array of found items for false on failure.
   */
  public function getMultiByKey($server_key,
                                $keys,
                                $with_cas = false,
                                $value_cb = null) {
    return $this->getMulti($keys, $with_cas, $value_cb);
  }

  /**
   * Retrieve a Memcached option value.
   *
   * @params int $option One of the Memcached::OPT_* constants.
   *
   * @return mixed the value of the requested option, of false on error.
   */
  public function getOption($option) {
    if (array_key_exists($option, $this->options)) {
      return $this->options[$option];
    }
    return false;
  }

  /**
   * Returns one of the Memcached::RES_* constants that is the result of the
   * last executed Memcached method.
   *
   * @return int The result code of the last memcached operation.
   */
  public function getResultCode() {
    return $this->result_code;
  }

  /**
   * Return the message describing the result of the last operation.
   *
   * @return string Message describing the result of the last operation.
   */
  public function getResultMessage() {
    // We're only handling the results that our code actually generates.
    switch ($this->result_code) {
      case self::RES_SUCCESS:
        return "SUCCESS";
      case self::RES_FAILURE:
        return "FAILURE";
      case self::RES_NOTSTORED:
        return "NOT STORED";
      case self::RES_NOT_FOUND:
        return "NOT FOUND";
    }
    return "UNKNOWN";
  }

  /**
   * This function is present only for compatibility and does nothing.
   */
  public function getServerByKey($server_key) {
    return false;
  }

  /**
   * This function is present only for compatibility and does nothing.
   */
  public function getServerList() {
    return [];
  }

  /**
   * This function is present only for compatibility and does nothing.
   */
  public function getStats() {
    return [];
  }

  /**
   * This function is present only for compatibility and does nothing.
   */
  public function getVersion() {
    return array();
  }

  /**
   * Increments a numeric item's value by the specified offset. If the item's
   * value is not numeric, and error will result.
   *
   * @param string $key The key of the item to increment
   * @param int $offset The amount by which to increment the item's value
   * @param int $initial_value The value to set the item to if it doesn't exist.
   * @param int $expiry The expiry time to set on the item.
   *
   * @return The new item's value on success or false on failure.
   */
  public function increment($key,
                            $offset = 1,
                            $initial_value = 0,
                            $expiry = 0) {
    // Sending of a key of 'null' or an unset value is a failure.
    if (is_null($key)) {
      return false;
    }

    $key = $this->getPrefixKey($key);
    $request = new MemcacheIncrementRequest();
    $response = new MemcacheIncrementResponse();
    $request->setKey($key);
    $request->setDelta($offset);
    $request->setInitialValue($initial_value);

    try {
      ApiProxy::makeSyncCall('memcache', 'Increment', $request, $response);
    } catch (Error $e) {
      $this->result_code = self::RES_FAILURE;
      return false;
    }
    if ($response->hasNewValue()) {
      $this->result_code = self::RES_SUCCESS;
      return $response->getNewValue();
    } else {
      $this->result_code = self::RES_NOTSTORED;
      return false;
    }
  }

  /**
   * @see Memcached::increment()
   *
   * @param string $server_key This parameter is ignored.
   * @param string $key The key of the item to increment
   * @param int $offset The amount by which to increment the item's value
   * @param int $initial_value The value to set the item to if it doesn't exist.
   * @param int $expiry The expiry time to set on the item.
   *
   * @return The new item's value on success or false on failure.
   */
  public function incrementByKey($server_key,
                                 $key,
                                 $offset = 1,
                                 $initial_value = 0,
                                 $expiry = 0) {
      return $this->increment($key, $offset, $initial_value, $expiry);
  }

  /**
   * This function is present only for compatibility and does nothing.
   */
  public function isPersistent() {
    return false;
  }

  /**
   * This function is present only for compatibility and does nothing.
   */
  public function isPristine() {
    return false;
  }

  /**
   * Prepends the given value string to an existing item.
   *
   * @param string $key The key under which to store the value.
   * @param string $value The string to prepend.
   *
   * @return true on success or false on failure.
   */
  public function prepend($key, $value) {
    do {
      $result = $this->get($key, null, $cas_token);
      if (!$result || !is_string($result)) {
        $this->result_code = self::RES_NOTSTORED;
        return false;
      }

      $result = $value . $result;
      $result = $this->cas($cas_token, $key, $result);
    } while (!$result && $this->result_code == self::RES_DATA_EXISTS);

    $this->result_code = $result ? self::RES_SUCCESS : self::RES_NOTSTORED;
    return $result;
  }

  /**
   * @see Memcached::prepend()
   *
   * @param string $server_key This parameter is ignored.
   * @param string $key The key under which to store the value.
   * @param string $value The string to prepend.
   *
   * @return true on success or false on failure.
   */
  public function prependByKey($server_key, $key, $value) {
    return $this->prepend($key, $value);
  }

  /**
   * This function is present only for compatibility and does nothing.
   */
  public function quit() {
    return false;
  }

  /**
   * Replace is similar to Memcache::set(), but the operation will fail if the
   * key is not found on the server.
   * 
   * @param string $key The key under which to store the value.
   * @param mixed $value The value to store.
   * @param int $expiration The expiration time, defaults to 0.
   *
   * @return true if the method succeeds, false on failure.
   */
  public function replace($key, $value, $expiration = 0) {
    $key = $this->getPrefixKey($key);
    $result = $this->memcache->replace($key, $value, null, $expiration);
    $this->result_code = $result ? self::RES_SUCCESS : self::RES_NOTSTORED;
    return $result;
  }

  /**
   * @see Memecached::replace()
   *
   * @param string $server_key This parameter is ignored.
   * @param string $key The key under which to store the value.
   * @param mixed $value The value to store.
   * @param int $expiration The expiration time, defaults to 0.
   *
   * @return true if the method succeeds, false on failure.
   */
  public function replaceByKey($server_key, $key, $value, $expiration = 0) {
    return $this->replace($key, $value, $expiration);
  }

  /**
   * This function is present only for compatibility and does nothing.
   */
  public function resetServerList() {
    return false;
  }

  /**
   * Stores the value on a memcache server under the specified key. The
   * expiration parameters can be used to control when the value is considered
   * expired.
   *
   * @param string $key The key under which to store the value.
   * @param mixed $value The value to store.
   * @param int $expiration The expiration time, defaults to 0.
   *
   * @return true if the method succeeds, false on failure.
   */
  public function set($key, $value, $expiration = 0) {
    $key = $this->getPrefixKey($key);
    $result = $this->memcache->set($key, $value, null, $expiration);
    $this->result_code = $result ? self::RES_SUCCESS : self::RES_FAILURE;
    return $result;
  }

  /**
   * @see Memcached::set()
   *
   * @param string $server_key This parameter is ignored.
   * @param string $key The key under which to store the value.
   * @param mixed $value The value to store.
   * @param int $expiration The expiration time, defaults to 0.
   *
   * @return true if the method succeeds, false on failure.
   */
  public function setByKey($server_key, $key, $value, $expiration = 0) {
    return $this->set($key, $value, $expiration);
  }

  /**
   * Is similar to Memcached::set(), but instead of a single key/value item, it
   * works on multiple items specified in items.
   *
   * @see Memcached::set()
   *
   * @param array $items An array of key value pairs to set.
   * @param int $expiration The expiration time to set for the value.
   *
   * returns bool true if the call succeeds, false otherwise.
   */
  public function setMulti($items, $expiration = 0) {
    if (array_key_exists(self::OPT_PREFIX_KEY, $this->options)) {
      $new_items = array();
      foreach($items as $key => $value) {
        $new_items[$this->getPrefixKey($key)] = $value;
      }
      $items = $new_items;
    }

    try {
      $set_results = MemcacheUtils::setMultiWithPolicy($items,
                                                       $expiration,
                                                       SetPolicy::SET);
    } catch (Exception $e) {
      $this->result_code = self::RES_FAILURE;
      return false;
    }

    // If any fail, report this method as failed.
    foreach($set_results as $result) {
      if ($result != SetStatusCode::STORED) {
        $this->result_code = self::RES_NOTSTORED;
        return false;
      }
    }

    $this->result_code = self::RES_SUCCESS;
    return true;
  }

  /**
   * @see Memcached::setMulti()
   *
   * @param string $server_key This parameter is ignored.
   * @param array $items An array of key value pairs to set.
   * @param int $expiration The expiration time to set for the value.
   *
   * @return bool true if the call succeeds, false otherwise.
   */
  public function setMultiByKey($server_key, $items, $expiration = 0) {
    return $this->setMulti($items, $expiration);
  }

  /**
   * This method sets the vaue of a memcached option.
   *
   * @param int $option The option to set.
   * @param mixed $value The value to set the option to.
   *
   * @return bool true if the call succeeds, false otherwise.
   */
  public function setOption($option, $value) {
    // The only option we allow to be changed is OPT_PREFIX_KEY
    if ($option == self::OPT_PREFIX_KEY) {
      $this->options[$option] = $value;
      return true;
    }
    return false;
  }

  /**
   * This is a varion of Memcached::setOption() that takes an array of options
   * to be set.
   *
   * @param mixed $options An associated array of options.
   *
   * @return bool true if the call succeeds, false otherwise.
   */
  public function setOptions($options) {
    $result = true;
    foreach($options as $option => $value) {
      $result |= $this->setOption($option, $value);
    }
    return $result;
  }

  /**
   * This function is present only for compatibility and does nothing.
   */
  public function setSaslAuthData($username, $password) {
  }

  /**
   * Sets a new expiration time on an item.
   *
   * @param string $key The key under which to append the value.
   * @param int $expiration The expiration time, defaults to 0.
   *
   * @return bool true on success or false on failure.
   */
  public function touch($key, $expiration = 0) {
    $result = $this->get($key, null, $cas_token);
    if ($result) {
      $result = $this->cas($cas_token, $key, $result, $expiration);
    }
    $this->result_code = $result ? self::RES_SUCCESS : self::RES_FAILURE;
    return $result;
  }

  /**
   * Functionally equivalent to Memcached::touch().
   *
   * @param string $server_key This parameter is ignored.
   * @param string $key The key under which to append the value.
   * @param int $expiration The expiration time, defaults to 0.
   *
   * @return bool true on success or false on failure.
   */
  public function touchByKey($server_key, $key, $expiration = 0) {
    return $this->touch($key, $expiration);
  }

  private function getPrefixKey($key) {
    if (array_key_exists(self::OPT_PREFIX_KEY, $this->options) && isset($key)) {
      $key = $this->options[self::OPT_PREFIX_KEY] . $key;
    }
    return $key;
  }
}
