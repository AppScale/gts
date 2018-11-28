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
 * Cloud Storage Rename Client handles rename() calls for renaming a GCS object.
 *
 */

namespace google\appengine\ext\cloud_storage_streams;

require_once 'google/appengine/ext/cloud_storage_streams/CloudStorageClient.php';

/**
 * Client for deleting objects from Google Cloud Storage.
 */
final class CloudStorageRenameClient extends CloudStorageClient {
  private $from_bucket;
  private $from_object;
  private $to_bucket;
  private $to_object;

  public function __construct($from_bucket,
                              $from_object,
                              $to_bucket,
                              $to_object,
                              $context) {
    parent::__construct($from_bucket, $from_object, $context);

    $this->from_bucket = $from_bucket;
    $this->from_object = $from_object;
    $this->to_bucket = $to_bucket;
    $this->to_object = $to_object;
  }

  /**
   * Perform the actual rename of a GCS storage object.
   * Renaming an object has the following steps.
   * 1. stat the 'from' object to get the ETag and content type.
   * 2. Use x-goog-copy-source-if-match to copy the object.
   * 3. Delete the original object.
   */
  public function rename() {
    $token_header = $this->getOAuthTokenHeader(parent::WRITE_SCOPE);
    if ($token_header === false) {
      if (!$this->quiet) {
        trigger_error("Unable to acquire OAuth token.", E_USER_WARNING);
      }
      return false;
    }

    // Stat the from object to get the etag and content-type
    $http_response = $this->makeHttpRequest($this->url, "HEAD", $token_header);
    if ($http_response === false) {
      trigger_error("Unable to connect to Google Cloud Storage Service.",
                    E_USER_WARNING);
      return false;
    }
    $status_code = $http_response['status_code'];

    if ($status_code != HttpResponse::OK) {
      trigger_error(sprintf("Unable to rename: %s. Cloud Storage Error: %s",
                            sprintf("gs://%s%s",
                                    $this->to_bucket,
                                    $this->to_object),
                            HttpResponse::getStatusMessage($status_code)),
                    E_USER_WARNING);
      return false;
    }

    $from_etag = $this->getHeaderValue('ETag', $http_response['headers']);
    $content_type = $this->getHeaderValue('Content-Type',
                                          $http_response['headers']);

    $copy_headers = [
        'x-goog-copy-source' =>
            sprintf("/%s%s", $this->from_bucket, $this->from_object),
        'x-goog-copy-source-if-match' => $from_etag,
        'content-type' => $content_type,
        'x-goog-metadata-directive' => 'COPY',
    ];

    if (array_key_exists("acl", $this->context_options)) {
      $acl = $this->context_options["acl"];
      if (in_array($acl, parent::$valid_acl_values)) {
        $copy_headers["x-goog-acl"] = $acl;
      } else {
        trigger_error(sprintf("Invalid ACL value: %s", $acl), E_USER_WARNING);
        return false;
      }
    }

    $to_url = $this->createObjectUrl($this->to_bucket, $this->to_object);
    $http_response = $this->makeHttpRequest($to_url, "PUT",
        array_merge($token_header, $copy_headers));

    if ($http_response === false) {
      trigger_error("Unable to copy source to destination.", E_USER_WARNING);
      return false;
    }

    $status_code = $http_response['status_code'];
    if ($status_code != HttpResponse::OK) {
      trigger_error(sprintf("Error copying to %s. Cloud Storage Error: %s",
                            sprintf("gs://%s%s",
                                    $this->to_bucket,
                                    $this->to_object),
                            HttpResponse::getStatusMessage($status_code)),
                    E_USER_WARNING);
      return false;
    }
    // Unlink the original file.
    $http_response = $this->makeHttpRequest($this->url,
                                            "DELETE",
                                            $token_header);

    if ($http_response === false) {
      trigger_error("Failed to delete the from cloud storage object.",
                    E_USER_WARNING);
      return false;
    }

    $status_code = $http_response['status_code'];
    if ($status_code !== HttpResponse::NO_CONTENT) {
      trigger_error(sprintf("Unable to unlink: %s. Cloud Storage Error: %s",
                            sprintf("gs://%s%s",
                                    $this->from_bucket,
                                    $this->from_object),
                            HttpResponse::getStatusMessage($status_code)),
                    E_USER_WARNING);
      return false;
    }

    return true;
  }
}
