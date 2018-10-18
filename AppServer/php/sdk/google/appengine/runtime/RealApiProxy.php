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

require_once 'google/appengine/runtime/ApplicationError.php';
require_once 'google/appengine/runtime/CapabilityDisabledError.php';
require_once 'google/appengine/runtime/FeatureNotEnabledError.php';

class RealApiProxy extends ApiProxyBase {
  // Specifying a value of -1.0 for the default deadline ensures that the
  // default for each package is used when making the call in the App Server.
  const DEFAULT_DEADLINE_VALUE = -1.0;
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
      $deadline = self::DEFAULT_DEADLINE_VALUE;
    }

    $result_array = array();

    \make_call($package,
               $call_name,
               $request->serializeToString(),
               $result_array,
               null,
               $deadline);

    $error_no = $result_array['error'];

    if ($error_no === ApiProxyBase::APPLICATION_ERROR) {
      throw new ApplicationError(
          $result_array['application_error'],
          $result_array['error_detail']);
    }

    if ($error_no === ApiProxyBase::CAPABILITY_DISABLED) {
      if (isset($result_array['error_detail'])) {
        $msg = $result_array['error_detail'];
      } else {
        $msg = sprintf('The API call %s.%s() is temporarily unavailable.',
            $package, $call_name);
      }
      throw new CapabilityDisabledError($msg);
    }

    if ($error_no === ApiProxyBase::FEATURE_DISABLED) {
      throw new FeatureNotEnabledError($result_array['error_detail']);
    }

    if (isset(ApiProxyBase::$exceptionLookupTable[$error_no])) {
      $res = ApiProxyBase::$exceptionLookupTable[$error_no];
      throw new $res[0](sprintf($res[1], $package, $call_name));
    }

    $response->parseFromString($result_array['result_string']);
  }
}
