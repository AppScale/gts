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

namespace google\appengine\api\mail;

require_once 'google/appengine/api/mail/BaseMessage.php';

use google\appengine\base\VoidProto;
use google\appengine\runtime\ApiProxy;
use google\appengine\runtime\ApplicationError;

class Message extends BaseMessage {
  /**
   * Adds a "bcc" address, or array of addresses, to the mail object.
   *
   * @param mixed $emails String email of individual recipient, or array of
   * emails of recipients
   * @throws InvalidArgumentException if any of the input emails are not
   * correctly formatted email addresses
   */
  public function addBcc($emails) {
    $email_array = $this->validEmailsArray($emails, "'bcc' recipient");
    foreach($email_array as $email) {
      $this->message->addBcc($email);
    }
  }

  /**
   * Adds a "cc" address, or array of addresses, to the mail object.
   *
   * @param mixed $emails String email of individual recipient, or array of
   * emails of recipients
   * @throws InvalidArgumentException if any of the input emails are not
   * correctly formatted email addresses
   */
  public function addCc($emails) {
    $email_array = $this->validEmailsArray($emails, "'cc' recipient");
    foreach($email_array as $email) {
      $this->message->addCc($email);
    }
  }

  /**
   * Adds a "to" address, or array of addresses, to the mail object.
   *
   * @param mixed $emails String email of individual recipient, or array of
   * emails of recipients
   * @throws InvalidArgumentException if any of the input emails are not
   * correctly formatted email addresses
   */
  public function addTo($emails) {
    $email_array = $this->validEmailsArray($emails, "'to' recipient");
    foreach($email_array as $email) {
      $this->message->addTo($email);
    }
  }

  /**
   * Clears all "bcc" addresses from the mail object.
   */
  public function clearBcc() {
    $this->message->clearBcc();
  }

  /**
   * Clears all "cc" addresses from the mail object.
   */
  public function clearCc() {
    $this->message->clearCc();
  }

  /**
   * Clear reply-to address from the mail object.
   */
  public function clearReplyTo() {
    $this->message->clearReplyto();
  }

  /**
   * Clears all "to" addresses from the mail object.
   */
  public function clearTo() {
    $this->message->clearTo();
  }

  /**
   * Returns the class variable $set_functions array, or the corresponding
   * value in that array if a key is provided.
   *
   * @param string $key Key to get corresponding value for
   * @return mixed $set_functions array, or a string value from that array
   */
  protected function getFunctionArray($key = null) {
    return self::$set_functions;
  }

  /**
   * Send the pre-formed email from the Message object.
   *
   * @throws InvalidArgumentException if a required field (sender, recipient
   * [to, cc or bcc], subject, body [plain or html]) is missing, or if an
   * ApplicationError was thrown by the RPC call due to an unauthorized
   * sender, an invalid attachment type, or an invalid header name
   * @throws RuntimeException If an ApplicationError was thrown by the RPC call
   * due to an internal error or bad request
   * @throws ApplicationError If there was an unknown error in the RPC call
   */
  public function send() {
    if (!$this->message->hasSender()) {
      throw new \InvalidArgumentException(
          "Required field sender is not provided.");
    } else if ($this->message->getToSize() == 0 &&
              $this->message->getCcSize() == 0 &&
              $this->message->getBccSize() == 0) {
      throw new \InvalidArgumentException(
          "Neither to, cc or bcc is set - at least one is required.");
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
          'mail', 'Send', $this->message, $response);
    } catch(ApplicationError $e) {
      $this->handleApplicationError($e);
    }
  }

  /**
   * Checks that an email input is either:
   * - An array, and each array member is a valid email
   * - A single valid email string
   * And subsequently returns an array of the valid emails.
   *
   * @param mixed $emails An array of emails string, or a single email string
   * @return An array of emails
   * @throws InvalidArgumentException if any of the input emails are not
   * correctly formatted email addresses
   */
  protected function validEmailsArray($email_list, $err_str) {
    if (is_string($email_list) && $this->checkValidEmail($email_list)) {
      return array($email_list);
    } else if (!is_array($email_list)) {
      $error = sprintf("Invalid %s: %s", $err_str, $email_list);
      throw new \InvalidArgumentException($error);
    } else {
      foreach($email_list as $email) {
        if (!$this->checkValidEmail($email)) {
          $error = sprintf("Invalid %s: %s", $err_str, $email);
          throw new \InvalidArgumentException($error);
        }
      }
      return $email_list;
    }
  }
}
