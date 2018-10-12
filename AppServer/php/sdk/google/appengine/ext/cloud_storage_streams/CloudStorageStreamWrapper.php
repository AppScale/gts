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
 * A user space stream wrapper for reading and writing to Google Cloud Storage.
 *
 * See: http://www.php.net/manual/en/class.streamwrapper.php
 *
 */

namespace google\appengine\ext\cloud_storage_streams;

require_once 'google/appengine/ext/cloud_storage_streams/CloudStorageClient.php';
require_once 'google/appengine/ext/cloud_storage_streams/CloudStorageDeleteClient.php';
require_once 'google/appengine/ext/cloud_storage_streams/CloudStorageDirectoryClient.php';
require_once 'google/appengine/ext/cloud_storage_streams/CloudStorageReadClient.php';
require_once 'google/appengine/ext/cloud_storage_streams/CloudStorageRenameClient.php';
require_once 'google/appengine/ext/cloud_storage_streams/CloudStorageUrlStatClient.php';
require_once 'google/appengine/ext/cloud_storage_streams/CloudStorageWriteClient.php';
require_once 'google/appengine/util/array_util.php';

use \google\appengine\util as util;
/**
 * Allowed stream_context options.
 * "anonymous": Boolean, if set then OAuth tokens will not be generated.
 * "acl": The ACL to apply when creating an object.
 * "Content-Type": The content type of the object being written.
 */
final class CloudStorageStreamWrapper {

  // The client instance that we're using to communicate with GS.
  private $client;

  // Must be public according to PHP documents - We capture the contents when
  // constructing objects.
  public $context;

  const ALLOWED_BUCKET_INI = "google_app_engine.allow_include_gs_buckets";
  const STREAM_OPEN_FOR_INCLUDE = 0x80;
  /**
   * Constructs a new stream wrapper.
   */
  public function __construct() {
  }

  /**
   * Destructs an existing stream wrapper.
   */
  public function __destruct() {
  }

  /**
   * Rename a cloud storage object.
   *
   * @return TRUE if the object was renamed, FALSE otherwise
   */
  public function rename($from, $to) {
    if (!$this->getBucketAndObjectFromPath($from, $from_bucket, $from_object) ||
        !isset($from_object)) {
      trigger_error(sprintf("Invalid Google Cloud Storage path: %s", $from),
                    E_USER_ERROR);
      return false;
    }
    if (!$this->getBucketAndObjectFromPath($to, $to_bucket, $to_object) ||
        !isset($to_object)) {
      trigger_error(sprintf("Invalid Google Cloud Storage path: %s", $to),
                    E_USER_ERROR);
      return false;
    }
    $client = new CloudStorageRenameClient($from_bucket,
                                           $from_object,
                                           $to_bucket,
                                           $to_object,
                                           $this->context);
    return $client->rename();
  }

  /**
   * All resources that were locked, or allocated, by the wrapper should be
   * released.
   *
   * No value is returned.
   */
  public function stream_close() {
    assert(isset($this->client));
    $this->client->close();
    $this->client = null;
  }

  /**
   * Tests for end-of-file on a file pointer.
   *
   * @return TRUE if the read/write position is at the end of the stream and if
   * no more data is available to be read, or FALSE otherwise
   */
  public function stream_eof() {
    assert(isset($this->client));
    return $this->client->eof();
  }

  /**
   * Flushes the output.
   *
   * @return TRUE if the cached data was successfully stored (or if there was
   * no data to store), or FALSE if the data could not be stored.
   */
  public function stream_flush() {
    assert(isset($this->client));
    return $this->client->flush();
  }

  public function stream_metadata($path, $option, $value) {
    return false;
  }

  public function stream_open($path, $mode, $options, &$opened_path) {
    if (!$this->getBucketAndObjectFromPath($path, $bucket, $object) ||
        !isset($object)) {
      if (($options & STREAM_REPORT_ERRORS) != 0) {
        trigger_error(sprintf("Invalid Google Cloud Storage path: %s", $path),
                E_USER_ERROR);
      }
      return false;
    }

    if (($options & self::STREAM_OPEN_FOR_INCLUDE) != 0) {
      $allowed_buckets = explode(",", ini_get(self::ALLOWED_BUCKET_INI));
      $include_allowed = false;
      foreach ($allowed_buckets as $bucket_name) {
        $bucket_name = trim($bucket_name);
        if ($bucket_name === $bucket) {
          $include_allowed = true;
          break;
        }
      }
      if (!$include_allowed) {
        if (($options & STREAM_REPORT_ERRORS) != 0) {
          trigger_error(
              sprintf("Not allowed to include/require from bucket '%s'",
                      $bucket),
              E_USER_ERROR);
        }
        return false;
      }
    }

    if ($mode === "r" || $mode === "rb") {
      $this->client = new CloudStorageReadClient($bucket,
                                                 $object,
                                                 $this->context);
    } else if ($mode === "w" || $mode === "wb") {
      $this->client = new CloudStorageWriteClient($bucket,
                                                  $object,
                                                  $this->context);
    } else {
      if (($options & STREAM_REPORT_ERRORS) != 0) {
        trigger_error(sprintf("Invalid mode: %s", $mode), E_USER_ERROR);
      }
      return false;
    }

    return $this->client->initialize();
  }

  /**
   * Read from a stream, return string of bytes.
   */
  public function stream_read($count) {
    assert(isset($this->client));
    return $this->client->read($count);
  }

  public function stream_seek($offset, $whence) {
    assert(isset($this->client));
    return $this->client->seek($offset, $whence);
  }

  public function stream_set_option($option, $arg1, $arg2) {
    assert(isset($this->client));
    return false;
  }

  public function stream_stat() {
    assert(isset($this->client));
    return $this->client->stat();
  }

  public function stream_tell() {
    assert(isset($this->client));
    return $this->client->tell();
  }

  /**
   * Return the number of bytes written.
   */
  public function stream_write($data) {
    assert(isset($this->client));
    return $this->client->write($data);
  }

  /**
   * Deletes a file. Called in response to unlink($filename).
   */
  public function unlink($path) {
    if (!$this->getBucketAndObjectFromPath($path, $bucket, $object) ||
        !isset($object)) {
      trigger_error(sprintf("Invalid Google Cloud Storage path: %s", $path),
              E_USER_ERROR);
      return false;
    }

    $this->client = new CloudStorageDeleteClient($bucket,
                                                 $object,
                                                 $this->context);
    return $this->client->delete();
  }

  public function url_stat($path, $flags) {
    if (!$this->getBucketAndObjectFromPath($path, $bucket, $object)) {
      if (($flags & STREAM_URL_STAT_QUIET) != 0) {
        trigger_error(sprintf("Invalid Google Cloud Storage path: %s", $path),
                E_USER_ERROR);
        return false;
      }
    }

    $client = new CloudStorageUrlStatClient($bucket,
                                            $object,
                                            $this->context,
                                            $flags);
    return $client->stat();
  }

  /**
   * Parse the supplied path and extract the bucket and object names from it.
   * It is possible that there is no object name in the path and a null will be
   * returned in the $object parameters if this is the case.
   */
  private function getBucketAndObjectFromPath($path, &$bucket, &$object) {
    // Decompose the $path into the GCS url components and check
    $url_parts = parse_url($path);

    if ($url_parts === false) {
      return false;
    }
    if ($url_parts['scheme'] !== 'gs' || empty($url_parts['host'])) {
      trigger_error(sprintf("Invalid Google Cloud Storage path: %s", $path),
                    E_USER_ERROR);
      return false;
    }
    $bucket = $url_parts['host'];
    $object = null;
    $path = util\FindByKeyOrNull($url_parts, 'path');
    if (isset($path) && $path !== "/") {
      $object = $path;
    }
    return true;
  }
}
