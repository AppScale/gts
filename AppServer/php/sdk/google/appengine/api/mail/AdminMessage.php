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

namespace google\appengine\api\mail;

require_once 'google/appengine/api/mail/BaseMessage.php';

use google\appengine\base\VoidProto;
use google\appengine\runtime\ApiProxy;
use google\appengine\runtime\ApplicationError;

/**
 * Allows users to send mail to application admins using the App Engine mail
 * APIs.
 */
final class AdminMessage extends BaseMessage {
  // Setter functions allowed for Message, but disallowed for AdminMessage.
  private static $disallowed_functions = array('addTo', 'addCc', 'addBcc');

  /**
   * Returns the class variable $set_functions array, or the corresponding
   * value in that array if a key is provided.
   *
   * @param string $key Key to get corresponding value for.
   * @return mixed $set_functions array, or a string value from that array.
   */
  protected function getFunctionArray($key = null) {
    $allowed_functions = array_diff(self::$set_functions,
                                    self::$disallowed_functions);
    return $allowed_functions;
  }

  /**
   * Send the pre-formed email from the Message object to application admins.
   *
   * @throws \InvalidArgumentException If a required field (sender, recipient
   * [to, cc or bcc], subject, body [plain or html]) is missing, or if an
   * ApplicationError was thrown by the RPC call due to an unauthorized
   * sender, an invalid attachment type, or an invalid header name.
   * @throws \RuntimeException If an ApplicationError was thrown by the RPC call
   * due to an internal error or bad request.
   * @throws ApplicationError If there was an unknown error in the RPC call.
   */
  public function send() {
    if (!$this->message->hasSender()) {
      throw new \InvalidArgumentException(
          "Required field sender is not provided.");
    } else if (!$this->message->hasSubject()) {
      throw new \InvalidArgumentException(
          "Required field subject is not provided.");
    } else if (!$this->message->hasTextbody() &&
              !$this->message->hasHtmlbody()) {
      throw new \InvalidArgumentException(
          "Neither a plain-text nor HTML body is provided - at least one is " .
          "required.");
    }

    $response = new VoidProto();
    try {
      ApiProxy::makeSyncCall(
          'mail', 'SendToAdmins', $this->message, $response);
    } catch(ApplicationError $e) {
      $this->handleApplicationError($e);
    }
  }
}
