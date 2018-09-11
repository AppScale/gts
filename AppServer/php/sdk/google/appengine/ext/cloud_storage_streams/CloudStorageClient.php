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
 * CloudStorageClient is the base class for classes that are used to communicate
 * with Google Cloud Storage via the PHP streams interface.
 *
 */

namespace google\appengine\ext\cloud_storage_streams;

require_once 'google/appengine/api/app_identity/AppIdentityService.php';
require_once 'google/appengine/api/urlfetch_service_pb.php';
require_once 'google/appengine/ext/cloud_storage_streams/HttpResponse.php';
require_once 'google/appengine/runtime/ApiProxy.php';
require_once 'google/appengine/runtime/ApplicationError.php';
require_once 'google/appengine/util/array_util.php';

use \google\appengine\api\app_identity\AppIdentityService;
use \google\appengine\api\app_identity\AppIdentityException;
use \google\appengine\runtime\ApiProxy;
use \google\appengine\runtime\ApplicationError;
use \google\appengine\URLFetchRequest\RequestMethod;
use \google\appengine\util as util;

/**
 * CloudStorageClient provides default fail implementations for all of the
 * methods that the stream wrapper might potentially call. Derived classes then
 * only implement the methods that are relevant to the operations that they
 * perform.
 */
abstract class CloudStorageClient {
  // Token scopers for accessing objects in Google Cloud Storage
  const READ_SCOPE = "https://www.googleapis.com/auth/devstorage.read_only";
  const WRITE_SCOPE = "https://www.googleapis.com/auth/devstorage.read_write";
  const FULL_SCOPE = "https://www.googleapis.com/auth/devstorage.full_control";

  // The storage host when running in the dev appserver.
  const LOCAL_HOST = "gcs-magicstring.appspot.com";

  // The storage host when running in production.
  const PRODUCTION_HOST = "storage.googleapis.com";

  // URL format for making requests for objects inside a bucket.
  const BUCKET_OBJECT_FORMAT = "https://%s/%s%s";

  // URL format for making requests for buckets only.
  const BUCKET_FORMAT = "https://%s/%s";

  // Format for the OAuth token header.
  const OAUTH_TOKEN_FORMAT = "OAuth %s";

  // Bit fields for the stat mode field
  const S_IFREG = 0100000;
  const S_IFDIR = 0040000;

  const S_IRWXU = 00700;  //  mask for owner permissions
  const S_IRUSR = 00400;  //  owner: read permission
  const S_IWUSR = 00200;  //  owner: write permission
  const S_IXUSR = 00100;  //  owner: execute permission

  // The API version header
  private static $api_version_header = ["x-goog-api-version" => 2];

  // Regex patterm for retrieving the Length of the content being served.
  const CONTENT_RANGE_REGEX = "/bytes\s+(\d+)-(\d+)\/(\d+)/i";

  // HTTP status codes that should be retried if they are returned by a request
  // to GCS. Retry should occur with a random exponential back-off.
  protected static $retry_error_codes = [HttpResponse::REQUEST_TIMEOUT,
                                         HttpResponse::INTERNAL_SERVER_ERROR,
                                         HttpResponse::BAD_GATEWAY,
                                         HttpResponse::SERVICE_UNAVAILABLE,
                                         HttpResponse::GATEWAY_TIMEOUT];

  // Values that are allowed to be supplied as ACLs when writing objects.
  protected static $valid_acl_values = ["private",
                                        "public-read",
                                        "public-read-write",
                                        "authenticated-read",
                                        "bucket-owner-read",
                                        "bucket-owner-full-control"];

  // Map HTTP request types to URLFetch method enum.
  private static $request_map = [
      "GET" => RequestMethod::GET,
      "POST" => RequestMethod::POST,
      "HEAD" => RequestMethod::HEAD,
      "PUT" => RequestMethod::PUT,
      "DELETE" => RequestMethod::DELETE,
      "PATCH" => RequestMethod::PATCH
  ];

  protected $bucket_name;  // Name of the bucket for this object.
  protected $object_name;  // The name of the object.
  protected $context_options = [];  // Any context arguments supplied on open.
  protected $url;  // GCS URL of the object.
  protected $anonymous;  // Use anonymous access when contacting GCS.

  /**
   * Construct an object of CloudStorageClient.
   *
   * @
   */
  public function __construct($bucket, $object = null, $context = null) {
    $this->bucket_name = $bucket;
    $this->object_name = $object;
    if (!isset($context)) {
      $context = stream_context_get_default();
    }
    $context_array = stream_context_get_options($context);
    if (array_key_exists("gs", $context_array)) {
      $this->context_options = $context_array["gs"];
    }
    $this->anonymous = util\FindByKeyOrNull($this->context_options,
                                            "anonymous");

    $host = $this->isDevelServer() ? self::LOCAL_HOST : self::PRODUCTION_HOST;
    if (isset($this->object_name)) {
      $this->url = sprintf(self::BUCKET_OBJECT_FORMAT, $host, $bucket, $object);
    } else {
      $this->url = sprintf(self::BUCKET_FORMAT, $host, $bucket);
    }
  }

  public function __destruct() {
  }

  public function initialize() {
    return false;
  }

  // @return nothing
  public function close() {
  }

  public function delete() {
    return false;
  }

  public function eof() {
    return true;
  }

  public function flush() {
    return true;
  }

  public function read($count_bytes) {
    return false;
  }

  public function seek($offset, $whence) {
    return false;
  }

  public function stat() {
    return false;
  }

  public function tell() {
    return false;
  }

  public function write($data) {
    return false;
  }

  /**
   * Get the OAuth Token HTTP header for the supplied scope.
   *
   * @param $scopes mixed The scopes to acquire the token for.
   *
   * @return array The HTTP authorization header for the scopes, using the
   * applications service account. False if the call failed.
   */
  protected function getOAuthTokenHeader($scopes) {
    if ($this->anonymous) {
      return [];
    }

    try {
      $token = AppIdentityService::getAccessToken($scopes);
      return ["Authorization" => sprintf(self::OAUTH_TOKEN_FORMAT,
                                         $token['access_token'])];
    } catch (AppIdentityException $e) {
      return false;
    }
  }

  /**
   * Return a Range HTTP header.
   *
   * @param $start_byte int The offset of the first byte in the range.
   * @param $end_byte int The offset of the last byte in the range.
   *
   * @return array The HTTP Range header for the supplied offsets.
   */
  protected function getRangeHeader($start_byte, $end_byte) {
    assert($start_byte <= $end_byte);
    return ["Range" => sprintf("bytes=%d-%d", $start_byte, $end_byte)];
  }

  /**
   * Make a request to GCS using HttpStreams.
   *
   * Returns:
   * headers array
   * response body
   */
  protected function makeHttpRequest($url, $method, $headers, $body = null) {
    $request_headers = array_merge($headers, self::$api_version_header);

    $result = $this->doHttpRequest($url,
                                   $method,
                                   $request_headers,
                                   $body);

    if ($result === false) {
      return false;
    }

    return [
      'status_code' => $result['status_code'],
      'headers' => $result['headers'],
      'body' => $result['body'],
    ];
  }

  /**
   * Return the value of a header stored in an associative array, using a case
   * insensitive comparison on the header name.
   *
   * @param $header_name string The name of the header to lookup.
   * @param $headers array Associative array of headers.
   *
   * @return The value of the header if found, false otherwise.
   */
  protected function getHeaderValue($header_name, $headers) {
    // Could be more than one header, in which case we keep an array.
    foreach($headers as $key => $value) {
      if (strcasecmp($key, $header_name) === 0) {
        return $value;
      }
    }
    return null;
  }

  /**
   *
   */
  private function doHttpRequest($url, $method, $headers, $body) {
    $req = new \google\appengine\URLFetchRequest();
    $req->setUrl($url);
    $req->setMethod(self::$request_map[$method]);
    $req->setMustValidateServerCertificate(true);
    if (isset($body)) {
      $req->setPayload($body);
    }

    foreach($headers as $key => $value) {
      $h = $req->addHeader();
      $h->setKey($key);
      $h->setValue($value);
    }

    $resp = new \google\appengine\URLFetchResponse();

    try {
      ApiProxy::makeSyncCall('urlfetch', 'Fetch', $req, $resp);
    } catch (ApplicationError $e) {
      syslog(LOG_ERR,
             sprintf("Call to URLFetch failed with application error %d.",
                     $e->getApplicationError()));
      return false;
    }

    $response_headers = [];
    foreach($resp->getHeaderList() as $header) {
      // TODO: Do we need to support multiple headers with the same key?
      $response_headers[trim($header->getKey())] = trim($header->getValue());
    }

    return [
      'status_code' => $resp->getStatusCode(),
      'headers' => $response_headers,
      'body' => $resp->getContent(),
    ];
  }

  /**
   * Generate the default stat() array, which is both associative and index
   * based.
   *
   * @access private
   */
  protected function createStatArray($stat_args) {
    $stat_keys = ["dev", "ino", "mode", "nlink", "uid", "gid", "rdev", "size",
        "atime", "mtime", "ctime", "blksize", "blocks"];

    $result = [];

    foreach ($stat_keys as $key) {
      $value = 0;
      if (array_key_exists($key, $stat_args)) {
        $value = $stat_args[$key];
      }
      // Add the associative entry.
      $result[$key] = $value;
      // Add the index entry.
      $result[] = $value;
    }

    return $result;
  }

  /**
   * Determine if the code is executing on the development server.
   *
   * @return bool True if running in the developement server, false otherwise.
   */
  private function isDevelServer() {
    $server_software = getenv("SERVER_SOFTWARE");
    $key = "Development";
    return strncmp($server_software, $key, strlen($key)) === 0;
  }
}
