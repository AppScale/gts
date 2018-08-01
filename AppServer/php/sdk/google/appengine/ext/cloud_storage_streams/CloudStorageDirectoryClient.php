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

/**
 * Client for deleting objects from Google Cloud Storage.
 */
final class CloudStorageDirectoryClient extends CloudStorageClient {

  // A character or multiple characters that can be used to simplify a list of
  // objects that use a directory-like naming scheme. Can be used in conjunction
  // with a prefix.
  const DELIMITER = '/';

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
    parent::__construct($bucket_name, null, $context);
    // Ignore the leading slash
    if (isset($object_prefix)) {
      $this->prefix = substr($object_prefix, 1);
    }
  }

  /**
   * Make the initial connection to GCS and fill the read buffer with files.
   *
   * @return bool TRUE if we can connect to the Cloud Storage bucket, FALSE
   * otherwise.
   */
  public function initialise() {
    return $this->fillFileBuffer();
  }

  /**
   * Read the next file in the directory list. If the list is empty and we
   * believe that there are more results to read then fetch them
   *
   * @return string The name of the next file in the directory, FALSE if there
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
   * @return bool True is successful, False otherwise.
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

  private function fillFileBuffer() {
    $headers = $this->getOAuthTokenHeader(parent::READ_SCOPE);
    if ($headers === false) {
      trigger_error("Unable to acquire OAuth token.", E_USER_WARNING);
      return false;
    }

    $query_arr = [
        'delimiter' => self::DELIMITER,
        'max-keys' => self::MAX_KEYS,
    ];
    if (isset($this->prefix)) {
      $query_arr['prefix'] = $this->prefix;
    }
    if (isset($this->next_marker)) {
      $query_arr['marker'] = $this->next_marker;
    }
    $query_str = http_build_query($query_arr);
    $http_response = $this->makeHttpRequest(sprintf("%s?%s",
                                                    $this->url,
                                                    $query_str),
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

    foreach($xml->Contents as $content) {
      array_push($this->current_file_list, (string) $content->Key);
    }

    return true;
  }
}
