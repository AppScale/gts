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
 * Google Cloud Storage Stream Wrapper Tests.
 *
 */

namespace {
// Ignore calls to memcache from app identity service.
class Memcache {
  public function get($keys, $flags = null) {
    return False;
  }
  public function set($key, $value, $flag = null, $expire = 0) {
  }
}
}  // namespace

namespace google\appengine\ext\cloud_storage_streams {

require_once 'google/appengine/api/app_identity/app_identity_service_pb.php';
require_once 'google/appengine/api/app_identity/AppIdentityService.php';
require_once 'google/appengine/api/urlfetch_service_pb.php';
require_once 'google/appengine/ext/cloud_storage_streams/CloudStorageClient.php';
require_once 'google/appengine/ext/cloud_storage_streams/CloudStorageReadClient.php';
require_once 'google/appengine/ext/cloud_storage_streams/CloudStorageStreamWrapper.php';
require_once 'google/appengine/ext/cloud_storage_streams/CloudStorageWriteClient.php';
require_once 'google/appengine/testing/ApiProxyTestBase.php';

use \google\appengine\testing\ApiProxyTestBase;
use \google\appengine\ext\cloud_storage_streams\CloudStorageClient;
use \google\appengine\ext\cloud_storage_streams\CloudStorageReadClient;
use \google\appengine\ext\cloud_storage_streams\CloudStorageWriteClient;
use \google\appengine\ext\cloud_storage_streams\HttpResponse;
use \google\appengine\URLFetchRequest\RequestMethod;

// Allow mocking of ini_get by declaring it in the namespace.
function ini_get($name) {
  if ($name === "google_app_engine.allow_include_gs_buckets") {
    return CloudStorageStreamWrapperTest::$allowed_gs_bucket;
  } else {
    return \ini_get($name);
  }
}

class CloudStorageStreamWrapperTest extends ApiProxyTestBase {

  public static $allowed_gs_bucket = "";

  protected function setUp() {
    parent::setUp();
    $this->_SERVER = $_SERVER;

    stream_wrapper_register("gs",
        "\\google\\appengine\\ext\\cloud_storage_streams\\CloudStorageStreamWrapper",
        STREAM_IS_URL);

    CloudStorageStreamWrapperTest::$allowed_gs_bucket = "";

    date_default_timezone_set("UTC");
  }

  protected function tearDown() {
    stream_wrapper_unregister("gs");

    $_SERVER = $this->_SERVER;
    parent::tearDown();
  }

  public function testInvalidPathName() {
    $this->setExpectedException("\PHPUnit_Framework_Error");
    $this->assertFalse(fopen("gs:///object.png", "r"));
    $this->setExpectedException("\PHPUnit_Framework_Error");
    $this->assertFalse(fopen("gs://", "r"));
  }

  public function testInvalidMode() {
    $valid_path = "gs://bucket/object_name.png";
    $this->setExpectedException("\PHPUnit_Framework_Error");
    $this->assertFalse(fopen($valid_path, "r+"));
    $this->setExpectedException("\PHPUnit_Framework_Error");
    $this->assertFalse(fopen($valid_path, "w+"));
    $this->setExpectedException("\PHPUnit_Framework_Error");
    $this->assertFalse(fopen($valid_path, "a"));
    $this->setExpectedException("\PHPUnit_Framework_Error");
    $this->assertFalse(fopen($valid_path, "a+"));
    $this->setExpectedException("\PHPUnit_Framework_Error");
    $this->assertFalse(fopen($valid_path, "x+"));
    $this->setExpectedException("\PHPUnit_Framework_Error");
    $this->assertFalse(fopen($valid_path, "c"));
    $this->setExpectedException("\PHPUnit_Framework_Error");
    $this->assertFalse(fopen($valid_path, "c+"));
  }

  public function testReadObjectSuccess() {
    $body = "Hello from PHP";

    $this->expectFileReadRequest($body,
                                 0,
                                 CloudStorageReadClient::DEFAULT_READ_SIZE,
                                 null);

    $valid_path = "gs://bucket/object_name.png";
    $data = file_get_contents($valid_path);

    $this->assertEquals($body, $data);
    $this->apiProxyMock->verify();
  }

  public function testReadObjectPartialContentResponseSuccess() {
    // GCS returns a 206 even if you can obtain all of the file in the first
    // read - this test simulates that behavior.
    $body = "Hello from PHP.";

    $this->expectFileReadRequest($body,
                                 0,
                                 CloudStorageReadClient::DEFAULT_READ_SIZE,
                                 null,
                                 true);

    $valid_path = "gs://bucket/object_name.png";
    $data = file_get_contents($valid_path);

    $this->assertEquals($body, $data);
    $this->apiProxyMock->verify();
  }

  public function testReadLargeObjectSuccess() {
    $body = str_repeat("1234567890", 100000);
    $data_len = strlen($body);

    $read_chunks = ceil($data_len / CloudStorageReadClient::DEFAULT_READ_SIZE);
    $start_chunk = 0;
    $etag = null;

    for ($i = 0; $i < $read_chunks; $i++) {
      $this->expectFileReadRequest($body,
                                   $start_chunk,
                                   CloudStorageReadClient::DEFAULT_READ_SIZE,
                                   $etag,
                                   true);
      $start_chunk += CloudStorageReadClient::DEFAULT_READ_SIZE;
      $etag = "deadbeef";
    }

    $valid_path = "gs://bucket/object_name.png";
    $fp = fopen($valid_path, "r");
    $data = stream_get_contents($fp);
    fclose($fp);

    $this->assertEquals($body, $data);
    $this->apiProxyMock->verify();
  }

  public function testSeekReadObjectSuccess() {
    $body = "Hello from PHP";

    $this->expectFileReadRequest($body,
                                 0,
                                 CloudStorageReadClient::DEFAULT_READ_SIZE,
                                 null);

    $valid_path = "gs://bucket/object_name.png";
    $fp = fopen($valid_path, "r");
    $this->assertEquals(0, fseek($fp, 4, SEEK_SET));
    $this->assertEquals($body[4], fread($fp, 1));
    $this->assertEquals(-1, fseek($fp, 100, SEEK_SET));
    $this->assertTrue(fclose($fp));

    $this->apiProxyMock->verify();
  }

  public function testReadZeroSizedObjectSuccess() {
    $this->expectFileReadRequest("",
                                 0,
                                 CloudStorageReadClient::DEFAULT_READ_SIZE,
                                 null);

    $data = file_get_contents("gs://bucket/object_name.png");

    $this->assertEquals("", $data);
    $this->apiProxyMock->verify();
  }

  public function testFileSizeSucess() {
    $body = "Hello from PHP";

    $this->expectFileReadRequest($body,
                                 0,
                                 CloudStorageReadClient::DEFAULT_READ_SIZE,
                                 null);

    $valid_path = "gs://bucket/object_name.png";
    $fp = fopen($valid_path, "r");
    $stat = fstat($fp);
    fclose($fp);
    $this->assertEquals(strlen($body), $stat["size"]);
    $this->apiProxyMock->verify();
  }

  public function testDeleteObjectSuccess() {
    $this->expectGetAccessTokenRequest(CloudStorageClient::WRITE_SCOPE);

    $request_headers = [
        "Authorization" => "OAuth foo token",
        "x-goog-api-version" => 2,
    ];
    $response = [
        'status_code' => 204,
        'headers' => [
        ],
    ];
    $expected_url = sprintf(CloudStorageClient::BUCKET_OBJECT_FORMAT,
                            CloudStorageClient::PRODUCTION_HOST,
                            "bucket",
                            "/object_name.png");
    $this->expectHttpRequest($expected_url,
                             RequestMethod::DELETE,
                             $request_headers,
                             null,
                             $response);

    $this->assertTrue(unlink("gs://bucket/object_name.png"));
    $this->apiProxyMock->verify();
  }

  public function testDeleteObjectFail() {
    $this->expectGetAccessTokenRequest(CloudStorageClient::WRITE_SCOPE);

    $request_headers = [
        "Authorization" => "OAuth foo token",
        "x-goog-api-version" => 2,
    ];
    $response = [
        'status_code' => 404,
        'headers' => [
        ],
    ];
    $expected_url = sprintf(CloudStorageClient::BUCKET_OBJECT_FORMAT,
                            CloudStorageClient::PRODUCTION_HOST,
                            "bucket",
                            "/object_name.png");
    $this->expectHttpRequest($expected_url,
                             RequestMethod::DELETE,
                             $request_headers,
                             null,
                             $response);

    $this->assertFalse(unlink("gs://bucket/object_name.png"));
    $this->apiProxyMock->verify();
  }

  public function testStatBucketSuccess() {
    $this->expectGetAccessTokenRequest(CloudStorageClient::WRITE_SCOPE);

    $request_headers = [
        "Authorization" => "OAuth foo token",
        "x-goog-api-version" => 2,
    ];
    $response = [
        'status_code' => 200,
        'headers' => [
        ],
    ];

    $expected_url = sprintf(CloudStorageClient::BUCKET_FORMAT,
                            CloudStorageClient::PRODUCTION_HOST,
                            "bucket");
    $this->expectHttpRequest($expected_url,
                             RequestMethod::HEAD,
                             $request_headers,
                             null,
                             $response);

    $this->assertTrue(is_dir("gs://bucket"));
    $this->apiProxyMock->verify();
  }

  public function testStatObjectSuccess() {
    $this->expectGetAccessTokenRequest(CloudStorageClient::WRITE_SCOPE);

    $request_headers = [
        "Authorization" => "OAuth foo token",
        "x-goog-api-version" => 2,
    ];
    $response = [
        'status_code' => 200,
        'headers' => [
            'Content-Length' => 37337,
        ],
    ];

    $expected_url = sprintf(CloudStorageClient::BUCKET_OBJECT_FORMAT,
                            CloudStorageClient::PRODUCTION_HOST,
                            "bucket",
                            "/object_name.png");
    $this->expectHttpRequest($expected_url,
                             RequestMethod::HEAD,
                             $request_headers,
                             null,
                             $response);

    $result = stat("gs://bucket/object_name.png");
    $this->assertEquals(37337, $result['size']);
    $this->assertEquals(0100400, $result['mode']);
    $this->apiProxyMock->verify();
  }

  public function testStatObjectFailed() {
    $this->expectGetAccessTokenRequest(CloudStorageClient::WRITE_SCOPE);

    $request_headers = [
        "Authorization" => "OAuth foo token",
        "x-goog-api-version" => 2,
    ];
    $response = [
        'status_code' => 404,
        'headers' => [
        ],
    ];

    $expected_url = sprintf(CloudStorageClient::BUCKET_OBJECT_FORMAT,
                            CloudStorageClient::PRODUCTION_HOST,
                            "bucket",
                            "/object_name.png");
    $this->expectHttpRequest($expected_url,
                             RequestMethod::HEAD,
                             $request_headers,
                             null,
                             $response);

    $this->setExpectedException("PHPUnit_Framework_Error_Warning");
    $result = stat("gs://bucket/object_name.png");
    $this->apiProxyMock->verify();
  }

  public function testWriteObjectSuccess() {
    $data_to_write = "Hello To PHP.";
    $data_to_write_len = strlen($data_to_write);

    $expected_url = sprintf(CloudStorageClient::BUCKET_OBJECT_FORMAT,
                            CloudStorageClient::PRODUCTION_HOST,
                            "bucket",
                            "/object.png");

    $this->expectFileWriteStartRequest("text/plain",
                                       "public-read",
                                       "foo_upload_id",
                                       $expected_url);

    $this->expectFileWriteContentRequest($expected_url,
                                         "foo_upload_id",
                                         $data_to_write,
                                         0,
                                         $data_to_write_len - 1,
                                         true);

    stream_context_set_default([
        "gs" => [
            "acl" => "public-read",
            "Content-Type" => "text/plain",
        ],
    ]);
    $this->assertEquals($data_to_write_len,
                        file_put_contents("gs://bucket/object.png",
                                          $data_to_write));
    $this->apiProxyMock->verify();
  }

  public function testWriteLargeObjectSuccess() {
    $data_to_write = str_repeat("1234567890", 100000);
    $data_len = strlen($data_to_write);

    $expected_url = sprintf(CloudStorageClient::BUCKET_OBJECT_FORMAT,
                            CloudStorageClient::PRODUCTION_HOST,
                            "bucket",
                            "/object.png");

    $this->expectFileWriteStartRequest("text/plain",
                                       "public-read",
                                       "foo_upload_id",
                                       $expected_url);

    $chunks = floor($data_len / CloudStorageWriteClient::WRITE_CHUNK_SIZE);
    $start_byte = 0;
    $end_byte = CloudStorageWriteClient::WRITE_CHUNK_SIZE - 1;

    for ($i = 0 ; $i < $chunks ; $i++) {
      $this->expectFileWriteContentRequest($expected_url,
                                           "foo_upload_id",
                                           $data_to_write,
                                           $start_byte,
                                           $end_byte,
                                           false);
      $start_byte += CloudStorageWriteClient::WRITE_CHUNK_SIZE;
      $end_byte += CloudStorageWriteClient::WRITE_CHUNK_SIZE;
    }

    // Write out the remainder
    $this->expectFileWriteContentRequest($expected_url,
                                         "foo_upload_id",
                                         $data_to_write,
                                         $start_byte,
                                         $data_len - 1,
                                         true);

    $file_context = [
        "gs" => [
            "acl" => "public-read",
            "Content-Type" => "text/plain",
        ],
    ];
    $ctx = stream_context_create($file_context);
    $this->assertEquals($data_len,
                        file_put_contents("gs://bucket/object.png",
                                          $data_to_write,
                                          0,
                                          $ctx));
    $this->apiProxyMock->verify();
  }

  public function testWriteEmptyObjectSuccess() {
    $data_to_write = "";
    $data_len = 0;

    $expected_url = sprintf(CloudStorageClient::BUCKET_OBJECT_FORMAT,
                            CloudStorageClient::PRODUCTION_HOST,
                            "bucket",
                            "/empty_file.txt");

    $this->expectFileWriteStartRequest("text/plain",
                                       "public-read",
                                       "foo_upload_id",
                                       $expected_url);

    $this->expectFileWriteContentRequest($expected_url,
                                         "foo_upload_id",
                                         $data_to_write,
                                         null,  // start_byte
                                         0,  // write_length
                                         true);  // Complete write

    $file_context = [
        "gs" => [
            "acl" => "public-read",
            "Content-Type" => "text/plain",
        ],
    ];
    $ctx = stream_context_create($file_context);
    $this->assertEquals($data_len,
                        file_put_contents("gs://bucket/empty_file.txt",
                                          $data_to_write,
                                          0,
                                          $ctx));
    $this->apiProxyMock->verify();
  }

  public function testInvalidBucketForInclude() {
    stream_wrapper_unregister("gs");
    stream_wrapper_register("gs",
        "\\google\\appengine\\ext\\cloud_storage_streams\\CloudStorageStreamWrapper",
        0);

    $this->setExpectedException("\PHPUnit_Framework_Error");
    include 'gs://bucket/object.php';
  }

  public function testValidBucketForInclude() {
    stream_wrapper_unregister("gs");
    stream_wrapper_register("gs",
        "\\google\\appengine\\ext\\cloud_storage_streams\\CloudStorageStreamWrapper",
        0);

    $body = '<?php $a = "foo";';

    $this->expectFileReadRequest($body,
                                 0,
                                 CloudStorageReadClient::DEFAULT_READ_SIZE,
                                 null);

    CloudStorageStreamWrapperTest::$allowed_gs_bucket = "foo, bucket, bar";
    $valid_path = "gs://bucket/object_name.png";
    require $valid_path;

    $this->assertEquals($a, 'foo');
    $this->apiProxyMock->verify();
  }

  private function expectFileReadRequest($body,
                                         $start_byte,
                                         $length,
                                         $etag = null,
                                         $paritial_content = null) {
    $this->expectGetAccessTokenRequest(CloudStorageClient::READ_SCOPE);

    assert($length > 0);
    $last_byte = $start_byte + $length - 1;
    $request_headers = [
        "Authorization" => "OAuth foo token",
        "Range" => sprintf("bytes=%d-%d", $start_byte, $last_byte),
    ];

    if (isset($etag)) {
      $request_headers['If-Match'] = $etag;
    }

    $request_headers["x-goog-api-version"] = 2;

    $response_headers = [
        "ETag" => "deadbeef",
        "Content-Type" => "text/plain",
        "Last-Modified" => "Mon, 02 Jul 2012 01:41:01 GMT",
    ];

    $response = $this->createSuccessfulGetHttpResponse($response_headers,
                                                       $body,
                                                       $start_byte,
                                                       $length,
                                                       $paritial_content);

    $exected_url = sprintf(CloudStorageClient::BUCKET_OBJECT_FORMAT,
                           CloudStorageClient::PRODUCTION_HOST,
                           "bucket",
                           "/object_name.png");

    $this->expectHttpRequest($exected_url,
                             RequestMethod::GET,
                             $request_headers,
                             null,
                             $response);
  }

  private function expectGetAccessTokenRequest($scope) {
    $req = new \google\appengine\GetAccessTokenRequest();

    $req->addScope($scope);

    $resp = new \google\appengine\GetAccessTokenResponse();
    $resp->setAccessToken('foo token');
    $resp->setExpirationTime(12345);

    $this->apiProxyMock->expectCall('app_identity_service',
                                    'GetAccessToken',
                                    $req,
                                    $resp);
  }

  private function createSuccessfulGetHttpResponse($headers,
                                                   $body,
                                                   $start_byte,
                                                   $length,
                                                   $return_partial_content) {
    $total_body_length = strlen($body);
    $partial_content = false;
    $range_cannot_be_satisfied = false;

    if ($total_body_length <= $start_byte) {
      $range_cannot_be_satisfied = true;
    }
    if ($start_byte != 0 || $length < $total_body_length) {
      $final_length = min($length, $total_body_length - $start_byte);
      $body = substr($body, $start_byte, $final_length);
      $partial_content = true;
    } else if ($return_partial_content) {
      $final_length = strlen($body);
      $partial_content = true;
    }

    $success_headers = [];
    if ($range_cannot_be_satisfied) {
      $status_code = HttpResponse::RANGE_NOT_SATISFIABLE;
    } else if (!$partial_content) {
      $status_code = HttpResponse::OK;
      $success_headers["Content-Length"] = $total_body_length;
    } else {
      $status_code = HttpResponse::PARTIAL_CONTENT;
      $end_range = $start_byte + $final_length - 1;
      $success_headers["Content-Length"] = $final_length;
      $success_headers["Content-Range"] = sprintf("bytes %d-%d/%d",
                                                  $start_byte,
                                                  $end_range,
                                                  $total_body_length);
    }

    return [
        'status_code' => $status_code,
        'headers' => array_merge($success_headers, $headers),
        'body' => $body,
    ];
  }

  private function expectFileWriteStartRequest($content_type, $acl, $id, $url) {
    $this->expectGetAccessTokenRequest(CloudStorageClient::WRITE_SCOPE);
    $upload_id =  "https://host/bucket/object.png?upload_id=" . $id;
    // The upload will start with a POST to acquire the upload ID.
    $request_headers = [
        "x-goog-resumable" => "start",
        "Authorization" => "OAuth foo token",
        "Content-Type" => $content_type,
        "x-goog-acl" => $acl,
        "x-goog-api-version" => 2,
    ];
    $response = [
        'status_code' => 201,
        'headers' => [
            'Location' => $upload_id,
        ],
    ];
    $this->expectHttpRequest($url,
                             RequestMethod::POST,
                             $request_headers,
                             null,
                             $response);
  }

  private function expectFileWriteContentRequest($url,
                                                 $upload_id,
                                                 $data,
                                                 $start_byte,
                                                 $end_byte,
                                                 $complete) {
    // The upload will be completed with a PUT with the final length
    $this->expectGetAccessTokenRequest(CloudStorageClient::WRITE_SCOPE);
    // If start byte is null then we assume that this is a PUT with no content,
    // and the end_byte contains the length of the data to write.
    if (is_null($start_byte)) {
      $range = sprintf("bytes */%d", $end_byte);
      $status_code = HttpResponse::OK;
      $body = null;
    } else {
      $length = $end_byte - $start_byte + 1;
      if ($complete) {
        $total_len = $end_byte + 1;
        $range = sprintf("bytes %d-%d/%d", $start_byte, $end_byte, $total_len);
        $status_code = HttpResponse::OK;
      } else {
        $range = sprintf("bytes %d-%d/*", $start_byte, $end_byte);
        $status_code = HttpResponse::RESUME_INCOMPLETE;
      }
      $body = substr($data, $start_byte, $length);
    }
    $request_headers = [
        "Authorization" => "OAuth foo token",
        "Content-Range" => $range,
        "x-goog-api-version" => 2,
    ];
    $response = [
        'status_code' => $status_code,
        'headers' => [
        ],
    ];
    $expected_url = $url . "?upload_id=" . $upload_id;
    $this->expectHttpRequest($expected_url,
                             RequestMethod::PUT,
                             $request_headers,
                             $body,
                             $response);
  }

  private function expectHttpRequest($url, $method, $headers, $body, $result) {
    $req = new \google\appengine\URLFetchRequest();
    $req->setUrl($url);
    $req->setMethod($method);
    $req->setMustValidateServerCertificate(true);

    foreach($headers as $k => $v) {
      $h = $req->addHeader();
      $h->setKey($k);
      $h->setValue($v);
    }

    if (isset($body)) {
      $req->setPayload($body);
    }

    $resp = new \google\appengine\URLFetchResponse();

    $resp->setStatusCode($result['status_code']);
    foreach($result['headers'] as $k => $v) {
      $h = $resp->addHeader();
      $h->setKey($k);
      $h->setValue($v);
    }
    if (isset($result['body'])) {
      $resp->setContent($result['body']);
    }

    $this->apiProxyMock->expectCall('urlfetch',
                                    'Fetch',
                                    $req,
                                    $resp);
  }
}

}  // namespace google\appengine\ext\cloud_storage_streams;

