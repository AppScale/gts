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
 * Http Response Code Constants.
 *
 */

namespace google\appengine\ext\cloud_storage_streams;

/**
 * Declares well known HTTP response codes and associated error messages.
 */
final class HttpResponse {
  const OK = 200;
  const CREATED = 201;
  const NO_CONTENT = 204;
  const PARTIAL_CONTENT = 206;

  const RESUME_INCOMPLETE = 308;

  const FORBIDDEN = 403;
  const NOT_FOUND = 404;
  const REQUEST_TIMEOUT = 408;
  const PRECONDITION_FAILED = 412;
  const RANGE_NOT_SATISFIABLE = 416;

  const INTERNAL_SERVER_ERROR = 500;
  const BAD_GATEWAY = 502;
  const SERVICE_UNAVAILABLE = 503;
  const GATEWAY_TIMEOUT = 504;

  private static $status_messages = [
    self::OK => "OK",
    self::CREATED => "CREATE",
    self::NO_CONTENT => "NO CONTENT",
    self::PARTIAL_CONTENT => "PARTIAL CONTENT",
    self::RESUME_INCOMPLETE => "RESUME INCOMPLETE",
    self::FORBIDDEN => "FORBIDDEN",
    self::NOT_FOUND => "NOT FOUND",
    self::REQUEST_TIMEOUT => "REQUEST TIMEOUT",
    self::PRECONDITION_FAILED => "PRECONDITION FAILED",
    self::RANGE_NOT_SATISFIABLE => "RANGE NOT SATISFIABLE",
    self::INTERNAL_SERVER_ERROR => "INTERNAL SERVER ERROR",
  ];

  public static function getStatusMessage($code) {
    if (array_key_exists($code, self::$status_messages)) {
      return self::$status_messages[$code];
    }
    return sprintf("Unknown Code %d", $code);
  }
}

