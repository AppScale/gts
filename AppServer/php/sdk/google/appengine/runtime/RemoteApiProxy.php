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

require_once 'google/appengine/runtime/ApiProxyBase.php';
require_once 'google/appengine/ext/remote_api/remote_api_pb.php';

require_once 'google/appengine/runtime/CallNotFoundError.php';
require_once 'google/appengine/runtime/ArgumentError.php';
require_once 'google/appengine/runtime/DeadlineExceededError.php';
require_once 'google/appengine/runtime/CancelledError.php';
require_once 'google/appengine/runtime/ApplicationError.php';
require_once 'google/appengine/runtime/OverQuotaError.php';
require_once 'google/appengine/runtime/RequestTooLargeError.php';
require_once 'google/appengine/runtime/ResponseTooLargeError.php';
require_once 'google/appengine/runtime/CapabilityDisabledError.php';
require_once 'google/appengine/runtime/FeatureNotEnabledError.php';
require_once 'google/appengine/runtime/RPCFailedError.php';

use \google\appengine\ext\remote_api\Request;
use \google\appengine\ext\remote_api\Response;
use \google\appengine\runtime\RPCFailedError;

class RemoteApiProxy extends ApiProxyBase{

  private $apiPort = null;
  private $requestId = null;

  /**
   * Constructs an instance of RemoteApiProxy.
   * @param int $apiPort Port to use
   * @param string $requestId ID of the request
   */
  function __construct($apiPort, $requestId) {
    $this->apiPort = $apiPort;
    $this->requestId = $requestId;
  }

  /**
   * Makes a synchronous RPC call.
   * @param string $package Package to call
   * @param string $call_name Specific RPC call to make
   * @param string $request Request proto, serialised to string
   * @param string $response Response proto string to populate
   * @param double $deadline Optional deadline for the RPC call
   */
  public function makeSyncCall(
      $package,
      $call_name,
      $request,
      $response,
      $deadline = null) {

    if ($deadline === null) {
      $deadline = 5;
    }

    $remote_request = new Request();
    $remote_request->setServiceName($package);
    $remote_request->setMethod($call_name);
    $remote_request->setRequest($request->serializeToString());
    $remote_request->setRequestId($this->requestId);

    $serialized_remote_request = $remote_request->serializeToString();

    $opts = array(
      'http'=>array(
        'method'=>'POST',
        'header'=>
            "Content-type: application/octet-stream\r\n" .
            'Content-Length: ' . strlen($serialized_remote_request) . "\r\n",
        'content' => $serialized_remote_request
      )
    );

    $context = stream_context_create($opts);
    $serialized_remote_respone = file_get_contents(
        'http://localhost:' . $this->apiPort, false, $context);
    $remote_response = new Response();
    $remote_response->parseFromString($serialized_remote_respone);

    if ($remote_response->hasApplicationError()) {
      throw new ApplicationError(
          $remote_response->getApplicationError()->getCode(),
          $remote_response->getApplicationError()->getDetail());
    }

    if ($remote_response->hasException() ||
        $remote_response->hasJavaException()) {
      // This indicates a bug in the remote implementation.
      throw new RPCFailedError(sprintf('Remote implementation for %s.%s failed',
                                       $package,
                                       $call_name));
    }
    $response->parseFromString($remote_response->getResponse());
  }
}
