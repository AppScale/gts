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

require_once 'google/appengine/api/api_base_pb.php';
require_once 'google/appengine/runtime/ApiProxyBase.php';
require_once 'google/appengine/runtime/ApplicationError.php';
require_once 'google/appengine/runtime/ArgumentError.php';
require_once 'google/appengine/runtime/CallNotFoundError.php';
require_once 'google/appengine/runtime/CancelledError.php';
require_once 'google/appengine/runtime/CapabilityDisabledError.php';
require_once 'google/appengine/runtime/DeadlineExceededError.php';
require_once 'google/appengine/runtime/FeatureNotEnabledError.php';
require_once 'google/appengine/runtime/OverQuotaError.php';
require_once 'google/appengine/runtime/RealApiProxy.php';
require_once 'google/appengine/runtime/RequestTooLargeError.php';
require_once 'google/appengine/runtime/ResponseTooLargeError.php';
require_once 'google/appengine/runtime/RPCFailedError.php';

use google\appengine\base\VoidProto;
use google\appengine\runtime\ApiProxyBase;
use google\appengine\runtime\RealApiProxy;

/**
 * Mocked make_call function
 * Returns an error value as inserted at the $call_name value
 */
function make_call($package,
                   $call_name,
                   $request,
                   &$result_array,
                   $callback,
                   $deadline) {
  $result_array['error'] = $call_name;
  $result_array['application_error'] = 1;
  $result_array['error_detail'] = 'this is the error detail';
}

/**
 * Unittest for ApiProxy class.
 */
class ApiProxyTest extends \PHPUnit_Framework_TestCase {

  /**
   * Checks that an expected exception corresponds to a
   * given error value (via the ApiProxyBase lookup table).
   */
  public function throwsException($exception, $errorNumber) {
    $this->setExpectedException("google\\appengine\\runtime\\" . $exception);
    $realApiProxy = new RealApiProxy();
    $requestProto = new VoidProto();
    $responseProto = "";
    $resultArray = [];

    $realApiProxy->makeSyncCall('google.big',
                                $errorNumber,
                                $requestProto,
                                $resultArray,
                                $responseProto,
                                60);
  }

  /**
   * Tests for each exception/error value combination.
   */
  public function testRPCFailedError() {
    $this->throwsException('RPCFailedError', ApiProxyBase::RPC_FAILED);
  }

  public function testCallNotFoundError() {
    $this->throwsException('CallNotFoundError', ApiProxyBase::CALL_NOT_FOUND);
  }

  public function testArgumentError() {
    $this->throwsException('ArgumentError', ApiProxyBase::ARGUMENT_ERROR);
  }

  public function testDeadlineExceededError() {
    $this->throwsException('DeadlineExceededError',
                            ApiProxyBase::DEADLINE_EXCEEDED);
  }

  public function testCancelledError() {
    $this->throwsException('CancelledError', ApiProxyBase::CANCELLED);
  }

  public function testApplicationError() {
    $this->throwsException('ApplicationError', ApiProxyBase::APPLICATION_ERROR);
  }

  public function testError() {
    $this->throwsException('Error', ApiProxyBase::OTHER_ERROR);
  }

  public function testOverQuotaError() {
    $this->throwsException('OverQuotaError', ApiProxyBase::OVER_QUOTA);
  }

  public function testRequestTooLargeError() {
    $this->throwsException('RequestTooLargeError',
                            ApiProxyBase::REQUEST_TOO_LARGE);
  }

  public function testCapabilityDisabledError() {
    $this->throwsException('CapabilityDisabledError',
                            ApiProxyBase::CAPABILITY_DISABLED);
  }

  public function testFeatureNotEnabledError() {
    $this->throwsException('FeatureNotEnabledError',
                            ApiProxyBase::FEATURE_DISABLED);
  }

  public function testResponseTooLargeError() {
    $this->throwsException('ResponseTooLargeError',
                            ApiProxyBase::RESPONSE_TOO_LARGE);
  }
}
