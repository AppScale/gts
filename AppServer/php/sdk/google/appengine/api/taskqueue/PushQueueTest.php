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
 * Unit tests for the PushQueue class.
 *
 */

namespace google\appengine\api\taskqueue;

require_once 'google/appengine/api/taskqueue/PushQueue.php';
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

class PushQueueTest extends ApiProxyTestBase {

  public function setUp() {
    parent::setUp();
    $this->_SERVER = $_SERVER;
  }

  public function tearDown() {
    $_SERVER = $this->_SERVER;
    parent::tearDown();
  }

  private static function buildBulkAddRequest($queue_name = 'default') {
    $req = new TaskQueueBulkAddRequest();
    $task = $req->addAddRequest();
    $task->setQueueName($queue_name);
    $task->setTaskName('');
    $task->setUrl('/someUrl');
    global $mockTime;
    $task->setEtaUsec($mockTime * 1e6);
    $task->setMethod(RequestMethod::POST);
    return $req;
  }

  private static function buildBulkAddRequestWithTwoTasks(
      $queue_name = 'default') {
    $req = self::buildBulkAddRequest($queue_name);

    $task = $req->addAddRequest();
    $task->setQueueName($queue_name);
    $task->setTaskName('');
    $task->setUrl('/someOtherUrl');
    global $mockTime;
    $task->setEtaUsec($mockTime * 1e6);
    $task->setMethod(RequestMethod::POST);

    return $req;
  }

  public function testConstructorNameWrongType() {
    $this->setExpectedException('\InvalidArgumentException',
        '$name must be a string. Actual type: integer');
    $queue = new PushQueue(54321);
  }

  public function testGetName() {
    $queue = new PushQueue();
    $this->assertEquals('default', $queue->getName());
    $queue = new PushQueue('fast-queue');
    $this->assertEquals('fast-queue', $queue->getName());
  }

  public function testAddTaskTooBig() {
    $this->setExpectedException(
        '\google\appengine\api\taskqueue\TaskQueueException',
        'Task greater than maximum size of ' . PushTask::MAX_TASK_SIZE_BYTES);
    // Althought 102400 is the max size, it's for the serialized proto which
    // includes the URL etc.
    $task = new PushTask('/someUrl', ['field' => str_repeat('a', 102395)]);
    (new PushQueue())->addTasks([$task]);
  }

  public function testPushQueueAddTasksWrongType() {
    $this->setExpectedException('\InvalidArgumentException',
        '$tasks must be an array. Actual type: string');
    $queue = new PushQueue();
    $task_names = $queue->addTasks('not an array');
  }

  public function testPushQueueAddTasksWrongValueType() {
    $this->setExpectedException('\InvalidArgumentException',
        'All values in $tasks must be instances of PushTask. ' .
        'Actual type: double');
    $queue = new PushQueue();
    $task_names = $queue->addTasks([1.0]);
  }

  public function testPushQueueAddTasksTooMany() {
    $this->setExpectedException('\InvalidArgumentException',
        '$tasks must contain at most 100 tasks. Actual size: 101');
    $tasks = [];
    for ($i = 0; $i < 101; $i++) {
      $tasks[] = new PushTask('/a-url');
    }
    $queue = new PushQueue();
    $queue->addTasks($tasks);
  }

  public function testPushQueueAddTasksEmptyArray() {
    $queue = new PushQueue();
    $task_names = $queue->addTasks([]);
    $this->assertEquals([], $task_names);
    $this->apiProxyMock->verify();
  }

  public function testPushQueueSimplestAddTasks() {
    $req = self::buildBulkAddRequest();

    $resp = new TaskQueueBulkAddResponse();
    $task_result = $resp->addTaskResult();
    $task_result->setResult(ErrorCode::OK);
    $task_result->setChosenTaskName('fred');

    $this->apiProxyMock->expectCall('taskqueue', 'BulkAdd', $req, $resp);

    $task = new PushTask('/someUrl');
    $queue = new PushQueue();
    $task_names = $queue->addTasks([$task]);
    $this->assertEquals(['fred'], $task_names);
    $this->apiProxyMock->verify();
  }

  public function testPushQueueAddTwoTasks() {
    $req = self::buildBulkAddRequestWithTwoTasks();

    $resp = new TaskQueueBulkAddResponse();
    $task_result = $resp->addTaskResult();
    $task_result->setResult(ErrorCode::OK);
    $task_result->setChosenTaskName('fred');
    $task_result = $resp->addTaskResult();
    $task_result->setResult(ErrorCode::OK);
    $task_result->setChosenTaskName('bob');

    $this->apiProxyMock->expectCall('taskqueue', 'BulkAdd', $req, $resp);

    $task1 = new PushTask('/someUrl');
    $task2 = new PushTask('/someOtherUrl');
    $queue = new PushQueue();
    $task_names = $queue->addTasks([$task1, $task2]);
    $this->assertEquals(['fred', 'bob'], $task_names);
    $this->apiProxyMock->verify();
  }

  public function testPushQueueAddTwoTasksNonDefaultQueue() {
    $req = self::buildBulkAddRequestWithTwoTasks('superQ');

    $resp = new TaskQueueBulkAddResponse();
    $task_result = $resp->addTaskResult();
    $task_result->setResult(ErrorCode::OK);
    $task_result->setChosenTaskName('fred');
    $task_result = $resp->addTaskResult();
    $task_result->setResult(ErrorCode::OK);
    $task_result->setChosenTaskName('bob');

    $this->apiProxyMock->expectCall('taskqueue', 'BulkAdd', $req, $resp);

    $task1 = new PushTask('/someUrl');
    $task2 = new PushTask('/someOtherUrl');
    $queue = new PushQueue('superQ');
    $task_names = $queue->addTasks([$task1, $task2]);
    $this->assertEquals(['fred', 'bob'], $task_names);
    $this->apiProxyMock->verify();
  }

  public function testPushQueueTaskAlreadyExistsError() {
    $req = self::buildBulkAddRequestWithTwoTasks();

    $resp = new TaskQueueBulkAddResponse();
    $task_result = $resp->addTaskResult();
    $task_result->setResult(ErrorCode::OK);
    $task_result->setChosenTaskName('fred');
    $task_result = $resp->addTaskResult();
    $task_result->setResult(ErrorCode::TOMBSTONED_TASK);
    $task_result->setChosenTaskName('bob');

    $this->setExpectedException(
        '\google\appengine\api\taskqueue\TaskAlreadyExistsException');
    $this->apiProxyMock->expectCall('taskqueue', 'BulkAdd', $req, $resp);

    $task1 = new PushTask('/someUrl');
    $task2 = new PushTask('/someOtherUrl');
    $queue = new PushQueue();
    $queue->addTasks([$task1, $task2]);
    $this->apiProxyMock->verify();
  }

  public function testPushQueueUnknownQueueError() {
    $req = self::buildBulkAddRequestWithTwoTasks();

    $resp = new TaskQueueBulkAddResponse();
    $task_result = $resp->addTaskResult();
    $task_result->setResult(ErrorCode::OK);
    $task_result->setChosenTaskName('fred');
    $task_result = $resp->addTaskResult();
    $task_result->setResult(ErrorCode::UNKNOWN_QUEUE);
    $task_result->setChosenTaskName('bob');

    $this->setExpectedException(
        '\google\appengine\api\taskqueue\TaskQueueException',
        'Unknown queue');
    $this->apiProxyMock->expectCall('taskqueue', 'BulkAdd', $req, $resp);

    $task1 = new PushTask('/someUrl');
    $task2 = new PushTask('/someOtherUrl');
    $queue = new PushQueue();
    $queue->addTasks([$task1, $task2]);
    $this->apiProxyMock->verify();
  }

  // UNKNOWN_QUEUE should take precedence over TOMBSTONED_TASK.
  public function testPushQueueTwoErrors() {
    $req = self::buildBulkAddRequestWithTwoTasks();

    $resp = new TaskQueueBulkAddResponse();
    $task_result = $resp->addTaskResult();
    $task_result->setResult(ErrorCode::TOMBSTONED_TASK);
    $task_result->setChosenTaskName('fred');
    $task_result = $resp->addTaskResult();
    $task_result->setResult(ErrorCode::UNKNOWN_QUEUE);
    $task_result->setChosenTaskName('bob');

    $this->setExpectedException(
        '\google\appengine\api\taskqueue\TaskQueueException',
        'Unknown queue');
    $this->apiProxyMock->expectCall('taskqueue', 'BulkAdd', $req, $resp);

    $task1 = new PushTask('/someUrl');
    $task2 = new PushTask('/someOtherUrl');
    $queue = new PushQueue();
    $queue->addTasks([$task1, $task2]);
    $this->apiProxyMock->verify();
  }

  public function testPushQueueTooManyTasksError() {
    $req = self::buildBulkAddRequestWithTwoTasks();

    $resp = new TaskQueueBulkAddResponse();
    $task_result = $resp->addTaskResult();
    $task_result->setResult(ErrorCode::OK);
    $task_result->setChosenTaskName('fred');
    $task_result = $resp->addTaskResult();
    $task_result->setResult(ErrorCode::TOO_MANY_TASKS);
    $task_result->setChosenTaskName('bob');

    $this->setExpectedException(
        '\google\appengine\api\taskqueue\TaskQueueException',
        'Too many tasks in request.');
    $this->apiProxyMock->expectCall('taskqueue', 'BulkAdd', $req, $resp);

    $task1 = new PushTask('/someUrl');
    $task2 = new PushTask('/someOtherUrl');
    $queue = new PushQueue();
    $queue->addTasks([$task1, $task2]);
    $this->apiProxyMock->verify();
  }

}
