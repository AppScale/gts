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

require_once 'google/appengine/runtime/Error.php';

/**
 * Thrown by APIProxy in the event of an application-level error.
 */
class ApplicationError extends Error {
  private $applicationError;

  public function __construct($applicationError, $errorDetail) {
    $this->applicationError = $applicationError;
    $this->message = $errorDetail;
  }

  public function getApplicationError() {
    return $this->applicationError;
  }
}
