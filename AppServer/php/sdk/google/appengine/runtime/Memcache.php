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
 * Interface for the "memcache" PHP extension.
 *
 * Implementation of the interface for the "memcache" PHP extension (see
 * http://php.net/manual/en/book.memcache.php) using the App Engine memcache
 * API).
 *
 * User provided "flags" arguments are currently ignored and many methods are
 * no-ops.
 */
use \google\appengine\MemcacheDeleteRequest;
use \google\appengine\MemcacheDeleteResponse;
use \google\appengine\MemcacheDeleteResponse\DeleteStatusCode;
use \google\appengine\MemcacheFlushRequest;
use \google\appengine\MemcacheFlushResponse;
use \google\appengine\MemcacheGetRequest;
use \google\appengine\MemcacheGetResponse;
use \google\appengine\MemcacheIncrementRequest;
use \google\appengine\MemcacheIncrementResponse;
use \google\appengine\MemcacheIncrementResponse\IncrementStatusCode;
use \google\appengine\MemcacheSetRequest;
use \google\appengine\MemcacheSetRequest\SetPolicy;
use \google\appengine\MemcacheSetResponse;
use \google\appengine\MemcacheSetResponse\SetStatusCode;
use \google\appengine\runtime\ApiProxy;
use \google\appengine\runtime\Error;
use \google\appengine\runtime\MemcacheUtils;

require_once 'google/appengine/api/memcache/memcache_service_pb.php';
require_once 'google/appengine/runtime/MemcacheUtils.php';
require_once 'google/appengine/runtime/ApiProxy.php';
require_once 'google/appengine/runtime/Error.php';

/**
 * Adds a new item to the cache. Will fail if the key is already present in the
 * cache.
 *
 * @param Memcache $memcache_obj The cache instance to add item to.
 *
 * @param string $key The key associated with the value added to the cache.
 *
 * @param mixed $value The value to add to the cache.
 *
 * @param int $flag This parameter is present only for compatibility and is
 *                  ignored.
 *
 * @param int $expire The delay before the item is removed from the cache. If
 *                    $expire <= 2592000 then it is interpreted as the number
 *                    of seconds from the time of the call to wait before
 *                    removing the item from the cache. If $expire > 2592000
 *                    then it is interpreted as the absolute Unix epoch time
 *                    when the value will expire.
 *
 * @return bool true if the item was successfully added to the cache, false
 *              otherwise.
 */
function memcache_add($memcache_obj, $key, $value, $flag = null, $expire = 0) {
  return $memcache_obj->add($key, $value, $flag, $expire);
}

/**
 * This function is present only for compatibility and does nothing.
 */
function memcache_add_server($memcache_obj, $host) {
  return $memcache_obj->addServer($host);
}

/**
 * This function is present only for compatibility and does nothing.
 */
function memcache_close($memcache_obj) {
  return $memcache_obj->close();
}

/**
 * This function is present only for compatibility and does nothing.
 */
function memcache_connect($host, $port = null, $timeout = 1) {
  $memcache_obj = new Memcache();
  if (!$memcache_obj->connect($host, $port, $timeout)) {
    return false;
  } else {
    return $memcache_obj;
  }
}

/**
 * Decrements a cached item's value. The value must be a int, float or string
 * representing an integer e.g. 5, 5.0 or "5" or the call with fail.
 *
 * @param Memcache $memcache_obj The cache instance to decrement the value in.
 *
 * @param string $key The key associated with the value to decrement.
 *
 * @param int $value The amount to decrement the value.
 *
 * @return mixed On success, the new value of the item is returned. On
 *               failure, false is returned.
 */
function memcache_decrement($memcache_obj, $key, $value = 1) {
  return $memcache_obj->decrement($key, $value);
}

/**
 * Deletes an item from the cache.
 *
 * @param Memcache $memcache_obj The cache instance to delete the item from.
 *
 * @param string $key The key associated with the item to delete.
 *
 * @return bool true if the item was successfully deleted from the cache,
 *              false otherwise. Note that this will return false if $key is
 *              not present in the cache.
 */
function memcache_delete($memcache_obj, $key) {
  return $memcache_obj->delete($key);
}

/**
 * Removes all items from cache.
 *
 * @param Memcache $memcache_obj The cache instance to flush.
 *
 * @return bool true if all items were removed, false otherwise.
 */
function memcache_flush($memcache_obj) {
  return $memcache_obj->flush();
}

/**
 * Fetches previously stored data from the cache.
 *
 * @param string|string[] $keys The key associated with the value to fetch, or
 *                              an array of keys if fetching multiple values.
 *
 * @param Memcache $memcache_obj The cache instance to get the item from.
 *
 * @param int $flags This parameter is present only for compatibility and is
 *                   ignored. It should return the stored flag value.
 *
 * @return mixed On success, the string associated with the key, or an array
 *               of key-value pairs when $keys is an array. On failure, false
 *               is returned.
 */
function memcache_get($memcache_obj, $keys, $flags = null) {
  return $memcache_obj->get($keys, $flags);
}

/**
 * Increments a cached item's value. The value must be a int, float or string
 * representing an integer e.g. 5, 5.0 or "5" or the call with fail.
 *
 * @param Memcache $memcache_obj The cache instance to increment the value in.
 *
 * @param string $key The key associated with the value to decrement.
 *
 * @param int $value The amount to increment the value.
 *
 * @return mixed On success, the new value of the item is returned. On
 *               failure, false is returned.
 */
function memcache_increment($memcache_obj, $key, $value = 1) {
  return $memcache_obj->increment($key, $value);
}

/**
 * This function is present only for compatibility and does nothing.
 */
function memcache_pconnect($memcache_obj, $host, $port = null, $timeout = 1) {
  $memcache_obj = new Memcache();
  if (!$memcache_obj->connect($host, $port, $timeout)) {
    return false;
  } else {
    return $memcache_obj;
  }
}

/**
 * Replaces an existing item in the cache. Will fail if the key is not already
 * present in the cache.
 *
 * @param Memcache $memcache_obj The cache instance to store the item in.
 *
 * @param string $key The key associated with the value that will be replaced in
 *                    the cache.
 *
 * @param mixed $value The new cache value.
 *
 * @param int $flag This parameter is present only for compatibility and is
 *                  ignored.
 *
 * @param int $expire The delay before the item is removed from the cache. If
 *                    $expire <= 2592000 then it is interpreted as the number
 *                    of seconds from the time of the call to wait before
 *                    removing the item from the cache. If $expire > 2592000
 *                    then it is interpreted as the absolute Unix epoch time
 *                    when the value will expire.
 *
 * @return bool true if the item was successfully replaced  in the cache,
 *              false otherwise.
 */
function memcache_replace($memcache_obj,
                          $key,
                          $value,
                          $flag = null,
                          $expire = 0) {
  return $memcache_obj->replace($key, $value, $flag, $expire);
}

/**
 * Sets the value of a key in the cache regardless of whether it is currently
 * present or not.
 *
 * @param Memcache $memcache_obj The cache instance to store the item in.
 *
 * @param string $key The key associated with the value that will be replaced in
 *                    the cache.
 *
 * @param mixed $value The new cache value.
 *
 * @param int $flag This parameter is present only for compatibility and is
 *                  ignored.
 *
 * @param int $expire The delay before the item is removed from the cache. If
 *                    $expire <= 2592000 then it is interpreted as the number
 *                    of seconds from the time of the call to wait before
 *                    removing the item from the cache. If $expire > 2592000
 *                    then it is interpreted as the absolute Unix epoch time
 *                    when the value will expire.
 *
 * @return bool true if the item was successfully replaced the cache, false
 *              otherwise.
 */
function memcache_set($memcache_obj, $key, $value, $flag = null, $expire = 0) {
  return $memcache_obj->set($key, $value, $flag, $expire);
}

/**
 * This function is present only for compatibility and does nothing.
 */
function memcache_set_compress_threshold($memcache_obj,
                                         $threshold,
                                         $min_savings = 0.2) {
  $memcache_obj->setCompressThreshold($threshold, $min_savings);
}

/**
 * An interface to the App Engine memory cache with an interface compatible with
 * the "memcache" PHP extension (see http://php.net/manual/en/book.memcache.php)
 *
 * All instances of this class use the same memory pool for their keys and
 * values.
 */
class Memcache {

  /**
   * Adds a new item to the cache. Will fail if the key is already present in
   * the cache.
   *
   * @param string $key The key associated with the value added to the cache.
   *
   * @param mixed $value The value to add to the cache.
   *
   * @param int $flag This parameter is present only for compatibility and is
   *                  ignored.
   *
   * @param int $expire The delay before the item is removed from the cache. If
   *                    $expire <= 2592000 then it is interpreted as the number
   *                    of seconds from the time of the call to wait before
   *                    removing the item from the cache. If $expire > 2592000
   *                    then it is interpreted as the absolute Unix epoch time
   *                    when the value will expire.
   *
   * @return bool true if the item was successfully added to the cache, false
   *              otherwise.
   */
  public function add($key, $value, $flag = null, $expire = 0) {
    // Sending of a key of 'null' or an unset value is a failure.
    if (is_null($key)) {
      return false;
    }

    try {
     $set_results = MemcacheUtils::setMultiWithPolicy(array($key => $value),
                                                      $expire,
                                                      SetPolicy::ADD);
    } catch (Error $e) {
      return false;
    }
    return $set_results[0] == SetStatusCode::STORED;
  }

  /**
   * This function is present only for compatibility and does nothing.
   */
  public function addServer($host) {
    return true;
  }

  /**
   * This function is present only for compatibility and does nothing.
   */
  public function close() {
    return true;
  }

  /**
   * This function is present only for compatibility and does nothing.
   */
  public function connect($host, $port = null, $timeout = 1) {
    return true;
  }

  /**
   * Decrements a cached item's value. The value must be a int, float or string
   * representing an integer e.g. 5, 5.0 or "5" or the call with fail.
   *
   * @param string $key The key associated with the value to decrement.
   *
   * @param int $value The amount to decrement the value.
   *
   * @return mixed On success, the new value of the item is returned. On
   *               failure, false is returned.
   */
  public function decrement($key, $value = 1) {
    return $this->increment($key, -$value);
  }

  /**
   * Deletes an item from the cache.
   *
   * @param string $key The key associated with the item to delete.
   *
   * @return bool true if the item was successfully deleted from the cache,
   *              false otherwise. Note that this will return false if $key is
   *              not present in the cache.
   */
  public function delete($key) {
    // Sending of a key of 'null' or an unset value is a failure.
    if (is_null($key)) {
      return false;
    }

    $request = new MemcacheDeleteRequest();
    $response = new MemcacheDeleteResponse();

    $request->addItem()->setKey($key);

    try {
      ApiProxy::makeSyncCall('memcache', 'Delete', $request, $response);
    } catch (Error $e) {
      return false;
    }
    $status_list = $response->getDeleteStatusList();
    return $status_list[0] == DeleteStatusCode::DELETED;
  }

  /**
   * Removes all items from cache.
   *
   * @return bool true if all items were removed, false otherwise.
   */
  public function flush() {
    $request = new MemcacheFlushRequest();
    $response = new MemcacheFlushResponse();

    try {
      ApiProxy::makeSyncCall('memcache', 'FlushAll', $request, $response);
    } catch (Error $e) {
      return false;
    }
    return true;
  }

  private function getMulti($keys, $flags = null) {
    $request = new MemcacheGetRequest();
    $response = new MemcacheGetResponse();

    foreach ($keys as $key) {
      $request->addKey($key);
    }

    ApiProxy::makeSyncCall('memcache', 'Get', $request, $response);

    $return_value = array();
    foreach ($response->getItemList() as $item) {
      $return_value[$item->getKey()] = MemcacheUtils::deserializeValue(
          $item->getValue(), $item->getFlags());
    }
    return $return_value;
  }

  /**
   * Fetches previously stored data from the cache.
   *
   * @param string|string[] $keys The key associated with the value to fetch, or
   *                              an array of keys if fetching multiple values.
   *
   * @param int $flags This parameter is present only for compatibility and is
   *                   ignored. It should return the stored flag value.
   *
   * @return mixed On success, the string associated with the key, or an array
   *               of key-value pairs when $keys is an array. On failure, false
   *               is returned.
   */
  public function get($keys, $flags = null) {
    if (is_array($keys)) {
      $return_value = $this->getMulti($keys, $flags);
      if (empty($return_value)) {
        return false;
      } else {
        return $return_value;
      }
    } else {
      try {
        $return_value = $this->getMulti(array($keys), array($flags));
      } catch (Error $e) {
        return false;
      }
      if (array_key_exists($keys, $return_value)) {
        return $return_value[$keys];
      } else {
        return false;
      }
    }
  }

  // Not implemented:
  // getExtendedStats
  // getServerStatus
  // getStats
  // getVersion

  /**
   * Increments a cached item's value. The value must be a int, float or string
   * representing an integer e.g. 5, 5.0 or "5" or the call with fail.
   *
   * @param string $key The key associated with the value to decrement.
   *
   * @param int $value The amount to increment the value.
   *
   * @return mixed On success, the new value of the item is returned. On
   *               failure, false is returned.
   */
  public function increment($key, $value = 1) {
    // Sending of a key of 'null' or an unset value is a failure.
    if (is_null($key)) {
      return false;
    }

    $request = new MemcacheIncrementRequest();
    $response = new MemcacheIncrementResponse();
    $request->setKey($key);
    $request->setDelta($value);

    try {
      ApiProxy::makeSyncCall('memcache', 'Increment', $request, $response);
    } catch (Exception $e) {
      return false;
    }
    if ($response->hasNewValue()) {
      return $response->getNewValue();
    } else {
      return false;
    }
  }

  /**
   * This function is present only for compatibility and does nothing.
   */
  public function pconnect($host, $port = null, $timeout = 1) {
    return true;
  }

  /**
   * Replaces an existing item in the cache. Will fail if the key is not already
   * present in the cache.
   *
   * @param string $key The key associated with the value that will be replaced
   *                    in the cache.
   *
   * @param mixed $value The new cache value.
   *
   * @param int $flag This parameter is present only for compatibility and is
   *                  ignored.
   *
   * @param int $expire The delay before the item is removed from the cache. If
   *                    $expire <= 2592000 then it is interpreted as the number
   *                    of seconds from the time of the call to wait before
   *                    removing the item from the cache. If $expire > 2592000
   *                    then it is interpreted as the absolute Unix epoch time
   *                    when the value will expire.
   *
   * @return bool true if the item was successfully replaced  in the cache,
   *              false otherwise.
   */
  public function replace($key, $value, $flag = null, $expire = 0) {
    // Sending of a key of 'null' or an unset value is a failure.
    if (is_null($key)) {
      return false;
    }

    try {
     $set_results = MemcacheUtils::setMultiWithPolicy(array($key => $value),
                                                      $expire,
                                                      SetPolicy::REPLACE);
    } catch (Error $e) {
      return false;
    }
    return $set_results[0] == SetStatusCode::STORED;
  }

  /**
   * Sets the value of a key in the cache regardless of whether it is currently
   * present or not.
   *
   * @param string $key The key associated with the value that will be replaced
   *                    in the cache.
   *
   * @param mixed $value The new cache value.
   *
   * @param int $flag This parameter is present only for compatibility and is
   *                  ignored.
   *
   * @param int $expire The delay before the item is removed from the cache. If
   *                    $expire <= 2592000 then it is interpreted as the number
   *                    of seconds from the time of the call to wait before
   *                    removing the item from the cache. If $expire > 2592000
   *                    then it is interpreted as the absolute Unix epoch time
   *                    when the value will expire.
   *
   * @return bool true if the item was successfully replaced the cache, false
   *              otherwise.
   */
  public function set($key, $value, $flag = null, $expire = 0) {
    // Sending of a key of 'null' or an unset value is a failure.
    if (is_null($key)) {
      return false;
    }

    try {
      $set_results = MemcacheUtils::setMultiWithPolicy(array($key => $value),
                                                       $expire,
                                                       SetPolicy::SET);
    } catch (Error $e) {
      return false;
    }
    return $set_results[0] == SetStatusCode::STORED;
  }

  /**
   * This function is present only for compatibility and does nothing.
   */
  public function setCompressThreshold($threshold, $min_savings = 0.2) {
    // Compression is not supported.
    return false;
  }

  // setServerParams not implemented.
}
