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
 * Unit tests for the PushTask class.
 *
 */

namespace google\appengine\api\taskqueue;

require_once 'google/appengine/api/taskqueue/PushTask.php';
require_once 'google/appengine/testing/ApiProxyTestBase.php';

use google\appengine\api\taskqueue\PushTask;
use google\appengine\testing\ApiProxyTestBase;
use \google\appengine\TaskQueueAddRequest\RequestMethod;
use \google\appengine\TaskQueueBulkAddRequest;
use \google\appengine\TaskQueueBulkAddResponse;
use \google\appengine\TaskQueueServiceError\ErrorCode;

$mockTime = 12345.6;

// This mocks out PHP's microtime() function.
function microtime($get_as_float=false) {
  if (!$get_as_float) {
    die('microtime called with get_as_float=false');
  }
  global $mockTime;
  return $mockTime;
}

class PushTaskTest extends ApiProxyTestBase {

  /**
   * Override time() in current namespace for testing.
   */
  public function setUp() {
    parent::setUp();
    $this->_SERVER = $_SERVER;
  }

  public function tearDown() {
    $_SERVER = $this->_SERVER;
    parent::tearDown();
  }

  private static function buildBulkAddRequest() {
    $req = new TaskQueueBulkAddRequest();
    $task = $req->addAddRequest();
    $task->setQueueName('default');
    $task->setTaskName('');
    $task->setUrl('/someUrl');
    global $mockTime;
    $task->setEtaUsec($mockTime * 1e6);
    $task->setMethod(RequestMethod::POST);
    return $req;
  }

  public function testConstructorUrlWrongType() {
    $this->setExpectedException('\InvalidArgumentException',
        'url_path must be a string. Actual type: integer');
    $task = new PushTask(999, ['key' => 'some value']);
  }

  public function testConstructorUrlEmpty() {
    $this->setExpectedException('\InvalidArgumentException',
        "url_path must begin with '/'.");
    $task = new PushTask('', ['key' => 'some value']);
  }

  public function testConstructorUrlWithoutLeadingSlash() {
    $this->setExpectedException('\InvalidArgumentException',
        "url_path must begin with '/'.");
    $task = new PushTask('wrong', ['key' => 'some value']);
  }

  public function testConstructorUrlMustNotContainQueryString() {
    $this->setExpectedException('\InvalidArgumentException',
        'query strings not allowed in url_path.');
    $task = new PushTask('/someurl?');
  }

  public function testConstructorQueryDataWrongType() {
    $this->setExpectedException('\InvalidArgumentException',
        'query_data must be an array. Actual type: string');
    $task = new PushTask('/myUrl', 'abc');
  }

  public function testConstructorOptionsWrongType() {
    $this->setExpectedException('\InvalidArgumentException',
        'options must be an array. Actual type: integer');
    $task = new PushTask('/someUrl', ['key' => 'some value'], 123);
  }

  public function testConstructorUnknownOptions() {
    $this->setExpectedException('\InvalidArgumentException',
        'Invalid options supplied: nonsense');
    $task = new PushTask('/someUrl', ['key' => 'some value'],
                         ['nonsense' => 123]);
  }

  public function testConstructorInvalidMethod() {
    $this->setExpectedException('\InvalidArgumentException',
        'Invalid method: POSTIT');
    $task = new PushTask('/someUrl', ['key' => 'some value'],
                         ['method' => 'POSTIT']);
  }

  public function testConstructorInvalidName() {
    $this->setExpectedException('\InvalidArgumentException',
        'name must be a string. Actual type: integer');
    $task = new PushTask('/someUrl', ['key' => 'some value'],
                         ['name' => 55]);
  }

  public function testConstructorNameTooLong() {
    $name = str_repeat('a', 501);
    $this->setExpectedException('\InvalidArgumentException',
        'name exceeds maximum length of 500. First 1000 ' .
        'characters of name: ' . $name);
    $task = new PushTask('/someUrl', ['key' => 'some value'],
                         ['name' => $name]);
  }

  public function testConstructorNameMaxLength() {
    // Just tests that this doesn't throw an exception.
    $task = new PushTask('/someUrl', ['key' => 'some value'],
                       ['name' => str_repeat('a', 500)]);
  }

  public function testConstructorNameBadCharacters() {
    $this->setExpectedException('\InvalidArgumentException',
        'name must match pattern: ' . PushTask::NAME_PATTERN .  '. name: @');
    $task = new PushTask('/someUrl', ['key' => 'some value'],
                       ['name' => '@']);
  }

  public function testConstructorInvalidDelaySeconds() {
    $this->setExpectedException('\InvalidArgumentException',
        'delay_seconds must be a numeric type.');
    $task = new PushTask('/someUrl', ['key' => 'some value'],
                         ['delay_seconds' => 'a few']);
  }

  public function testConstructorNegativeDelaySeconds() {
    $this->setExpectedException('\InvalidArgumentException',
        'delay_seconds must be between 0 and ' . PushTask::MAX_DELAY_SECONDS .
        ' (30 days). delay_seconds: -1');
    $task = new PushTask('/someUrl', ['key' => 'some value'],
                         ['delay_seconds' => -1]);
  }

  public function testConstructorDelaySecondsTooBig() {
    $delay = 1 + 30 * 86400;
    $this->setExpectedException('\InvalidArgumentException',
        'delay_seconds must be between 0 and ' . PushTask::MAX_DELAY_SECONDS .
        ' (30 days). delay_seconds: ' . $delay);
    $task = new PushTask('/someUrl', ['key' => 'some value'],
                         ['delay_seconds' => $delay]);
  }

  public function testConstructorMaxDelaySecond() {
    // Just tests that a 30 day delay_seconds doesn't throw an exception.
    $task = new PushTask('/someUrl', ['key' => 'some value'],
                         ['delay_seconds' => 30 * 86400]);
  }

  public function testConstructorUrlTooBig() {
    $url = '/' . str_repeat('b', 2083);
    $this->setExpectedException(
        '\InvalidArgumentException',
        'URL length greater than maximum of ' . PushTask::MAX_URL_LENGTH) .
        '. URL: ' . $url;
    $t = new PushTask($url);
  }

  public function testConstructorHeaderWrongType() {
    $this->setExpectedException('\InvalidArgumentException',
        'header must be a string. Actual type: double');
    $t = new PushTask('/some-url', ['user-key' => 'user-data'],
        ['header' => 50.0]);
  }

  public function testConstructorHeaderWithoutColon() {
    $this->setExpectedException('\InvalidArgumentException',
        'Each header must contain a colon. Header: bad-header!');
    $t = new PushTask('/some-url', ['user-key' => 'user-data'],
        ['header' => 'bad-header!']);
  }

  public function testConstructorInvalidContentType() {
    $this->setExpectedException('\InvalidArgumentException',
        'Content-type header may not be specified as it is set by the task.');
    $t = new PushTask('/some-url', ['user-key' => 'user-data'],
        ['header' => 'content-type: application/pdf']);
  }

  public function testAddInvalidQueue() {
    $this->setExpectedException('\InvalidArgumentException');
    (new PushTask('/someUrl'))->add(999);
  }

  public function testAddTaskTooBig() {
    $this->setExpectedException(
        '\google\appengine\api\taskqueue\TaskQueueException',
        'Task greater than maximum size of ' . PushTask::MAX_TASK_SIZE_BYTES);
    // Althought 102400 is the max size, it's for the serialized proto which
    // includes the URL etc.
    (new PushTask('/someUrl', ['field' => str_repeat('a', 102395)]))->add();
  }

  public function testPushTaskSimplestAdd() {
    $req = self::buildBulkAddRequest();

    $resp = new TaskQueueBulkAddResponse();
    $task_result = $resp->addTaskResult();
    $task_result->setResult(ErrorCode::OK);
    $task_result->setChosenTaskName('fred');

    $this->apiProxyMock->expectCall('taskqueue', 'BulkAdd', $req, $resp);

    $task_name = (new PushTask('/someUrl'))->add();
    $this->assertEquals('fred', $task_name);
    $this->apiProxyMock->verify();
  }

  public function testPushTaskSimpleAddWithQueryData() {
    $query_data = ['key' => 'some value'];
    $req = self::buildBulkAddRequest();
    $req->getAddRequest(0)->setBody(http_build_query($query_data));
    $header = $req->getAddRequest(0)->addHeader();
    $header->setKey('content-type');
    $header->setValue('application/x-www-form-urlencoded');

    $resp = new TaskQueueBulkAddResponse();

    $this->apiProxyMock->expectCall('taskqueue', 'BulkAdd', $req, $resp);

    (new PushTask('/someUrl', $query_data))->add();
    $this->apiProxyMock->verify();
  }

  public function testPushTaskAddToNonDefaultQueue() {
    $req = self::buildBulkAddRequest();
    $req->getAddRequest(0)->setQueueName('myqueue');

    $resp = new TaskQueueBulkAddResponse();

    $this->apiProxyMock->expectCall('taskqueue', 'BulkAdd', $req, $resp);

    (new PushTask('/someUrl'))->add('myqueue');
    $this->apiProxyMock->verify();
  }

  public function testPushTaskAddBasicGetRequest() {
    $req = self::buildBulkAddRequest();
    $req->getAddRequest(0)->setMethod(RequestMethod::GET);

    $resp = new TaskQueueBulkAddResponse();

    $this->apiProxyMock->expectCall('taskqueue', 'BulkAdd', $req, $resp);

    (new PushTask('/someUrl', [], ['method' => 'GET']))->add();
    $this->apiProxyMock->verify();
  }

  public function testPushTaskAddGetRequestWithQueryData() {
    $req = self::buildBulkAddRequest();
    $req->getAddRequest(0)->setMethod(RequestMethod::GET);
    $req->getAddRequest(0)->setUrl('/someUrl?aKey=aValue');

    $resp = new TaskQueueBulkAddResponse();

    $this->apiProxyMock->expectCall('taskqueue', 'BulkAdd', $req, $resp);

    $task = new PushTask('/someUrl', ['aKey' => 'aValue'], ['method' => 'GET']);
    $task->add();
    $this->apiProxyMock->verify();
  }

  public function testPushTaskWithNameAndETA() {
    $req = self::buildBulkAddRequest();
    $add_req = $req->getAddRequest(0);
    $add_req->setTaskName('customTaskName');
    $add_req->setEtaUsec($add_req->getEtaUsec() + 5 * 1e6);

    $resp = new TaskQueueBulkAddResponse();

    $this->apiProxyMock->expectCall('taskqueue', 'BulkAdd', $req, $resp);

    $task = new PushTask('/someUrl', [],
                         ['delay_seconds' => 5, 'name' => 'customTaskName']);
    $task_name = $task->add();
    $this->assertEquals('customTaskName', $task_name);
    $this->apiProxyMock->verify();
  }

  public function testPushTaskAddWithHeader() {
    $req = self::buildBulkAddRequest();
    $add_req = $req->getAddRequest(0);
    $header = $add_req->addHeader();
    $header->setKey('custom-header');
    $header->setValue('54321');

    $resp = new TaskQueueBulkAddResponse();
    $task_result = $resp->addTaskResult();
    $task_result->setResult(ErrorCode::OK);
    $task_result->setChosenTaskName('fred');

    $this->apiProxyMock->expectCall('taskqueue', 'BulkAdd', $req, $resp);

    $task_name = (new PushTask('/someUrl', [],
        ['header' => 'custom-header: 54321']))->add();
    $this->assertEquals('fred', $task_name);
    $this->apiProxyMock->verify();
  }

  public function testPushTaskAddWithHeaderAndQueryData() {
    $query_data = ['key' => 'some value'];
    $req = self::buildBulkAddRequest();
    $add_req = $req->getAddRequest(0);
    $add_req->setBody(http_build_query($query_data));

    $header = $add_req->addHeader();
    $header->setKey('content-type');
    $header->setValue('application/x-www-form-urlencoded');
    $header = $add_req->addHeader();
    $header->setKey('custom-header');
    $header->setValue('xyz');

    $resp = new TaskQueueBulkAddResponse();

    $this->apiProxyMock->expectCall('taskqueue', 'BulkAdd', $req, $resp);

    (new PushTask('/someUrl', $query_data,
        ['header' => 'custom-header: xyz']))->add();
    $this->apiProxyMock->verify();
  }

  public function testPushTaskAddWithTwoHeaders() {
    $req = self::buildBulkAddRequest();
    $add_req = $req->getAddRequest(0);
    $header = $add_req->addHeader();
    $header->setKey('custom-header');
    $header->setValue('54321');
    $header = $add_req->addHeader();
    $header->setKey('another-custom-header');
    $header->setValue('abc');


    $resp = new TaskQueueBulkAddResponse();
    $task_result = $resp->addTaskResult();
    $task_result->setResult(ErrorCode::OK);
    $task_result->setChosenTaskName('fred');

    $this->apiProxyMock->expectCall('taskqueue', 'BulkAdd', $req, $resp);

    $task_name = (new PushTask('/someUrl', [],
        ['header' => "custom-header: 54321\r\n" .
                     "another-custom-header: abc"]))->add();
    $this->assertEquals('fred', $task_name);
    $this->apiProxyMock->verify();
  }

  public function testUnknownQueueError() {
    $req = self::buildBulkAddRequest();
    $exception = new \google\appengine\runtime\ApplicationError(
        ErrorCode::UNKNOWN_QUEUE, 'message');

    $this->setExpectedException(
        '\google\appengine\api\taskqueue\TaskQueueException',
        'Unknown queue');

    $this->apiProxyMock->expectCall('taskqueue', 'BulkAdd', $req, $exception);

    (new PushTask('/someUrl'))->add();
  }

  public function testTransientError() {
    $req = self::buildBulkAddRequest();
    $exception = new \google\appengine\runtime\ApplicationError(
        ErrorCode::TRANSIENT_ERROR, 'message');

    $this->setExpectedException(
        '\google\appengine\api\taskqueue\TransientTaskQueueException');

    $this->apiProxyMock->expectCall('taskqueue', 'BulkAdd', $req, $exception);

    (new PushTask('/someUrl'))->add();
  }

  public function testPermissionDeniedError() {
    $req = self::buildBulkAddRequest();
    $exception = new \google\appengine\runtime\ApplicationError(
        ErrorCode::PERMISSION_DENIED, 'message');

    $this->setExpectedException(
        '\google\appengine\api\taskqueue\TaskQueueException',
        'Permission Denied');

    $this->apiProxyMock->expectCall('taskqueue', 'BulkAdd', $req, $exception);

    (new PushTask('/someUrl'))->add();
  }

  public function testTombstonedTaskError() {
    $req = self::buildBulkAddRequest();
    $exception = new \google\appengine\runtime\ApplicationError(
        ErrorCode::TOMBSTONED_TASK, 'message');

    $this->setExpectedException(
        '\google\appengine\api\taskqueue\TaskAlreadyExistsException');

    $this->apiProxyMock->expectCall('taskqueue', 'BulkAdd', $req, $exception);

    (new PushTask('/someUrl'))->add();
  }

  public function testTaskAlreadyExistsError() {
    $req = self::buildBulkAddRequest();
    $exception = new \google\appengine\runtime\ApplicationError(
        ErrorCode::TASK_ALREADY_EXISTS, 'message');

    $this->setExpectedException(
        '\google\appengine\api\taskqueue\TaskAlreadyExistsException');

    $this->apiProxyMock->expectCall('taskqueue', 'BulkAdd', $req, $exception);

    (new PushTask('/someUrl'))->add();
  }

  public function testTaskInvalidQueueModeError() {
    $req = self::buildBulkAddRequest();
    $exception = new \google\appengine\runtime\ApplicationError(
        ErrorCode::INVALID_QUEUE_MODE, 'message');

    $this->setExpectedException(
        '\google\appengine\api\taskqueue\TaskQueueException',
        'Cannot add a PushTask to a pull queue.');

    $this->apiProxyMock->expectCall('taskqueue', 'BulkAdd', $req, $exception);

    (new PushTask('/someUrl'))->add();
  }
}
