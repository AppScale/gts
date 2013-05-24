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
 * Allow users to send mail using the App Engine mail APIs.
 *
 */

// Until we have a C extension for the devappserver2 environment, the mail
// function will be defined. Make sure we do not generate an error trying to
// redefine the function.
if (!function_exists("mail")) {

/**
 * Mail stub function - provided so that scripts do not crash when running
 * on the production server when they attempt to send mail, as the function is
 * not defined.
 */
function mail($to,
              $subject,
              $message,
              $additional_headers = null,
              $additional_parameters = null) {
  syslog(LOG_WARNING, "The function 'mail' is not implemented.");
  return false;
}

}  // !function_exists("mail")
