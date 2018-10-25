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
# - Support additional options for PushTasks, including retry options and maybe
#   raw payloads.
# - Support various queue level functionality such as FetchQueueStats.
# - Add PullTask class.  At that point, perhaps refactor to use a Task
#   baseclass to share code with PushTask.
# - Add a PullQueue class, including pull specific queue methods such as
#   leaseTasks, DeleteTasks etc.
# - Consider adding a Queue base class with common functionality between Push
#   and Pull queues.

namespace google\appengine\api\taskqueue;

require_once 'google/appengine/api/taskqueue/PushQueue.php';
require_once 'google/appengine/api/taskqueue/taskqueue_service_pb.php';

use \google\appengine\TaskQueueAddRequest\RequestMethod;


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
    'header'        => '',
  ];

  private $url;

  private $query_data;

  private $options;

  private $headers = [];

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
   *   <li>'header': string Additional headers to be sent when the task
   *   executes.</li>
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

    $this->query_data = $query_data;
    $this->url = $url_path;
    if ($query_data) {
      if (in_array($this->options['method'], ['GET', 'HEAD', 'DELETE'])) {
        $this->url = $url_path . '?' . http_build_query($query_data);
      } else { // PUT or POST
        $this->headers[] = 'content-type: application/x-www-form-urlencoded';
      }
    }
    if (strlen($this->url) > self::MAX_URL_LENGTH) {
      throw new \InvalidArgumentException(
          'URL length greater than maximum of ' .
          PushTask::MAX_URL_LENGTH . '. URL: ' . $this->url);
    }

    // Handle user specified headers.
    $header = $this->options['header'];
    if (!is_string($header)) {
      throw new \InvalidArgumentException('header must be a string. ' .
          'Actual type: ' . gettype($header));
    }

    $has_content_type = !empty($this->headers);
    $header_array = explode("\r\n", $header);
    foreach ($header_array as $h) {
      $h = trim($h);
      if (empty($h)) {
        continue;
      }
      if (strpos($h, ':') == false) {
        throw new \InvalidArgumentException(
            'Each header must contain a colon. Header: ' . $h);
      }
      if ($has_content_type &&
          strncasecmp('content-type', $h, strlen('content-type')) == 0) {
        throw new \InvalidArgumentException('Content-type header may not ' .
            'be specified as it is set by the task.');
        continue;
      }
      $this->headers[] = $h;
    }
  }

  /**
   * Return the task's URL.  This will be the task's URL path, plus any query
   * parameters if the task's method is GET, HEAD, or DELETE.
   *
   * @return string The task's URL path.
   */
  public function getUrl() {
    return $this->url;
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
   * Return the task's headers.
   *
   * @return string[] The headers that will be sent when the task is
   * executed. This list is not exhaustive as the backend may add more
   * headers at execution time.
   * The array is numerically indexed and of the same format as that returned
   * by the standard headers_list() function.
   */
  public function getHeaders() {
    return $this->headers;
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
  public function add($queue_name = 'default') {
    $queue = new PushQueue($queue_name);
    return $queue->addTasks([$this])[0];
  }
}
