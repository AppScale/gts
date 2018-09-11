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
 * Cloud Storage Write Client implements the stream wrapper functions required
 * to write to a Google Cloud Storage object.
 *
 */

namespace google\appengine\ext\cloud_storage_streams;

require_once 'google/appengine/ext/cloud_storage_streams/CloudStorageClient.php';

// TODO: Retry on transient errors.

final class CloudStorageWriteClient extends CloudStorageClient {
  // GS requires all chunks of data written to be multiples of 256K except for
  // the last chunk.
  const WRITE_CHUNK_SIZE = 262144;

  // Content Range Header format when the total length is unknown.
  const PARTIAL_CONTENT_RANGE_FORMAT = "bytes %d-%d/*";

  // Content Range Header format when the length is known.
  const FINAL_CONTENT_RANGE_FORMAT = "bytes %d-%d/%d";

  // Content Range Header for final chunk with no new data
  const FINAL_CONTENT_RANGE_NO_DATA = "bytes */%d";

  private static $upload_start_header = ["x-goog-resumable" => "start"];

  // The array of bytes to be written to GS
  private $byte_buffer;

  // The resumable upload ID we are using for this upload.
  private $upload_id;

  // The offset in the file where the current buffer starts
  private $buffer_start_offset;

  // The number of bytes we've written to GS so far.
  private $total_bytes_uploaded;

  public function __construct($bucket, $object, $context) {
    parent::__construct($bucket, $object, $context);
  }

  /**
   * Called when the stream is being opened. Try and start a resumable upload
   * here.
   *
   * @return true if the streamable upload started, false otherwise.
   */
  public function initialize() {
    $headers = self::$upload_start_header;

    $token_header = $this->getOAuthTokenHeader(parent::WRITE_SCOPE);
    if ($token_header === false) {
      trigger_error("Unable to acquire OAuth token.", E_USER_WARNING);
      return false;
    }
    $headers = array_merge($headers, $token_header);

    if (array_key_exists("Content-Type", $this->context_options)) {
      $headers["Content-Type"] = $this->context_options["Content-Type"];
    }

    if (array_key_exists("acl", $this->context_options)) {
      $acl = $this->context_options["acl"];
      if (in_array($acl, parent::$valid_acl_values)) {
        $headers["x-goog-acl"] = $acl;
      } else {
        trigger_error(sprintf("Invalid ACL value: %s", $acl), E_USER_WARNING);
        return false;
      }
    }

    $http_response = $this->makeHttpRequest($this->url,
                                            "POST",
                                            $headers);

    if ($http_response === false) {
      trigger_error("Unable to connect to Google Cloud Storage Service.",
                    E_USER_WARNING);
      return false;
    }

    $status_code = $http_response['status_code'];
    if ($status_code == HttpResponse::FORBIDDEN) {
      trigger_error("Access Denied", E_USER_WARNING);
      return false;
    }
    if ($status_code != HttpResponse::CREATED) {
      trigger_error(sprintf("Error connecting to Google Cloud Storage: %s",
                            HttpResponse::getStatusMessage($status_code)),
                    E_USER_WARNING);
      return false;
    }

    $location = $this->getHeaderValue("Location", $http_response['headers']);

    $query_str = parse_url($location)["query"];
    parse_str($query_str, $query_arr);
    $this->upload_id = $query_arr["upload_id"];

    if (!isset($this->upload_id)) {
      trigger_error(sprintf("Location Header was not returned (%s).",
                            implode(",",
                                    array_keys($http_response['headers']))),
                    E_USER_WARNING);
      return false;
    }

    $this->buffer_start_offset = 0;
    $this->total_bytes_uploaded = 0;
    $this->byte_buffer = "";
    return true;
  }

  /**
   * Return the number of bytes written.
   */
  public function write($data) {
    $this->byte_buffer .= $data;
    $current_buffer_len = strlen($this->byte_buffer);
    $data_len = strlen($data);
    // If this data doesn't fill the buffer then write it and return.
    if ($current_buffer_len < self::WRITE_CHUNK_SIZE) {
      return $data_len;
    }

    // Write out this data
    if (!$this->writeBufferToGS()) {
      // Remove the bytes we added to the buffer
      $this->byte_buffer = substr($this->byte_buffer, 0, -strlen($data));
      return 0;
    }

    // We wrote the buffered content - but only return the amount of $data
    // we wrote as per the contract of write()
    return $data_len;
  }

  /**
   * Because of the write byte alignment required by GS we will not write any
   * data on a flush. If there is data remaining in the buffer we'll write it
   * during close.
   */
  public function flush() {
    return true;
  }

  /**
   * When closing the stream we need to complete the upload.
   */
  public function close() {
    $this->writeBufferToGS(true);
  }

  private function writeBufferToGS($complete = false) {
    $headers = $this->getOAuthTokenHeader(parent::WRITE_SCOPE);
    if ($headers === false) {
      trigger_error("Unable to acquire OAuth token.", E_USER_ERROR);
      return false;
    }

    $buffer_len = strlen($this->byte_buffer);

    if ($complete) {
      $write_size = $buffer_len;
    } else {
      // Incomplete writes should never be less than WRITE_CHUNK_SIZE
      assert($buffer_len >= self::WRITE_CHUNK_SIZE);
      // Is PHP the only language in the world where the quotient of two
      // integers is a double?
      $write_size =
          floor($buffer_len / self::WRITE_CHUNK_SIZE) * self::WRITE_CHUNK_SIZE;
    }

    // Determine the final byte of the buffer we're writing for Range header.
    if ($write_size !== 0) {
      $write_end_byte = $this->buffer_start_offset + $write_size - 1;
      $body = substr($this->byte_buffer, 0, $write_size);
    } else {
      $body = null;
    }

    if ($complete) {
      $object_length = $this->buffer_start_offset + $write_size;
      if ($write_size === 0) {
        $headers['Content-Range'] = sprintf(self::FINAL_CONTENT_RANGE_NO_DATA,
                                            $object_length);
      } else {
        $headers['Content-Range'] = sprintf(self::FINAL_CONTENT_RANGE_FORMAT,
                                            $this->buffer_start_offset,
                                            $write_end_byte,
                                            $object_length);
      }
    } else {
      $headers['Content-Range'] = sprintf(self::PARTIAL_CONTENT_RANGE_FORMAT,
                                          $this->buffer_start_offset,
                                          $write_end_byte);
    }

    $url = sprintf("%s?upload_id=%s", $this->url, $this->upload_id);
    $http_response = $this->makeHttpRequest($url, "PUT", $headers, $body);
    $code = $http_response['status_code'];

    // TODO: Retry on some status codes.
    if (($complete && $code != HttpResponse::OK) ||
        (!$complete && $code != HttpResponse::RESUME_INCOMPLETE)) {
      trigger_error(
          sprintf("Error writing to Google Cloud Storage Service: %s",
                  HttpResponse::getStatusMessage($code)),
          E_USER_WARNING);
      return false;
    }
    // Buffer flushed, update pointers if we actually wrote something.
    if ($write_size !== 0) {
      $this->buffer_start_offset = $write_end_byte + 1;
      $this->byte_buffer = substr($this->byte_buffer, $write_size);
    }
    return true;
  }
}

