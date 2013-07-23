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
 * Tests for Mail API on App Engine.
 *
 */

require_once 'google/appengine/api/mail_service_pb.php';
require_once 'google/appengine/api/mail/Message.php';
require_once 'google/appengine/runtime/ApplicationError.php';
require_once 'google/appengine/testing/ApiProxyTestBase.php';

use google\appengine\base\VoidProto;
use google\appengine\api\mail\Message;
use google\appengine\MailMessage;
use google\appengine\MailServiceError\ErrorCode;
use google\appengine\runtime\ApplicationError;
use google\appengine\testing\ApiProxyTestBase;

class MessageTest extends ApiProxyTestBase {
  public function testConstructorBadValues() {
    $options = array("fakeSet" => "test");
    $this->setExpectedException(
        "InvalidArgumentException",
        "Message received an invalid option: fakeSet");
    $message = new Message($options);
  }

  public function testConstructNonString() {
    $options = "test";
    $this->setExpectedException(
        "InvalidArgumentException", "Message expects an array, not string");
    $message = new Message($options);
  }

  public function testAddAttachmentError() {
    $message = new Message();
    $this->setExpectedException(
        "InvalidArgumentException", "'exe' is a blacklisted file extension.");
    $message->addAttachment("file.exe", "data");
  }

  private function setupAttachmentTest($input) {
    $message = new Message();
    $error_message = "";

    try {
      $message->addAttachmentArray($input);
    } catch(InvalidArgumentException $e) {
      $error_message = $e->getMessage();
    }

    return $error_message;
  }

  public function testAddAttachmentArrayError() {
    $this->assertEquals(
        $this->setupAttachmentTest("string"),
        "Input is not an array (Actual type: string).");

    $attach_arr = array("data.gif" => "data",
                        "data.exe" => "data");
    $this->assertEquals(
        $this->setupAttachmentTest($attach_arr),
        "'exe' is a blacklisted file extension.");
  }

  private function setupValidEmailTest($email_input) {
    $message = new Message();
    $error_message = "";

    try {
      $message->addTo($email_input);
    } catch(InvalidArgumentException $e) {
      $error_message = $e->getMessage();
    }

    return $error_message;
  }

  public function testCheckValidEmails() {
    $this->assertEquals($this->setupValidEmailTest("invalid.email"),
                        "Invalid 'to' recipient: invalid.email");

    $array_emails = array("test@test.com", "invalid.email");
    $this->assertEquals($this->setupValidEmailTest($array_emails),
                        "Invalid 'to' recipient: invalid.email");
  }

  public function testAddHeaderNonWhitelisted() {
    $message = new Message();
    $this->setExpectedException(
        "InvalidArgumentException",
        "Input header 'invalid-header: data' is not whitelisted for use with" .
        " the Google App Engine Mail Service.");
    $message->addHeader("invalid-header", "data");
  }

  public function testAddHeaderWrongKeyType() {
    $message = new Message();
    $this->setExpectedException(
        "InvalidArgumentException",
        "Header key is not a string (Actual type: array).");
    $message->addHeader(array("not-string"), "data");
  }

  public function testAddHeaderArray() {
    $message = new Message();
    $this->setExpectedException(
        "InvalidArgumentException",
        "Input is not an array (Actual type: string).");
    $message->addHeaderArray("string");
  }

  public function testSetHtmlBody() {
    $message = new Message();
    $this->setExpectedException(
        "InvalidArgumentException",
        "HTML text given is not a string (Actual type: array).");
    $message->setHtmlBody(array("text"));
  }

  public function testSetReplyTo() {
    $message = new Message();
    $this->setExpectedException(
        "InvalidArgumentException", "Invalid reply-to: invalid.email");
    $message->setReplyTo("invalid.email");
  }

  public function testSetSender() {
    $message = new Message();
    $this->setExpectedException(
        "InvalidArgumentException", "Invalid sender: invalid.email");
    $message->setSender("invalid.email");
  }

  public function testSetSubject() {
    $message = new Message();
    $this->setExpectedException(
        "InvalidArgumentException",
        "Subject given is not a string (Actual type: array).");
    $message->setSubject(array("test"));
  }

  public function testSetTextBody() {
    $message = new Message();
    $this->setExpectedException(
        "InvalidArgumentException",
        "Plain text given is not a string (Actual type: array).");
    $message->setTextBody(array("text"));
  }

  public function testSendNoSender() {
    $message = new Message();
    $this->setExpectedException(
        "InvalidArgumentException", "Required field sender is not provided.");
    $message->send();
  }

  public function testSendNoRecipient() {
    $message = new Message();
    $this->setExpectedException(
        "InvalidArgumentException",
        "Neither to, cc or bcc is set - at least one is required.");
    $message->setSender("test@example.com");
    $message->send();
  }

  public function testSendNoSubject() {
    $message = new Message();
    $this->setExpectedException(
        "InvalidArgumentException",
        "Required field subject is not provided.");
    $message->setSender("test@example.com");
    $message->addTo("example@test.com");
    $message->send();
  }

  public function testSendNoBody() {
    $message = new Message();
    $this->setExpectedException(
        "InvalidArgumentException",
        "Neither a plain-text nor HTML body is provided - at least one is " .
        "required.");
    $message->setSender("test@example.com");
    $message->addTo("example@test.com");
    $message->setSubject("test");
    $message->send();
  }

  /**
   * Setup a basic message and message proto with:
   * - sender
   * - to
   * - subject
   * - text body
   */
  private function setupMessageSimple($message, $message_proto) {
    $message->setSender("test@example.com");
    $message_proto->setSender("test@example.com");

    $message->addTo("example@test.com");
    $message_proto->addTo("example@test.com");

    $message->setSubject("test");
    $message_proto->setSubject("test");

    $message->setTextBody("text body");
    $message_proto->setTextbody("text body");
  }

  /**
   * Tests various message elements:
   * - everything in setupMessageSimple()
   * - to (array)
   * - bcc, bcc (array)
   * - cc, cc (array)
   * - html body
   * - reply to
   */
  public function testSucceedFields() {
    $message = new Message();
    $message_proto = new MailMessage();
    $this->setupMessageSimple($message, $message_proto);

    $message->addTo(array("b@test.com", "c@test.com"));
    $message_proto->addTo("b@test.com");
    $message_proto->addTo("c@test.com");

    $message->addBcc("a@example.com");
    $message_proto->addBcc("a@example.com");

    $message->addBcc(array("b@example.com", "c@example.com"));
    $message_proto->addBcc("b@example.com");
    $message_proto->addBcc("c@example.com");

    $message->addCc("d@example.com");
    $message_proto->addCc("d@example.com");

    $message->addCc(array("e@example.com", "f@example.com"));
    $message_proto->addCc("e@example.com");
    $message_proto->addCc("f@example.com");

    $message->setHtmlBody("text body");
    $message_proto->setHtmlbody("text body");

    $message->setReplyTo("reply@example.com");
    $message_proto->setReplyto("reply@example.com");

    $response = new VoidProto();
    $this->apiProxyMock->expectCall('mail', 'Send', $message_proto, $response);
    $message->send();
    $this->apiProxyMock->verify();
  }

  public function testSucceedWithOptionsArray() {
    $headers = array('in-reply-to' => 'data',
                     'list-id' => 'data2',
                     'references' => 'data3');
    $attachments = array('test.gif' => 'data',
                         't.jpg' => 'data2',
                         'z.png' => 'data3');
    $options = array('sender' => 'test@example.com',
                     'replyto' => 'test@example.com',
                     'to' => array('b@test.com', 'c@test.com'),
                     'cc' => array('d@test.com', 'e@test.com'),
                     'bcc' => array('f@test.com', 'g@test.com'),
                     'subject' => 'test',
                     'textBody' => 'text body',
                     'htmlBody' => 'html body',
                     'header' => $headers,
                     'attachment' => $attachments);

    $message = new Message($options);
    $message_proto = new MailMessage();

    $message_proto->setSender("test@example.com");
    $message_proto->setReplyto("test@example.com");
    $message_proto->addTo("b@test.com");
    $message_proto->addTo("c@test.com");
    $message_proto->addCc("d@test.com");
    $message_proto->addCc("e@test.com");
    $message_proto->addBcc("f@test.com");
    $message_proto->addBcc("g@test.com");
    $message_proto->setSubject("test");
    $message_proto->setTextbody("text body");
    $message_proto->setHtmlbody("html body");

    $header = $message_proto->addHeader();
    $header->setName("in-reply-to");
    $header->setValue("data");
    $header = $message_proto->addHeader();
    $header->setName("list-id");
    $header->setValue("data2");
    $header = $message_proto->addHeader();
    $header->setName("references");
    $header->setValue("data3");

    $attach = $message_proto->addAttachment();
    $attach->setFilename("test.gif");
    $attach->setData("data");
    $attach = $message_proto->addAttachment();
    $attach->setFilename("t.jpg");
    $attach->setData("data2");
    $attach = $message_proto->addAttachment();
    $attach->setFilename("z.png");
    $attach->setData("data3");

    $response = new VoidProto();
    $this->apiProxyMock->expectCall('mail', 'Send', $message_proto, $response);
    $message->send();
    $this->apiProxyMock->verify();
  }

  public function testSucceedWithAttachments() {
    $message = new Message();
    $message_proto = new MailMessage();
    $this->setupMessageSimple($message, $message_proto);

    $message->addAttachment("test.gif", "data");
    $attach = $message_proto->addAttachment();
    $attach->setFilename("test.gif");
    $attach->setData("data");

    $multi_attach = array("t" => "data2",
                          "z." => "data3");
    $message->addAttachmentArray($multi_attach);
    $attach = $message_proto->addAttachment();
    $attach->setFilename("t");
    $attach->setData("data2");
    $attach = $message_proto->addAttachment();
    $attach->setFilename("z.");
    $attach->setData("data3");

    $response = new VoidProto();
    $this->apiProxyMock->expectCall('mail', 'Send', $message_proto, $response);
    $message->send();
    $this->apiProxyMock->verify();
  }

  public function testSucceedWithHeaders() {
    $message = new Message();
    $message_proto = new MailMessage();
    $this->setupMessageSimple($message, $message_proto);

    $message->addHeader("in-reply-to", "data");
    $header = $message_proto->addHeader();
    $header->setName("in-reply-to");
    $header->setValue("data");

    $multi_header = array("list-id" => "data2", "references" => "data3");
    $message->addHeaderArray($multi_header);
    $header = $message_proto->addHeader();
    $header->setName("list-id");
    $header->setValue("data2");
    $header = $message_proto->addHeader();
    $header->setName("references");
    $header->setValue("data3");

    $response = new VoidProto();
    $this->apiProxyMock->expectCall('mail', 'Send', $message_proto, $response);
    $message->send();
    $this->apiProxyMock->verify();
  }

  public function testRpcApplicationErrorInternalError() {
    $message = new Message();
    $message_proto = new MailMessage();
    $this->setupMessageSimple($message, $message_proto);

    $exception = new ApplicationError(ErrorCode::INTERNAL_ERROR, "test");
    $this->setExpectedException("RuntimeException", "test");

    $this->apiProxyMock->expectCall('mail', 'Send', $message_proto, $exception);
    $message->send();
    $this->apiProxyMock->verify();
  }

  public function testRpcApplicationErrorBadRequest() {
    $message = new Message();
    $message_proto = new MailMessage();
    $this->setupMessageSimple($message, $message_proto);

    $exception = new ApplicationError(ErrorCode::BAD_REQUEST, "test");
    $this->setExpectedException("RuntimeException", "test");

    $this->apiProxyMock->expectCall('mail', 'Send', $message_proto, $exception);
    $message->send();
    $this->apiProxyMock->verify();
  }

  public function testRpcApplicationErrorUnauthorizedSender() {
    $message = new Message();
    $message_proto = new MailMessage();
    $this->setupMessageSimple($message, $message_proto);

    $exception = new ApplicationError(ErrorCode::UNAUTHORIZED_SENDER, "test");
    $this->setExpectedException(
        "InvalidArgumentException",
        "Mail Service Error: Sender (test@example.com) is not an ".
        "authorized email address.");

    $this->apiProxyMock->expectCall('mail', 'Send', $message_proto, $exception);

    $message->send();
    $this->apiProxyMock->verify();
  }

  public function testRpcApplicationErrorInvalidAttachmentType() {
    $message = new Message();
    $message_proto = new MailMessage();
    $this->setupMessageSimple($message, $message_proto);

    $exception = new ApplicationError(ErrorCode::INVALID_ATTACHMENT_TYPE,
                                      "test");
    $this->setExpectedException(
        "InvalidArgumentException",
        "Mail Service Error: Invalid attachment type.");

    $this->apiProxyMock->expectCall('mail', 'Send', $message_proto, $exception);

    $message->send();
    $this->apiProxyMock->verify();
  }

  public function testRpcApplicationErrorInvalidHeaderName() {
    $message = new Message();
    $message_proto = new MailMessage();
    $this->setupMessageSimple($message, $message_proto);

    $exception = new ApplicationError(ErrorCode::INVALID_HEADER_NAME, "test");
    $this->setExpectedException(
        "InvalidArgumentException",
        "Mail Service Error: Invalid header name.");

    $this->apiProxyMock->expectCall('mail', 'Send', $message_proto, $exception);

    $message->send();
    $this->apiProxyMock->verify();
  }
}
