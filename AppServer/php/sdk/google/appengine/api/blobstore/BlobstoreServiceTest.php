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
 * PHP Unit tests for the BlobstoreService.
 *
 */

require_once 'google/appengine/api/blobstore/BlobstoreService.php';
require_once 'google/appengine/testing/ApiProxyTestBase.php';

use google\appengine\api\blobstore\BlobstoreService;
use google\appengine\testing\ApiProxyTestBase;
use google\appengine\BlobstoreServiceError;

/**
 * Unit test for BlobstoreService class.
 *
 * @outputBuffering disabled
 */
class BlobstoreServiceTest extends ApiProxyTestBase {

  public function setUp() {
    parent::setUp();
    $this->_SERVER = $_SERVER;

    // This is a a hacky workaround to the fact that you cannot use the header()
    // call in PHPUnit because you hit "headers already sent" errors.
    $this->sent_headers = [];
    $mock_send_header = function($key, $value){
      $this->sent_headers[$key] = $value;
    };
    BlobstoreService::setSendHeaderFunction($mock_send_header);
  }

  public function tearDown() {
    $_SERVER = $this->_SERVER;
    parent::tearDown();
  }

  public function testCreateUploadUrl() {
    $req = new \google\appengine\files\GetDefaultGsBucketNameRequest();
    $resp = new \google\appengine\files\GetDefaultGsBucketNameResponse();

    $resp->setDefaultGsBucketName("some_bucket");

    $this->apiProxyMock->expectCall("file",
                                    "GetDefaultGsBucketName",
                                    $req,
                                    $resp);

    $req = new \google\appengine\CreateUploadURLRequest();
    $req->setSuccessPath('http://foo/bar');
    $req->setGsBucketName("some_bucket");

    $resp = new \google\appengine\CreateUploadURLResponse();
    $resp->setUrl('http://upload/to/here');

    $this->apiProxyMock->expectCall('blobstore', 'CreateUploadURL', $req,
        $resp);

    $upload_url = BlobstoreService::createUploadUrl('http://foo/bar');
    $this->assertEquals($upload_url, 'http://upload/to/here');
    $this->apiProxyMock->verify();
  }

  public function testInvalidSuccessPath() {
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = BlobstoreService::CreateUploadUrl(10);
  }

  public function testSetMaxBytesPerBlob() {
    $req = new \google\appengine\CreateUploadURLRequest();
    $req->setSuccessPath('http://foo/bar');
    $req->setMaxUploadSizePerBlobBytes(37337);
    $req->setGsBucketName("some_bucket");

    $resp = new \google\appengine\CreateUploadURLResponse();
    $resp->setUrl('http://upload/to/here');

    $this->apiProxyMock->expectCall('blobstore', 'CreateUploadURL', $req,
        $resp);

    $upload_url = BlobstoreService::createUploadUrl('http://foo/bar',
        ['max_bytes_per_blob' => 37337,
         'gs_bucket_name' => 'some_bucket',]);
    $this->assertEquals($upload_url, 'http://upload/to/here');
    $this->apiProxyMock->verify();
  }

  public function testInvalidMaxBytesPerBlob() {
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = BlobstoreService::createUploadUrl('http://foo/bar',
        ['max_bytes_per_blob' => 'not an int',]);
  }

  public function testNegativeMaxBytesPerBlob() {
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = BlobstoreService::createUploadUrl('http://foo/bar',
        ['max_bytes_per_blob' => -1,]);
  }

  public function testSetMaxBytesTotal() {
    $req = new \google\appengine\CreateUploadURLRequest();
    $req->setSuccessPath('http://foo/bar');
    $req->setMaxUploadSizeBytes(137337);
    $req->setGsBucketName("some_bucket");

    $resp = new \google\appengine\CreateUploadURLResponse();
    $resp->setUrl('http://upload/to/here');

    $this->apiProxyMock->expectCall('blobstore', 'CreateUploadURL', $req,
        $resp);

    $upload_url = BlobstoreService::createUploadUrl('http://foo/bar',
        ['max_bytes_total' => 137337,
         'gs_bucket_name' => 'some_bucket',]);
    $this->assertEquals($upload_url, 'http://upload/to/here');
    $this->apiProxyMock->verify();
  }

  public function testInvalidMaxBytes() {
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = BlobstoreService::CreateUploadUrl('http://foo/bar',
        ['max_bytes_total' => 'not an int',]);
  }

  public function testNegativeMaxBytes() {
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = BlobstoreService::createUploadUrl('http://foo/bar',
        ['max_bytes_total' => -1,]);
  }

  public function testGsBucketName() {
    $req = new \google\appengine\CreateUploadURLRequest();
    $req->setSuccessPath('http://foo/bar');
    $req->setGsBucketName('my_cool_bucket');

    $resp = new \google\appengine\CreateUploadURLResponse();
    $resp->setUrl('http://upload/to/here');

    $this->apiProxyMock->expectCall('blobstore', 'CreateUploadURL', $req,
        $resp);

    $upload_url = BlobstoreService::createUploadUrl('http://foo/bar',
        ['gs_bucket_name' => 'my_cool_bucket',]);
    $this->assertEquals($upload_url, 'http://upload/to/here');
    $this->apiProxyMock->verify();
  }

  public function testInvalidGsBucketName() {
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = BlobstoreService::createUploadUrl('http://foo/bar',
        ['gs_bucket_name' => null,]);
  }

  public function testMultipleOptions() {
    $req = new \google\appengine\CreateUploadURLRequest();
    $req->setSuccessPath('http://foo/bar');
    $req->setMaxUploadSizePerBlobBytes(37337);
    $req->setMaxUploadSizeBytes(137337);
    $req->setGsBucketName('my_cool_bucket');

    $resp = new \google\appengine\CreateUploadURLResponse();
    $resp->setUrl('http://upload/to/here');

    $this->apiProxyMock->expectCall('blobstore', 'CreateUploadURL', $req,
        $resp);

    $upload_url = BlobstoreService::createUploadUrl('http://foo/bar',
        ['gs_bucket_name' => 'my_cool_bucket',
         'max_bytes_total' => 137337,
         'max_bytes_per_blob' => 37337]);
    $this->assertEquals($upload_url, 'http://upload/to/here');
    $this->apiProxyMock->verify();
  }

  public function testUrlTooLongException() {
    $req = new \google\appengine\CreateUploadURLRequest();
    $req->setSuccessPath('http://foo/bar');
    $req->setGsBucketName("some_bucket");

    $exception = new \google\appengine\runtime\ApplicationError(
        BlobstoreServiceError\ErrorCode::URL_TOO_LONG, 'message');

    $this->setExpectedException('\InvalidArgumentException', '');

    $this->apiProxyMock->expectCall('blobstore', 'CreateUploadURL', $req,
        $exception);

    $upload_url = BlobstoreService::createUploadUrl('http://foo/bar',
        ['gs_bucket_name' => 'some_bucket',]);
    $this->apiProxyMock->verify();
  }

  public function testPermissionDeniedException() {
    $req = new \google\appengine\CreateUploadURLRequest();
    $req->setSuccessPath('http://foo/bar');
    $req->setGsBucketName("some_bucket");

    $exception = new \google\appengine\runtime\ApplicationError(
        BlobstoreServiceError\ErrorCode::PERMISSION_DENIED, 'message');

    $this->setExpectedException(
        '\google\appengine\api\blobstore\BlobstoreException',
        'Permission Denied');

    $this->apiProxyMock->expectCall('blobstore', 'CreateUploadURL', $req,
        $exception);

    $upload_url = BlobstoreService::createUploadUrl('http://foo/bar',
        ['gs_bucket_name' => 'some_bucket',]);
    $this->apiProxyMock->verify();
  }

  public function testInternalErrorException() {
    $req = new \google\appengine\CreateUploadURLRequest();
    $req->setSuccessPath('http://foo/bar');
    $req->setGsBucketName("some_bucket");

    $exception = new \google\appengine\runtime\ApplicationError(
        BlobstoreServiceError\ErrorCode::INTERNAL_ERROR, 'message');

    $this->setExpectedException(
        '\google\appengine\api\blobstore\BlobstoreException', '');

    $this->apiProxyMock->expectCall('blobstore', 'CreateUploadURL', $req,
        $exception);

    $upload_url = BlobstoreService::createUploadUrl('http://foo/bar',
        ['gs_bucket_name' => 'some_bucket',]);
    $this->apiProxyMock->verify();
  }

  public function testNoDefaultBucketException() {
    $req = new \google\appengine\files\GetDefaultGsBucketNameRequest();
    $resp = new \google\appengine\files\GetDefaultGsBucketNameResponse();

    $this->apiProxyMock->expectCall("file",
                                    "GetDefaultGsBucketName",
                                    $req,
                                    $resp);
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = BlobstoreService::createUploadUrl('http://foo/bar');
    $this->apiProxyMock->verify();
  }

  public function testInvalidOptions() {
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = BlobstoreService::createUploadUrl('http://foo/bar',
        ['gs_bucket_name' => 'bucket',
         'foo' => 'bar']);
  }

  public function testCreateGsKeyInvalidFileName() {
    $this->setExpectedException('\InvalidArgumentException');
    BlobstoreService::createGsKey(1);
  }

  public function testCreateGsKeyInvalidGcsPrefix() {
    $this->setExpectedException('\InvalidArgumentException');
    BlobstoreService::serve("/goo/bar.png");
  }

  public function testCreateGsKeyInvalidBucketObjectName() {
    $this->setExpectedException(
        '\InvalidArgumentException',
        'filename not in the format gcs://bucket_name/object_name.');
    BlobstoreService::serve("gcs://some_bucket");
  }

  public function testCreateGsKeySuccess() {
    $req = new \google\appengine\CreateEncodedGoogleStorageKeyRequest();
    $req->setFilename("/gs/some_bucket/some_object");

    $resp = new \google\appengine\CreateEncodedGoogleStorageKeyResponse();
    $resp->setBlobKey("some_blob_key");

    $this->apiProxyMock->expectCall("blobstore",
                                    "CreateEncodedGoogleStorageKey",
                                    $req,
                                    $resp);

    $filename = "gcs://some_bucket/some_object";
    $this->assertEquals("some_blob_key",
                        BlobstoreService::createGsKey($filename));
    $this->apiProxyMock->verify();
  }

  public function testServeInvalidOptionArray() {
    $this->setExpectedException('\InvalidArgumentException');
    BlobstoreService::serve("gcs://foo/bar.png", ["foo" => true]);
  }

  public function testServeEndBadRanges() {
    $ranges = [[null, 1], [null, -1], [2, 1], [-1, 1]];
    foreach($ranges as $range) {
      try {
        BlobstoreService::serve("gcs://foo/bar.png",
                                ["start" => $range[0], "end" => $range[1]]);
      } catch (\InvalidArgumentException $e) {
        continue;
      }
      $this->fail("InvalidArgumentException was not thrown");
    }
  }

  public function testServeRangeIndexDoNotMatchRangeHeader() {
    $this->setExpectedException("\InvalidArgumentException");
    $_SERVER["HTTP_RANGE"] = "bytes=1-2";
    BlobstoreService::serve("gcs://foo/bar.png", ["start" => 1, "end" => 3,
        "use_range" => true]);
  }

  public function testServeSuccess() {
    $req = new \google\appengine\CreateEncodedGoogleStorageKeyRequest();
    $req->setFilename("/gs/some_bucket/some_object");

    $resp = new \google\appengine\CreateEncodedGoogleStorageKeyResponse();
    $resp->setBlobKey("some_blob_key");

    $this->apiProxyMock->expectCall("blobstore",
                                    "CreateEncodedGoogleStorageKey",
                                    $req,
                                    $resp);

    $filename = "gcs://some_bucket/some_object";
    $expected_headers = [
        "X-AppEngine-BlobKey" => "some_blob_key",
        "X-AppEngine-BlobRange" => "bytes=1-2",
        "Content-Disposition" => "attachment; filename=foo.jpg",
    ];
    $options = [
        "start" => 1,
        "end" => 2,
        "save_as" => "foo.jpg",
    ];
    BlobstoreService::serve($filename, $options);
    $this->assertEquals(ksort($this->sent_headers), ksort($expected_headers));
    $this->apiProxyMock->verify();
  }

  public function testServeSuccessNegativeRange() {
    $req = new \google\appengine\CreateEncodedGoogleStorageKeyRequest();
    $req->setFilename("/gs/some_bucket/some_object");

    $resp = new \google\appengine\CreateEncodedGoogleStorageKeyResponse();
    $resp->setBlobKey("some_blob_key");

    $this->apiProxyMock->expectCall("blobstore",
                                    "CreateEncodedGoogleStorageKey",
                                    $req,
                                    $resp);

    $filename = "gcs://some_bucket/some_object";
    $expected_headers = [
        "X-AppEngine-BlobKey" => "some_blob_key",
        "X-AppEngine-BlobRange" => "bytes=-1001",
        "Content-Disposition" => "attachment; filename=foo.jpg",
    ];
    $options = [
        "start" => -1001,
        "save_as" => "foo.jpg",
    ];
    BlobstoreService::serve($filename, $options);
    $this->assertEquals(ksort($this->sent_headers), ksort($expected_headers));
    $this->apiProxyMock->verify();
  }

  public function testServeRangeHeaderSuccess() {
    $req = new \google\appengine\CreateEncodedGoogleStorageKeyRequest();
    $req->setFilename("/gs/some_bucket/some_object");

    $resp = new \google\appengine\CreateEncodedGoogleStorageKeyResponse();
    $resp->setBlobKey("some_blob_key");

    $this->apiProxyMock->expectCall("blobstore",
                                    "CreateEncodedGoogleStorageKey",
                                    $req,
                                    $resp);

    $filename = "gcs://some_bucket/some_object";
    $expected_headers = [
        "X-AppEngine-BlobKey" => "some_blob_key",
        "X-AppEngine-BlobRange" => "bytes=100-200",
        "Content-Disposition" => "attachment; filename=foo.jpg",
        "Content-Type" => "image/jpeg",
    ];
    $options = [
        "save_as" => "foo.jpg",
        "use_range" => true,
        "content_type" => "image/jpeg",
    ];
    $_SERVER["HTTP_RANGE"] = "bytes=100-200";
    BlobstoreService::serve($filename, $options);
    $this->assertEquals(ksort($this->sent_headers), ksort($expected_headers));
    $this->apiProxyMock->verify();
  }

  public function testGetDefaultBucketNameSuccess() {
    $req = new \google\appengine\files\GetDefaultGsBucketNameRequest();
    $resp = new \google\appengine\files\GetDefaultGsBucketNameResponse();

    $resp->setDefaultGsBucketName("some_bucket");

    $this->apiProxyMock->expectCall("file",
                                    "GetDefaultGsBucketName",
                                    $req,
                                    $resp);

    $bucket = BlobstoreService::getDefaultGoogleStorageBucketName();
    $this->assertEquals($bucket, "some_bucket");
    $this->apiProxyMock->verify();
  }

  public function testGetDefaultBucketNameNotSet() {
    $req = new \google\appengine\files\GetDefaultGsBucketNameRequest();
    $resp = new \google\appengine\files\GetDefaultGsBucketNameResponse();

    $this->apiProxyMock->expectCall("file",
                                    "GetDefaultGsBucketName",
                                    $req,
                                    $resp);

    $bucket = BlobstoreService::getDefaultGoogleStorageBucketName();
    $this->assertEquals($bucket, "");
    $this->apiProxyMock->verify();
  }
}

