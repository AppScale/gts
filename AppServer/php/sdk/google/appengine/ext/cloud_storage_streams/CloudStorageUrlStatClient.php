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
 * Cloud Storage Url Stat Client handles stat() calls for objects and buckets.
 *
 */

namespace google\appengine\ext\cloud_storage_streams;

require_once 'google/appengine/ext/cloud_storage_streams/CloudStorageClient.php';

/**
 * Client for deleting objects from Google Cloud Storage.
 */
final class CloudStorageUrlStatClient extends CloudStorageClient {
  private $quiet;

  public function __construct($bucket, $object, $context, $flags) {
    parent::__construct($bucket, $object, $context);
    $this->quiet = ($flags & STREAM_URL_STAT_QUIET) == STREAM_URL_STAT_QUIET;
  }

  public function stat() {
    $headers = $this->getOAuthTokenHeader(parent::WRITE_SCOPE);
    if ($headers === false) {
      if (!$this->quiet) {
        trigger_error("Unable to acquire OAuth token.", E_USER_WARNING);
      }
      return false;
    }

    $http_response = $this->makeHttpRequest($this->url, "HEAD", $headers);
    if ($http_response === false) {
      if (!$this->quiet) {
        trigger_error($this->getErrorMessage($http_response['status_code'],
                                             $http_response['body']),
                      E_USER_WARNING);
      }
      return false;
    }
    $status_code = $http_response['status_code'];

    // TODO: Implement retry.
    if ($status_code != HttpResponse::OK) {
      return false;
    }

    $mode = isset($this->object_name) ? parent::S_IFREG : parent::S_IFDIR;

    // If the app could stat the file, then it must be readable.
    $mode |= parent::S_IRUSR;

    $stat_args["mode"] = $mode;

    $last_modified = $this->getHeaderValue('Last-Modified',
                                           $http_response['headers']);
    if (isset($last_modified)) {
      $unix_time = strtotime($last_modified);
      if ($unix_time !== false) {
        $stat_args["mtime"] = $unix_time;
      }
    }

    $content_length = $this->getHeaderValue('Content-Length',
                                            $http_response['headers']);

    if (isset($content_length)) {
      $stat_args["size"] = intval($content_length);
    }

    return $this->createStatArray($stat_args);
  }
}

