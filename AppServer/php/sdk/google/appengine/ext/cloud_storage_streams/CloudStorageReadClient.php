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
 * Google Cloud Storage Read Client - Implements only the methods required to
 * read bytes from GCS using stream wrappers. For a fully fledged client
 * to access Google Cloud Storage you should consult the Google API client.
 *
 */

namespace google\appengine\ext\cloud_storage_streams;

require_once 'google/appengine/ext/cloud_storage_streams/CloudStorageClient.php';
require_once 'google/appengine/ext/cloud_storage_streams/HttpResponse.php';

/**
 * Google Cloud Storage Client for reading objects.
 */
final class CloudStorageReadClient extends CloudStorageClient {
  // Buffer for storing data.
  private $read_buffer;

  // Position in the read buffer where we are currently
  private $buffer_read_position = 0;

  // Position in the object where the current block starts from
  private $object_block_start_position = 0;

  // Next position to read from when this buffer is finished.
  private $next_read_position = 0;

  // Overall size of the object in GCS
  private $object_total_length;

  // ETag of the object as it was first read.
  private $object_etag;

  // We have reached the end of the file while reading it.
  private $eof = false;

  // When we first read the file we partially complete the stat_result that
  // we then return in calls to stat()
  private $stat_result = [];

  // HTTP status codes that indicate that there is an object to read, and we
  // need to process the response.
  private static $valid_status_codes = [HttpResponse::OK,
                                        HttpResponse::PARTIAL_CONTENT,
                                        HttpResponse::RANGE_NOT_SATISFIABLE];

  // Client for caching the results of GCS reads.
  private $memcache_client;

  public function __construct($bucket, $object, $context) {
    parent::__construct($bucket, $object, $context);
    $this->memcache_client = new \Memcache();
  }

  public function __destruct() {
    parent::__destruct();
  }

  // Initialize is called when opening the stream. We will try and retrieve
  // the first chunk of the file during this stage, to validate that
  // - it exists
  // - the app has the ACL to access it.
  public function initialize() {
    return $this->fillReadBuffer(0);
  }

  /**
   * Read at most $count_bytes from the file.
   * If we have reached the end of the buffered amount, and there is more
   * data in the file then retreive more bytes from storage.
   */
  public function read($count_bytes) {
    // If we have data in the read_buffer then use it.
    $readBuffer_size = strlen($this->read_buffer);
    $bytes_available = $readBuffer_size - $this->buffer_read_position;

    // If there are no more bytes available then get some.
    if ($bytes_available === 0 && !$this->eof) {
      // If we know the object size, check it first.
      $object_bytes_read = $this->object_block_start_position +
                           $this->buffer_read_position;
      if ($object_bytes_read === $this->object_total_length ||
          !isset($this->next_read_position)) {
        $this->eof = true;
        return false;
      }
      if (!$this->fillReadBuffer($this->next_read_position)) {
        return false;
      }
      // Re-calculate the number of bytes we can serve.
      $readBuffer_size = strlen($this->read_buffer);
      $bytes_available = $readBuffer_size - $this->buffer_read_position;
    }

    if ($bytes_available > 0) {
      $bytes_to_read = min($bytes_available, $count_bytes);
      $current_buffer_position = $this->buffer_read_position;
      $this->buffer_read_position += $bytes_to_read;

      return substr($this->read_buffer,
                    $current_buffer_position,
                    $bytes_to_read);
    }

    return false;
  }

  /**
   * Returns true if we have read to the end of file, false otherwise.
   */
  public function eof() {
    return $this->eof;
  }

  /**
   * Seek within the current file. We only deal with SEEK_SET which we expect
   * the upper layers of PHP to convert and SEEK_CUR or SEEK_END calls to.
   */
  public function seek($offset, $whence) {
    if ($whence != SEEK_SET) {
      trigger_error(sprintf("Unsupported seek mode: %d", $whence),
                    E_USER_WARNING);
      return false;
    }
    // If we know the size, then make sure they are only seeking within it.
    if (isset($this->object_total_length) &&
        $offset > $this->object_total_length) {
      return false;
    }
    if ($offset < 0) {
      return false;
    }
    // Clear EOF and work it out next time they read.
    $this->eof = false;

    // Check if we can seek inside the current buffer
    $buffer_end = $this->object_block_start_position +
                  strlen($this->read_buffer);
    if ($this->object_block_start_position <= $offset && $offset < $buffer_end) {
      $this->buffer_read_position = $offset -
          $this->object_block_start_position;
    } else {
      $this->read_buffer = "";
      $this->buffer_read_position = 0;
      $this->next_read_position = $offset;
    }
    return true;
  }

  /**
   * Return our stat buffer, if we have one.
   */
  public function stat() {
    if (!empty($this->stat_result)) {
      return $this->stat_result;
    } else {
      return false;
    }
  }

  /**
   * Having tell() at this level in the stack seems bonkers.
   */
  public function tell() {
    return $this->buffer_read_position + $this->object_block_start_position;
  }

  /**
   * Override the makeHttpRequest function so we can implement caching.
   * If caching is enabled then we try and retrieve a matching request for the
   * object name and range from memcache.
   * If we find a result in memcache, and optimistic caching is enabled then
   * we return that result immediately without checking if the object has
   * changed in GCS. Otherwise, we will issue a 'If-None-Match' request with
   * the ETag of the object to ensure it is still current.
   *
   * Optimisitic caching is best suited when the application is soley updating
   * objects in cloud storage, as the cache can be invalidated when the object
   * is updated by the application.
   */
  protected function makeHttpRequest($url, $method, $headers, $body = null) {
    if (!$this->context_options['enable_cache']) {
      return parent::makeHttpRequest($url, $method, $headers, $body);
    }

    $cache_key = sprintf(parent::MEMCACHE_KEY_FORMAT, $url, $headers['Range']);
    $cache_obj = $this->memcache_client->get($cache_key);
    if (false !== $cache_obj) {
      if ($this->context_options['enable_optimistic_cache']) {
        return $cache_obj;
      } else {
        $cache_etag = $this->getHeaderValue('ETag', $cache_obj['headers']);
        if (array_key_exists('If-Match', $headers)) {
          // We will perform a If-None-Match to validate the cache object, only
          // if it has the same ETag value as what we are asking for.
          if ($headers['If-Match'] === $cache_etag) {
            unset($headers['If-Match']);
          } else {
            // We are asking for a different object that what is in the cache.
            $cache_etag = null;
          }
        }
      }
      if (isset($cache_etag)) {
        $headers['If-None-Match'] = $cache_etag;
      }
    }

    $result = parent::makeHttpRequest($url, $method, $headers, $body);

    if (false === $result) {
      return false;
    }
    $status_code = $result['status_code'];
    if (HttpResponse::NOT_MODIFIED === $result['status_code']) {
      return $cache_obj;
    }
    if (in_array($status_code, self::$valid_status_codes)) {
      $this->memcache_client->set($cache_key, $result, 0,
          $this->context_options['cache_expiry_seconds']);
    }
    return $result;
  }

  /**
   * Fill our internal buffer with data, by making a http request to Google
   * Cloud Storage.
   */
  private function fillReadBuffer($read_position) {
    $headers = $this->getOAuthTokenHeader(parent::READ_SCOPE);
    if ($headers === false) {
      trigger_error("Unable to acquire OAuth token.", E_USER_WARNING);
      return false;
    }

    $end_range = $read_position + parent::DEFAULT_READ_SIZE - 1;
    $range = $this->getRangeHeader($read_position, $end_range);
    $headers = array_merge($headers, $range);

    // If we have an ETag from the first read then use it to ensure we are
    // retrieving the same object.
    if (isset($this->object_etag)) {
      $headers["If-Match"] = $this->object_etag;
    }

    $http_response = $this->makeHttpRequest($this->url,
                                            "GET",
                                            $headers);

    if ($http_response === false) {
      trigger_error("Unable to connect to Google Cloud Storage Service.",
                    E_USER_WARNING);
      return false;
    }

    $status_code = $http_response['status_code'];
    if ($status_code === HttpResponse::NOT_FOUND) {
      return false;
    }
    if ($status_code === HttpResponse::PRECONDITION_FAILED) {
      trigger_error("Object content has changed.", E_USER_WARNING);
      return false;
    }

    if (!in_array($status_code, self::$valid_status_codes)) {
      trigger_error($this->getErrorMessage($status_code,
                                           $http_response['body']),
                    E_USER_WARNING);
      return false;
    }

    $this->read_buffer = $http_response['body'];
    $this->buffer_read_position = 0;
    $this->object_block_start_position = $read_position;

    // If we got the complete object in the response then use the
    // Content-Length
    if ($status_code == HttpResponse::OK) {
      $content_length = $this->getHeaderValue('Content-Length',
                                              $http_response['headers']);
      assert(isset($content_length));
      $this->object_total_length = intval($content_length);
      $this->next_read_position = null;
    } else if ($status_code == HttpResponse::RANGE_NOT_SATISFIABLE) {
      // We've read past the end of the object ... no more data.
      $this->read_buffer = "";
      $this->eof = true;
      $this->next_read_position = null;
      if (!isset($this->object_total_length)) {
        $this->object_total_length = 0;
      }
    } else {
      $content_range = $this->getHeaderValue('Content-Range',
                                             $http_response['headers']);
      assert(isset($content_range));
      if (preg_match(parent::CONTENT_RANGE_REGEX, $content_range, $m) === 1) {
        $this->next_read_position = intval($m[2]) + 1;
        $this->object_total_length = intval($m[3]);
      }
    }

    $this->object_etag =
        $this->getHeaderValue('ETag', $http_response['headers']);

    if (empty($this->stat_result)) {
      $stat_args = ['size' => $this->object_total_length,
                    'mode' => parent::S_IFREG];

      $last_modified = $this->getHeaderValue('Last-Modified',
                                             $http_response['headers']);
      if (isset($last_modified)) {
        $unix_time = strtotime($last_modified);
        if ($unix_time !== false) {
          $stat_args["mtime"] = $unix_time;
        }
      }
      $this->stat_result = $this->createStatArray($stat_args);
    }

    return true;
  }
}

