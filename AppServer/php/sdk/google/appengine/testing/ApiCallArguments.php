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
namespace google\appengine\testing;

class ApiCallArguments {
  public function __construct($package, $call_name, $req, $resp) {
    $this->package = $package;
    $this->call_name = $call_name;
    $this->req = $req;
    $this->resp = $resp;
  }

  public function isInputEqual($other) {
    if ($other === null) {
      return false;
    }

    return $this->package === $other->package
        && $this->call_name === $other->call_name
        && $this->req->equals($other->req);
  }

  public function toString() {
    return "Package: " . $this->package . "\n"
        . "Call: " . $this->call_name . "\n"
        . $this->req->shortDebugString();
  }
};

