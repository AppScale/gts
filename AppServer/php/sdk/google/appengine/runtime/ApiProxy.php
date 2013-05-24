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
namespace google\appengine\runtime;

require_once 'google/appengine/runtime/RealApiProxy.php';

class ApiProxy {
  private static $apiProxy = null;

  /**
   * Makes a synchronous RPC call.
   * @param string $package Package to call
   * @param string $call_name Specific RPC call to make
   * @param string $request Request proto, serialised to string
   * @param string $response Response proto string to populate
   * @param double $deadline Optional deadline for the RPC call
   */
  public static function makeSyncCall(
      $package,
      $call_name,
      $request,
      $response,
      $deadline = null) {
    if (ApiProxy::$apiProxy === null) {
      ApiProxy::$apiProxy = new RealApiProxy();
    }
    ApiProxy::$apiProxy->makeSyncCall(
      $package, $call_name, $request, $response, $deadline);
  }

  /**
   * Set the API Proxy instance used to make the RPC call. Allows for mocking
   * in tests.
   * @param resource $apiProxy API Proxy instance to use
   */
  public static function setApiProxy($apiProxy) {
    ApiProxy::$apiProxy = $apiProxy;
  }
}
