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
 * Blobstore Service allows the user to create and serve blobs.
 *
 */

namespace google\appengine\api\blobstore;

use \google\appengine\BlobstoreServiceError\ErrorCode;
use \google\appengine\CreateEncodedGoogleStorageKeyRequest;
use \google\appengine\CreateEncodedGoogleStorageKeyResponse;
use \google\appengine\CreateUploadURLRequest;
use \google\appengine\CreateUploadURLResponse;
use \google\appengine\files\GetDefaultGsBucketNameRequest;
use \google\appengine\files\GetDefaultGsBucketNameResponse;
use \google\appengine\runtime\ApiProxy;
use \google\appengine\runtime\ApplicationError;
use \google\appengine\util as util;

require_once 'google/appengine/api/blobstore/blobstore_service_pb.php';
require_once 'google/appengine/api/blobstore/BlobstoreException.php';
require_once 'google/appengine/api/files/file_service_pb.php';
require_once 'google/appengine/runtime/ApiProxy.php';
require_once 'google/appengine/runtime/ApplicationError.php';
require_once 'google/appengine/util/array_util.php';



class BlobstoreService {
  const GCS_PREFIX = 'gcs://';
  const BLOB_KEY_HEADER = "X-AppEngine-BlobKey";
  const BLOB_RANGE_HEADER = "X-AppEngine-BlobRange";
  /**
   * The list of options that can be supplied to createUploadUrl.
   * @see BlobstoreService::createUploadUrl()
   * @var array
   */
  static $create_upload_url_options = ['gs_bucket_name', 'max_bytes_per_blob',
      'max_bytes_total'];

  /**
   * The list of options that can be suppied to serve.
   * @var array
   */
  static $serve_options = ['content_type', 'save_as', 'start', 'end',
      'use_range'];

  /**
   * Workaround for the 'Cannot modify header information' problem when
   * trying to send headers from unit tests. If set, then $send_header is
   * expected to be a closure that accepts a key, value pair where key is the
   * header name, and value is the header value.
   */
  static $send_header = null;

  /**
   * Create an absolute URL that can be used by a user to asynchronously upload
   * a large blob. Upon completion of the upload, a callback is made to the
   * specified URL.
   *
   * @param string $success_path A relative URL which will be invoked after the
   * user successfully uploads a blob.
   * @param mixed[] $options A key value pair array of upload options. Valid
   * options are:
   * - max_bytes_per_blob: an integer value of the largest size that any one
   *   uploaded blob may be. Default value: unlimited.
   * - max_bytes_total: an integer value that is the total size that sum of all
   *   uploaded blobs may be. Default value: unlimited.
   * - gs_bucket_name: a string that is the name of a Google Cloud Storage
   *   bucket that the blobs should be uploaded to. Not specifying a value
   *   will result in the blob being uploaded to the application's default
   *   bucket.
   *
   * @return string The upload URL.
   *
   * @throws InvalidArgumentException If $success_path is not valid, or one of
   * the options is not valid.
   * @throws BlobstoreException Thrown when there is a failure using the
   * blobstore service.
   */
  public static function createUploadUrl($success_path, $options=array()) {
    $req = new CreateUploadURLRequest();
    $resp = new CreateUploadURLResponse();

    if (!is_string($success_path)) {
      throw new \InvalidArgumentException('$success_path must be a string');
    }

    $req->setSuccessPath($success_path);

    if (array_key_exists('max_bytes_per_blob', $options)) {
      $val = $options['max_bytes_per_blob'];
      if (!is_int($val)) {
        throw new \InvalidArgumentException(
            'max_bytes_per_blob must be an integer');
      }
      if ($val < 1) {
        throw new \InvalidArgumentException(
            'max_bytes_per_blob must be positive.');
      }
      $req->setMaxUploadSizePerBlobBytes($val);
    }

    if (array_key_exists('max_bytes_total', $options)) {
      $val = $options['max_bytes_total'];
      if (!is_int($val)) {
        throw new \InvalidArgumentException(
            'max_bytes_total must be an integer');
      }
      if ($val < 1) {
        throw new \InvalidArgumentException(
            'max_bytes_total must be positive.');
      }
      $req->setMaxUploadSizeBytes($val);
    }

    if (array_key_exists('gs_bucket_name', $options)) {
      $val = $options['gs_bucket_name'];
      if (!is_string($val)) {
        throw new \InvalidArgumentException('gs_bucket_name must be a string');
      }
      $req->setGsBucketName($val);
    } else {
      $bucket = BlobstoreService::getDefaultGoogleStorageBucketName();

      if (!$bucket) {
        throw new \InvalidArgumentException(
            'Application does not have a default Cloud Storage Bucket, ' .
            'gs_bucket_name must be specified');
      }
      $req->setGsBucketName($bucket);
    }

    $extra_options = array_diff(array_keys($options),
                                self::$create_upload_url_options);

    if (!empty($extra_options)) {
      throw new \InvalidArgumentException('Invalid options supplied: ' .
          implode(',', $extra_options));
    }

    try {
      ApiProxy::makeSyncCall('blobstore', 'CreateUploadURL', $req, $resp);
    } catch (ApplicationError $e) {
      throw BlobstoreService::ApplicationErrorToException($e);
    }
    return $resp->getUrl();
  }

  /**
   * Create a blob key for a Google Cloud Storage file.
   *
   * @param string $filename The google cloud storage filename, in the format
   * gcs://bucket_name/object_name
   *
   * @return string A blob key for this filename that can be used in other API
   * calls.
   *
   * @throws InvalidArgumentException if the filename is not in the correct
   * format.
   * @throws BlobstoreException If there was a problem contacting the
   * service.
   */
  public static function createGsKey($filename) {
    if (!is_string($filename)) {
      throw new \InvalidArgumentException('filename must be a string.');
    }

    $gcs_prefix_len = strlen(self::GCS_PREFIX);

    if (strncmp($filename, self::GCS_PREFIX, $gcs_prefix_len) != 0) {
      throw new \InvalidArgumentException(
          sprintf('filename must start with the prefix %s.', self::GCS_PREFIX));
    }

    $gcs_filename = substr($filename, $gcs_prefix_len);

    if (!strpos($gcs_filename, "/")) {
      throw new \InvalidArgumentException(
        'filename not in the format gcs://bucket_name/object_name.');
    }

    $gcs_filename = sprintf('/gs/%s', $gcs_filename);

    $request = new CreateEncodedGoogleStorageKeyRequest();
    $response = new CreateEncodedGoogleStorageKeyResponse();

    $request->setFilename($gcs_filename);

    try {
      ApiProxy::makeSyncCall('blobstore',
                             'CreateEncodedGoogleStorageKey',
                             $request,
                             $response);
    } catch (ApplicationError $e) {
      throw BlobstoreService::ApplicationErrorToException($e);
    }

    return $response->getBlobKey();
  }

  /**
   * Serve a Google Cloud Storage file as the response.
   *
   * @param string $gcs_filename The name of the Google Cloud Storage object to
   * serve.
   * @param mixed $options Array of additional options for serving the object.
   *   content_type: Content-Type to override when known.
   *   save_as: If True then send the file as an attachment.
   *   start: Start index of content-range to send.
   *   end: End index of content-range to send. End index is inclusive.
   *   use_range: Use provided content range from the request's Range header.
   *     Mutually exclusive with start and end.
   *
   * @throws InvalidArgumentException If invalid options are supplied.
   */
  public static function serve($gcs_filename, $options = []) {
    $extra_options = array_diff(array_keys($options), self::$serve_options);

    if (!empty($extra_options)) {
      throw new \InvalidArgumentException('Invalid options supplied: ' .
          implode(',', $extra_options));
    }

    // Determine the range to send
    $start = util\FindByKeyOrNull($options, "start");
    $end = util\FindByKeyOrNull($options, "end");
    $use_range = util\FindByKeyOrNull($options, "use_range");
    $request_range_header = util\FindByKeyOrNull($_SERVER, "HTTP_RANGE");

    $range_header = BlobstoreService::checkRanges($start,
                                                  $end,
                                                  $use_range,
                                                  $request_range_header);

    $save_as = util\FindByKeyOrNull($options, "save_as");
    if (isset($save_as) && !is_string($save_as)) {
      throw new \InvalidArgumentException("Unexpected value for save_as.");
    }

    $blob_key = BlobstoreService::createGsKey($gcs_filename);
    BlobstoreService::sendHeader(self::BLOB_KEY_HEADER, $blob_key);

    if (isset($range_header)) {
      BlobstoreService::sendHeader(self::BLOB_RANGE_HEADER, $range_header);
    }

    $content_type = util\FindByKeyOrNull($options, "content_type");
    if (isset($content_type)) {
      BlobstoreService::sendHeader("Content-Type", $content_type);
    }

    if (isset($save_as)) {
      BlobstoreService::sendHeader("Content-Disposition", sprintf(
          "attachment; filename=%s", $save_as));
    }
  }

  /**
   * Return the name of the default Google Cloud Storage bucket for the
   * application, if one has been configured.
   *
   * @return string The bucket name, or an empty string if no bucket has been
   * configured.
   */
  public static function getDefaultGoogleStorageBucketName() {
    $request = new GetDefaultGsBucketNameRequest();
    $response = new GetDefaultGsBucketNameResponse();

    ApiProxy::makeSyncCall('file',
                           'GetDefaultGsBucketName',
                           $request,
                           $response);

    return $response->getDefaultGsBucketName();
  }

  /**
   * This function is used for unit testing only, it allows replacement of the
   * send_header function that is used to set headers on the response.
   *
   * @param mixed $new_header_func The function to use to set response headers.
   * Set to null to use the inbuilt PHP method header().
   */
  public static function setSendHeaderFunction($new_header_func) {
    self::$send_header = $new_header_func;
  }

  /**
   * @access private
   */
  private static function ApplicationErrorToException($error) {
    switch($error->getApplicationError()) {
      case ErrorCode::URL_TOO_LONG:
        return new \InvalidArgumentException(
            'The upload URL supplied was too long.');
      case ErrorCode::PERMISSION_DENIED:
        return new BlobstoreException('Permission Denied');
      case ErrorCode::ARGUMENT_OUT_OF_RANGE:
        return new \InvalidArgumentException($error->getMessage());
      default:
        return new BlobstoreException(
            'Error Code: ' . $error->getApplicationError());
    }
  }

  /**
   * @access private
   */
  private static function checkRanges($start, $end, $use_range, $range_header) {
    if ($end && !$start) {
      throw new \InvalidArgumentException(
        "May not specify an end range value without a start value.");
    }

    $use_indexes = isset($start);
    if ($use_indexes) {
      if (isset($end)) {
        if ($start > $end) {
          throw new \InvalidArgumentException(
              sprintf(
                  "Start range (%d) cannot be greater than the end range (%d).",
                  $start,
                  $end));
        }
        if ($start < 0) {
          throw new \InvalidArgumentException(
              sprintf("The start range (%d) cannot be less than 0.", $start));
        }
      }
      $range_indexes = BlobstoreService::serializeRange($start, $end);
    }

    // If both headers and index parameters are in use they must be the same.
    if ($use_range && $use_indexes) {
      if (strcmp($range_header, $range_indexes) != 0) {
        throw new \InvalidArgumentException(
            sprintf("May not provide non-equivalent range indexes and " .
                    "range headers: (header) %s != (indexes) %s.",
                    $range_header,
                    $range_indexes));
      }
    }

    if ($use_range && isset($range_header)) {
      return $range_header;
    } else if ($use_indexes) {
      return $range_indexes;
    } else {
      return null;
    }
  }

  /**
   * @access private
   */
  private static function serializeRange($start, $end) {
    if ($start < 0) {
      $range_str = sprintf('%d', $start);
    } else if (!isset($end)) {
      $range_str = sprintf("%d-", $start);
    } else {
      $range_str = sprintf("%d-%d", $start, $end);
    }
    return sprintf("bytes=%s", $range_str);
  }

  /**
   * @access private
   */
  private static function sendHeader($key, $value) {
    if (isset(self::$send_header)) {
      call_user_func(self::$send_header, $key, $value);
    } else {
      header(sprintf("%s: %s", $key, $value));
    }
  }
}
