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
 * The PushTask class, which is part of the Task Queue API.
 *
 */

# Overview of TODOs(petermck) for building out the full Task Queue API:
# - Support additional options for PushTasks, including headers, target,
#   payload, and retry options.
# - Add a PushQueue class which will support adding multiple tasks at once, plus
#   various other queue level functionality such as FetchQueueStats.
# - Add PullTask class.  At that point, perhaps refactor to use a Task
#   baseclass to share code with PushTask.
# - Add a PullQueue class, including pull specific queue methods such as
#   leaseTasks, DeleteTasks etc.
# - Consider adding a Queue base class with common functionality between Push
#   and Pull queues.

namespace google\appengine\api\taskqueue;

require_once 'google/appengine/api/taskqueue/taskqueue_service_pb.php';
require_once 'google/appengine/api/taskqueue/TaskAlreadyExistsException.php';
require_once 'google/appengine/api/taskqueue/TaskQueueException.php';
require_once 'google/appengine/api/taskqueue/TransientTaskQueueException.php';
require_once 'google/appengine/runtime/ApiProxy.php';
require_once 'google/appengine/runtime/ApplicationError.php';

use \google\appengine\runtime\ApiProxy;
use \google\appengine\runtime\ApplicationError;
use \google\appengine\TaskQueueAddRequest;
use \google\appengine\TaskQueueAddRequest\RequestMethod;
use \google\appengine\TaskQueueAddResponse;
use \google\appengine\TaskQueueBulkAddRequest;
use \google\appengine\TaskQueueBulkAddResponse;
use \google\appengine\TaskQueueServiceError\ErrorCode;


/**
 * A PushTask encapsulates a unit of work that an application places onto a
 * Push Queue for asnychronous execution. The queue executes that work by
 * sending the task back to the application in the form of an HTTP request to
 * one of the application's handlers.
 * This class is immutable.
 */
final class PushTask {
  /**
   * A task may be scheduled up to 30 days into the future.
   */
  const MAX_DELAY_SECONDS = 2592000;
  const MAX_NAME_LENGTH = 500;
  const MAX_TASK_SIZE_BYTES = 102400;
  const MAX_URL_LENGTH = 2083;
  const NAME_PATTERN = '/^[a-zA-Z0-9_-]+$/';

  private static $methods = [
    'POST'   => RequestMethod::POST,
    'GET'    => RequestMethod::GET,
    'HEAD'   => RequestMethod::HEAD,
    'PUT'    => RequestMethod::PUT,
    'DELETE' => RequestMethod::DELETE
  ];

  private static $default_options = [
    'delay_seconds' => 0.0,
    'method'        => 'POST',
    'name'          => '',
  ];

  private $url_path;

  private $query_data;

  private $options;

  /**
   * Construct a PushTask.
   *
   * @param string $url_path The path of the URL handler for this task relative
   * to your application's root directory.
   * @param array $query_data The data carried by task, typically in the form of
   * a set of key value pairs. This data will be encoded using
   * http_build_query() and will be either:
   * <ul>
   *   <li>Added to the payload of the http request if the task's method is POST
   *    or PUT.</li>
   *   <li>Added to the URL if the task's method is GET, HEAD, or DELETE.</li>
   * </ul>
   * @param array $options Additional options for the task. Valid options are:
   * <ul>
   *   <li>'method': string One of 'POST', 'GET', 'HEAD', 'PUT', 'DELETE'.
   *   Default value: 'POST'.</li>
   *   <li>'name': string Name of the task. Defaults to '' meaning the service
   *   will generate a unique task name.</li>
   *   <li>'delay_seconds': float The minimum time to wait before executing the
   *   task. Default: zero.</li>
   * </ul>
   */
  public function __construct($url_path, $query_data=[], $options=[]) {
    if (!is_string($url_path)) {
      throw new \InvalidArgumentException('url_path must be a string. ' .
          'Actual type: ' . gettype($url_path));
    }
    if (empty($url_path) || $url_path[0] !== '/') {
      throw new \InvalidArgumentException(
          'url_path must begin with \'/\'.');
    }
    if (strpos($url_path, "?") !== false) {
      throw new \InvalidArgumentException(
          'query strings not allowed in url_path.');
    }
    if (!is_array($query_data)) {
      throw new \InvalidArgumentException('query_data must be an array. ' .
          'Actual type: ' . gettype($query_data));
    }
    if (!is_array($options)) {
      throw new \InvalidArgumentException('options must be an array. ' .
          'Actual type: ' . gettype($options));
    }

    $extra_options = array_diff(array_keys($options),
                                array_keys(self::$default_options));
    if (!empty($extra_options)) {
      throw new \InvalidArgumentException('Invalid options supplied: ' .
                                          implode(',', $extra_options));
    }

    $this->url_path = $url_path;
    $this->query_data = $query_data;
    $this->options = array_merge(self::$default_options, $options);

    if (!array_key_exists($this->options['method'], self::$methods)) {
      throw new \InvalidArgumentException('Invalid method: ' .
                                          $this->options['method']);
    }
    $name = $this->options['name'];
    if (!is_string($name)) {
      throw new \InvalidArgumentException('name must be a string. ' .
          'Actual type: ' . gettype($name));
    }
    if (!empty($name)) {
      if (strlen($name) > self::MAX_NAME_LENGTH) {
        $display_len = 1000;
        throw new \InvalidArgumentException('name exceeds maximum length of ' .
            self::MAX_NAME_LENGTH . ". First $display_len characters of name: "
            . substr($name, 0, $display_len));
      }
      if (!preg_match(self::NAME_PATTERN, $name)) {
        throw new \InvalidArgumentException('name must match pattern: ' .
            self::NAME_PATTERN . '. name: ' . $name);
      }
    }
    $delay = $this->options['delay_seconds'];
    if (!(is_double($delay) || is_long($delay))) {
      throw new \InvalidArgumentException(
          'delay_seconds must be a numeric type.');
    }
    if ($delay < 0 || $delay > self::MAX_DELAY_SECONDS) {
      throw new \InvalidArgumentException(
          'delay_seconds must be between 0 and ' . self::MAX_DELAY_SECONDS .
          ' (30 days). delay_seconds: ' . $delay);
    }
  }

  /**
   * Return the task's URL path.
   *
   * @return string The task's URL path.
   */
  public function getUrlPath() {
    return $this->url_path;
  }

  /**
   * Return the task's query data.
   *
   * @return array The task's query data.
   */
  public function getQueryData() {
    return $this->query_data;
  }

  /**
   * Return the task's name if it was explicitly named.
   *
   * @return string The task's name if it was explicity named, or empty string
   * if it will be given a uniquely generated name in the queue.
   */
  public function getName() {
    return $this->options['name'];
  }

  /**
   * Return the task's execution delay, in seconds.
   *
   * @return float The task's execution delay in seconds.
   */
  public function getDelaySeconds() {
    return $this->options['delay_seconds'];
  }

  /**
   * Return the task's HTTP method.
   *
   * @return string The task's HTTP method, i.e. one of 'DELETE', 'GET', 'HEAD',
   * 'POST', 'PUT'.
   */
  public function getMethod() {
    return $this->options['method'];
  }

  /**
   * Adds the task to a queue.
   *
   * @param string $queue The name of the queue to add to. Defaults to
   * 'default'.
   *
   * @return string The name of the task.
   *
   * @throws TaskAlreadyExistsException if a task of the same name already
   * exists in the queue.
   * @throws TaskQueueException if there was a problem using the service.
   */
  public function add($queue = 'default') {
    if (!is_string($queue)) {
      throw new \InvalidArgumentException('query must be a string.');
    }
    # TODO: validate queue name length and regex.
    return self::addTasks([$this], $queue)[0];
  }

  private static function applicationErrorToException($error) {
    switch($error->getApplicationError()) {
      case ErrorCode::UNKNOWN_QUEUE:
        return new TaskQueueException('Unknown queue');
      case ErrorCode::TRANSIENT_ERROR:
        return new TransientTaskQueueException();
      case ErrorCode::INTERNAL_ERROR:
        return new TaskQueueException('Internal error');
      case ErrorCode::TASK_TOO_LARGE:
        return new TaskQueueException('Task too large');
      case ErrorCode::INVALID_TASK_NAME:
        return new TaskQueueException('Invalid task name');
      case ErrorCode::INVALID_QUEUE_NAME:
      case ErrorCode::TOMBSTONED_QUEUE:
        return new TaskQueueException('Invalid queue name');
      case ErrorCode::INVALID_URL:
        return new TaskQueueException('Invalid URL');
      case ErrorCode::PERMISSION_DENIED:
        return new TaskQueueException('Permission Denied');

      // Both TASK_ALREADY_EXISTS and TOMBSTONED_TASK are translated into the
      // same exception. This is in keeping with the Java API but different to
      // the Python API. Knowing that the task is tombstoned isn't particularly
      // interesting: the main point is that it has already been added.
      case ErrorCode::TASK_ALREADY_EXISTS:
      case ErrorCode::TOMBSTONED_TASK:
        return new TaskAlreadyExistsException();
      case ErrorCode::INVALID_ETA:
        return new TaskQueueException('Invalid delay_seconds');
      case ErrorCode::INVALID_REQUEST:
        return new TaskQueueException('Invalid request');
      case ErrorCode::INVALID_QUEUE_MODE:
        return new TaskQueueException('Cannot add a PushTask to a pull queue.');
      default:
        return new TaskQueueException(
            'Error Code: ' . $error->getApplicationError());
    }
  }

  # TODO: Move this function into a PushQueue class when we have one.
  # Returns an array containing the name of each task added.
  private static function addTasks($tasks, $queue) {
    $req = new TaskQueueBulkAddRequest();
    $resp = new TaskQueueBulkAddResponse();

    $names = [];
    $current_time = microtime(true);
    foreach ($tasks as $task) {
      $names[] = $task->getName();
      $add = $req->addAddRequest();
      $add->setQueueName($queue);
      $add->setTaskName($task->getName());
      $add->setEtaUsec(($current_time + $task->getDelaySeconds()) * 1e6);
      $add->setMethod(self::$methods[$task->getMethod()]);
      if ($task->getMethod() == 'POST' || $task->getMethod() == 'PUT') {
        $add->setUrl($task->getUrlPath());
        if ($task->getQueryData()) {
          $add->setBody(http_build_query($task->getQueryData()));
          $header = $add->addHeader();
          $header->setKey('content-type');
          $header->setValue('application/x-www-form-urlencoded');
        }
      } else {
        $url_path = $task->getUrlPath();
        if ($task->getQueryData()) {
          $url_path = $url_path . '?' .
              http_build_query($task->getQueryData());
        }
        $add->setUrl($url_path);
      }
      if (strlen($add->getUrl()) > self::MAX_URL_LENGTH) {
        throw new TaskQueueException('URL length greater than maximum of ' .
            self::MAX_URL_LENGTH . '. URL: ' . $add->getUrl());
      }
      if ($add->byteSizePartial() > self::MAX_TASK_SIZE_BYTES) {
        throw new TaskQueueException('Task greater than maximum size of ' .
            self::MAX_TASK_SIZE_BYTES . '. size: ' . $add->byteSizePartial());
      }
    }

    try {
      ApiProxy::makeSyncCall('taskqueue', 'BulkAdd', $req, $resp);
    } catch (ApplicationError $e) {
      throw self::applicationErrorToException($e);
    }

    // Update $names with any generated task names.
    $results = $resp->getTaskResultList();
    foreach ($results as $index => $taskResult) {
      if ($taskResult->hasChosenTaskName()) {
        $names[$index] = $taskResult->getChosenTaskName();
      }
    }
    return $names;
  }
}
