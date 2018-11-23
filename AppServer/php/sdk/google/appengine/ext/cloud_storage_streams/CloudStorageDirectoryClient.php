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
 * Cloud Storage Directory Client handles dir_opendir(), dir_readdir() and
 * dir_closedir() calls for GCS bucket.
 *
 */

namespace google\appengine\ext\cloud_storage_streams;

require_once 'google/appengine/ext/cloud_storage_streams/CloudStorageClient.php';
require_once 'google/appengine/util/string_util.php';

use \google\appengine\util as util;

/**
 * Client for deleting objects from Google Cloud Storage.
 */
final class CloudStorageDirectoryClient extends CloudStorageClient {
  // Maximum number of keys to return per call
  const MAX_KEYS = 1000;

  // Next marker is used when the previous call returned a trucated set of
  // results. It will resume listing after the last result returned from the
  // previous set.
  private $next_marker = null;

  // A string that can be used to limit the number of objects that are returned
  // in a GET Bucket request. Can be used in conjunction with a delimiter.
  private $prefix = null;

  // The current list of files we're enumerating through
  private $current_file_list = null;

  public function __construct($bucket_name, $object_prefix, $context) {
    parent::__construct($bucket_name, $object_prefix, $context);
    // Ignore the leading slash
    if (isset($object_prefix)) {
      if (!util\endsWith($object_prefix, '/')) {
        $object_prefix .= '/';
      }
      $this->prefix = substr($object_prefix, 1);
    }
  }

  /**
   * Make the initial connection to GCS and fill the read buffer with files.
   *
   * @return bool <code>true</code> if we can connect to the Cloud Storage
   * bucket, <code>false</code> otherwise.
   */
  public function initialise() {
    return $this->fillFileBuffer();
  }

  /**
   * Read the next file in the directory list. If the list is empty and we
   * believe that there are more results to read then fetch them
   *
   * @return string The name of the next file in the directory, false if there
   * are not more files.
   */
  public function dir_readdir() {
    // Current file list will be null if there was a rewind.
    if (is_null($this->current_file_list)) {
      if (!$this->fillFileBuffer()) {
        return false;
      }
    } else if (empty($this->current_file_list)) {
      // If there is no next marker, or we cannot fill the buffer, we are done.
      if (!isset($this->next_marker) || !$this->fillFileBuffer()) {
        return false;
      }
    }

    // The file list might be empty if out next_marker was actually the last
    // file in the list.
    if (empty($this->current_file_list)) {
      return false;
    } else {
      return array_shift($this->current_file_list);
    }
  }

  /**
   * Rewind the directory handle to the first file that would have been returned
   * from opendir().
   *
   * @return bool <code>true</code> is successful, <code>false</code> otherwise.
   */
  public function dir_rewinddir() {
    // We could be more efficient if the user calls opendir() followed by
    // rewinddir() but you just can't help some people.
    $this->next_marker = null;
    $this->current_file_list = null;
    return true;
  }

  public function close() {
  }

  /**
   * Make a 'directory' in Google Cloud Storage.
   *
   * @param mixed $options A bitwise mask of values, such as
   * STREAM_MKDIR_RECURSIVE.
   *
   * @return bool <code>true</code> if the directory was created,
   * <code>false</code> otherwise.
   *
   * TODO: If the STREAM_MKDIR_RECURSIVE bit is not set in the options then we
   * should validate that the entire path exists before we create the directory.
   */
  public function mkdir($options) {
    $report_errors = ($options | STREAM_REPORT_ERRORS) != 0;
    $path = $this->getCorrectPathForDirectoryName();
    $headers = $this->getOAuthTokenHeader(parent::WRITE_SCOPE);
    if ($headers === false) {
      if ($report_errors) {
        trigger_error("Unable to acquire OAuth token.", E_USER_WARNING);
      }
      return false;
    }

    // Use x-goog-if-generation-match so we only create a new object.
    $headers['x-goog-if-generation-match'] = 0;
    $headers['Content-Range'] = sprintf(parent::FINAL_CONTENT_RANGE_NO_DATA, 0);
    $url = $this->createObjectUrl($this->bucket_name, $path);
    $http_response = $this->makeHttpRequest($url, "PUT", $headers);

    if (false === $http_response) {
      if ($report_errors) {
        trigger_error("Unable to connect to Google Cloud Storage Service.",
                      E_USER_WARNING);
      }
      return false;
    }

    // The status code precondition failed means that the 'directoy' already
    // existed.
    $status_code = $http_response['status_code'];
    if ($status_code != HttpResponse::OK &&
        $status_code != HttpResponse::PRECONDITION_FAILED) {
      if ($report_errors) {
        trigger_error($this->getErrorMessage($status_code,
                                             $http_response['body']),
                    E_USER_WARNING);
      }
      return false;
    }
    return ($status_code === HttpResponse::OK);
  }

  /**
   * Attempts to remove the directory . The directory must be empty. A
   * E_WARNING level error will be generated on failure.
   *
   * @param mixed $options A bitwise mask of values, such as
   * STREAM_MKDIR_RECURSIVE.
   *
   * @return bool <code>true</code> if the directory was removed,
   * <code>false</code> otherwise.
   */
  public function rmdir($options) {
    // We need to check that the 'directory' is empty before we can unlink it.
    // As we create a new instance of a CloudStorageDirectoryClient when
    // performing a rmdir(), all we need to check is that a readdir() returns
    // any value to know that the directory is not empty.
    if ($this->dir_readdir() !== false) {
      trigger_error('The directory is not empty.', E_USER_WARNING);
      return false;
    }

    $headers = $this->getOAuthTokenHeader(parent::WRITE_SCOPE);
    if ($headers === false) {
      if ($report_errors) {
        trigger_error("Unable to acquire OAuth token.", E_USER_WARNING);
      }
      return false;
    }

    $path = $this->getCorrectPathForDirectoryName();
    $url = $this->createObjectUrl($this->bucket_name, $path);
    $http_response = $this->makeHttpRequest($url, "DELETE", $headers);

    if (false === $http_response) {
      trigger_error("Unable to connect to Google Cloud Storage Service.",
                    E_USER_WARNING);
      return false;
    }

    if (HttpResponse::NO_CONTENT == $http_response['status_code']) {
      return true;
    } else {
      trigger_error($this->getErrorMessage($http_response['status_code'],
                                           $http_response['body']),
                    E_USER_WARNING);
      return false;
    }
  }

  private function fillFileBuffer() {
    $headers = $this->getOAuthTokenHeader(parent::READ_SCOPE);
    if ($headers === false) {
      trigger_error("Unable to acquire OAuth token.", E_USER_WARNING);
      return false;
    }

    $query_arr = [
        'delimiter' => parent::DELIMITER,
        'max-keys' => self::MAX_KEYS,
    ];
    if (isset($this->prefix)) {
      $query_arr['prefix'] = $this->prefix;
    }
    if (isset($this->next_marker)) {
      $query_arr['marker'] = $this->next_marker;
    }
    $query_str = http_build_query($query_arr);
    $url = $this->createObjectUrl($this->bucket_name);
    $http_response = $this->makeHttpRequest(sprintf("%s?%s", $url, $query_str),
                                            "GET",
                                            $headers);

    if (false === $http_response) {
      trigger_error("Unable to connect to Google Cloud Storage Service.",
                    E_USER_WARNING);
      return false;
    }
    $status_code = $http_response['status_code'];
    if (HttpResponse::OK != $status_code) {
      trigger_error($this->getErrorMessage($status_code,
                                           $http_response['body']),
                    E_USER_WARNING);
      return false;
    }

    // Extract the files into the result array.
    $xml = simplexml_load_string($http_response['body']);

    if (isset($xml->NextMarker)) {
      $this->next_marker = (string) $xml->NextMarker;
    } else {
      $this->next_marker = null;
    }

    if (is_null($this->current_file_list)) {
      $this->current_file_list = [];
    }

    $prefix_len = isset($this->prefix) ? strlen($this->prefix) : 0;
    foreach($xml->Contents as $content) {
      $key = (string) $content->Key;
      if ($prefix_len != 0) {
        $key = substr($key, $prefix_len);
      }
      // If the key ends with FOLDER_SUFFIX then replace that value with a '/'
      // to be consistent with the folder behaviour of Google Cloud Storage
      // Manager, which supports the creating of 'folders' in the UI. See
      // https://developers.google.com/storage/docs/gsmanager
      if (util\endsWith($key, self::FOLDER_SUFFIX)) {
        $key = substr_replace($key,
                              parent::DELIMITER,
                              -strlen(parent::FOLDER_SUFFIX));
      }
      array_push($this->current_file_list, $key);
    }
    return true;
  }

  private function getCorrectPathForDirectoryName() {
    // Replace the trailing MARKER from the prefix and replace it with the
    // FOLDER_SUFFIX.
    if (util\endsWith($this->object_name, parent::DELIMITER)) {
      return substr_replace($this->object_name,
                            parent::FOLDER_SUFFIX,
                            -strlen(parent::DELIMITER));
    } else {
      return $this->object_name . parent::FOLDER_SUFFIX;
    }
  }
}
