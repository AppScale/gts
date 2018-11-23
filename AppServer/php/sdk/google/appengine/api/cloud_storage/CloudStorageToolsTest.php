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
 * PHP Unit tests for the CloudStorageTools.
 *
 */

require_once 'google/appengine/api/cloud_storage/CloudStorageTools.php';
require_once 'google/appengine/testing/ApiProxyTestBase.php';

use google\appengine\api\cloud_storage\CloudStorageTools;
use google\appengine\testing\ApiProxyTestBase;
use google\appengine\BlobstoreServiceError;
use google\appengine\ImagesServiceError;

/**
 * Unit test for CloudStorageTools class.
 *
 * @outputBuffering disabled
 */
class CloudStorageToolsTest extends ApiProxyTestBase {

  public function setUp() {
    parent::setUp();
    $this->_SERVER = $_SERVER;

    // This is a a hacky workaround to the fact that you cannot use the header()
    // call in PHPUnit because you hit "headers already sent" errors.
    $this->sent_headers = [];
    $mock_send_header = function($key, $value){
      $this->sent_headers[$key] = $value;
    };
    CloudStorageTools::setSendHeaderFunction($mock_send_header);
  }

  public function tearDown() {
    $_SERVER = $this->_SERVER;
    parent::tearDown();
  }

  private function expectFilenameTranslation($filename, $blob_key) {
    $req = new \google\appengine\CreateEncodedGoogleStorageKeyRequest();
    $req->setFilename($filename);

    $resp = new \google\appengine\CreateEncodedGoogleStorageKeyResponse();
    $resp->setBlobKey($blob_key);

    $this->apiProxyMock->expectCall('blobstore',
                                    'CreateEncodedGoogleStorageKey',
                                    $req,
                                    $resp);
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

    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar');
    $this->assertEquals($upload_url, 'http://upload/to/here');
    $this->apiProxyMock->verify();
  }

  public function testInvalidSuccessPath() {
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = CloudStorageTools::createUploadUrl(10);
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

    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
        ['max_bytes_per_blob' => 37337,
         'gs_bucket_name' => 'some_bucket',]);
    $this->assertEquals($upload_url, 'http://upload/to/here');
    $this->apiProxyMock->verify();
  }

  public function testInvalidMaxBytesPerBlob() {
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
        ['max_bytes_per_blob' => 'not an int',]);
  }

  public function testNegativeMaxBytesPerBlob() {
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
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

    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
        ['max_bytes_total' => 137337,
         'gs_bucket_name' => 'some_bucket',]);
    $this->assertEquals($upload_url, 'http://upload/to/here');
    $this->apiProxyMock->verify();
  }

  public function testInvalidMaxBytes() {
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = CloudStorageTools::CreateUploadUrl('http://foo/bar',
        ['max_bytes_total' => 'not an int',]);
  }

  public function testNegativeMaxBytes() {
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
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

    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
        ['gs_bucket_name' => 'my_cool_bucket',]);
    $this->assertEquals($upload_url, 'http://upload/to/here');
    $this->apiProxyMock->verify();
  }

  public function testInvalidGsBucketName() {
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
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

    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
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

    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
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
        '\google\appengine\api\cloud_storage\CloudStorageException',
        'Permission Denied');

    $this->apiProxyMock->expectCall('blobstore', 'CreateUploadURL', $req,
        $exception);

    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
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
        '\google\appengine\api\cloud_storage\CloudStorageException', '');

    $this->apiProxyMock->expectCall('blobstore', 'CreateUploadURL', $req,
        $exception);

    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
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
    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar');
    $this->apiProxyMock->verify();
  }

  public function testInvalidOptions() {
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
        ['gs_bucket_name' => 'bucket',
         'foo' => 'bar']);
  }

  public function testServeInvalidGsPrefix() {
    $this->setExpectedException('\InvalidArgumentException');
    CloudStorageTools::serve("/goo/bar.png");
  }

  public function testServeInvalidBucketObjectName() {
    $this->setExpectedException(
        '\InvalidArgumentException',
        'filename not in the format gs://bucket_name/object_name.');
    CloudStorageTools::serve("gs://some_bucket");
  }

  public function testServeInvalidOptionArray() {
    $this->setExpectedException('\InvalidArgumentException');
    CloudStorageTools::serve("gs://foo/bar.png", ["foo" => true]);
  }

  public function testServeEndBadRanges() {
    $ranges = [[null, 1], [null, -1], [2, 1], [-1, 1]];
    foreach($ranges as $range) {
      try {
        CloudStorageTools::serve("gs://foo/bar.png",
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
    CloudStorageTools::serve("gs://foo/bar.png", ["start" => 1, "end" => 3,
        "use_range" => true]);
  }

  public function testServeSuccess() {
    $this->expectFilenameTranslation("/gs/some_bucket/some_object",
                                     "some_blob_key");
    $filename = "gs://some_bucket/some_object";
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
    CloudStorageTools::serve($filename, $options);
    $this->assertEquals(ksort($this->sent_headers), ksort($expected_headers));
    $this->apiProxyMock->verify();
  }

  public function testServeSuccessNegativeRange() {
    $this->expectFilenameTranslation("/gs/some_bucket/some_object",
                                     "some_blob_key");
    $filename = "gs://some_bucket/some_object";
    $expected_headers = [
        "X-AppEngine-BlobKey" => "some_blob_key",
        "X-AppEngine-BlobRange" => "bytes=-1001",
        "Content-Disposition" => "attachment; filename=foo.jpg",
    ];
    $options = [
        "start" => -1001,
        "save_as" => "foo.jpg",
    ];
    CloudStorageTools::serve($filename, $options);
    $this->assertEquals(ksort($this->sent_headers), ksort($expected_headers));
    $this->apiProxyMock->verify();
  }

  public function testServeRangeHeaderSuccess() {
    $this->expectFilenameTranslation("/gs/some_bucket/some_object",
                                     "some_blob_key");
    $filename = "gs://some_bucket/some_object";
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
    CloudStorageTools::serve($filename, $options);
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

    $bucket = CloudStorageTools::getDefaultGoogleStorageBucketName();
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

    $bucket = CloudStorageTools::getDefaultGoogleStorageBucketName();
    $this->assertEquals($bucket, "");
    $this->apiProxyMock->verify();
  }

  // getImageServingUrl tests.

  public function testGetImageUrlInvalidFilenameType() {
    $this->setExpectedException('\InvalidArgumentException');
    $url = CloudStorageTools::getImageServingUrl(123);
  }

  public function testGetImageUrlInvalidFilename() {
    $this->setExpectedException('\InvalidArgumentException');
    $url = CloudStorageTools::getImageServingUrl('not-gs://abucket/photo');
  }

  public function testGetImageUrlCropInvalidType() {
    $this->expectFilenameTranslation('/gs/mybucket/photo.jpg', 'some_blob_key');
    $this->setExpectedException('\InvalidArgumentException');
    $url = CloudStorageTools::getImageServingUrl('gs://mybucket/photo.jpg',
                                                ['crop' => 5]);
    $this->apiProxyMock->verify();
  }

  public function testGetImageUrlCropRequiresSize() {
    $this->expectFilenameTranslation('/gs/mybucket/photo.jpg', 'some_blob_key');
    $this->setExpectedException('\InvalidArgumentException');
    $url = CloudStorageTools::getImageServingUrl('gs://mybucket/photo.jpg',
                                                ['crop' => true]);
    $this->apiProxyMock->verify();
  }

  public function testGetImageUrlSizeInvalidType() {
    $this->expectFilenameTranslation('/gs/mybucket/photo.jpg', 'some_blob_key');
    $this->setExpectedException(
        '\InvalidArgumentException',
        '$options[\'size\'] must be an integer. Actual type: string');
    $url = CloudStorageTools::getImageServingUrl('gs://mybucket/photo.jpg',
                                                ['size' => 'abc']);
    $this->apiProxyMock->verify();
  }

  public function testGetImageUrlSizeTooSmall() {
    $this->expectFilenameTranslation('/gs/mybucket/photo.jpg', 'some_blob_key');
    $this->setExpectedException(
        '\InvalidArgumentException',
        '$options[\'size\'] must be >= 0 and <= 1600. Actual value: -1');
    $url = CloudStorageTools::getImageServingUrl('gs://mybucket/photo.jpg',
                                                ['size' => -1]);
    $this->apiProxyMock->verify();
  }

  public function testGetImageUrlSizeTooBig() {
    $this->expectFilenameTranslation('/gs/mybucket/photo.jpg', 'some_blob_key');
    $this->setExpectedException(
        '\InvalidArgumentException',
        '$options[\'size\'] must be >= 0 and <= 1600. Actual value: 1601');
    $url = CloudStorageTools::getImageServingUrl('gs://mybucket/photo.jpg',
                                                ['size' => 1601]);
    $this->apiProxyMock->verify();
  }

  public function testGetImageUrlSecureUrlWrongType() {
    $this->expectFilenameTranslation('/gs/mybucket/photo.jpg', 'some_blob_key');
    $this->setExpectedException(
        '\InvalidArgumentException',
        '$options[\'secure_url\'] must be a boolean. Actual type: integer');
    $url = CloudStorageTools::getImageServingUrl('gs://mybucket/photo.jpg',
                                                ['secure_url' => 5]);
    $this->apiProxyMock->verify();
  }

  # getImageServingUrl success case.
  public function testGetImageUrlSimpleSuccess() {
    $this->expectFilenameTranslation('/gs/mybucket/photo.jpg', 'some_blob_key');
    $req = new \google\appengine\ImagesGetUrlBaseRequest();
    $resp = new \google\appengine\ImagesGetUrlBaseResponse();
    $req->setBlobKey('some_blob_key');
    $req->setCreateSecureUrl(false);
    $resp->setUrl('http://magic-url');
    $this->apiProxyMock->expectCall('images',
                                    'GetUrlBase',
                                    $req,
                                    $resp);

    $url = CloudStorageTools::getImageServingUrl('gs://mybucket/photo.jpg');
    $this->assertEquals('http://magic-url', $url);
    $this->apiProxyMock->verify();
  }

  public function testGetImageUrlWithSizeAndCropSuccess() {
    $this->expectFilenameTranslation('/gs/mybucket/photo.jpg', 'some_blob_key');
    $req = new \google\appengine\ImagesGetUrlBaseRequest();
    $resp = new \google\appengine\ImagesGetUrlBaseResponse();
    $req->setBlobKey('some_blob_key');
    $req->setCreateSecureUrl(false);
    $resp->setUrl('http://magic-url');
    $this->apiProxyMock->expectCall('images',
                                    'GetUrlBase',
                                    $req,
                                    $resp);

    $url = CloudStorageTools::getImageServingUrl(
        'gs://mybucket/photo.jpg', ['size' => 40, 'crop' => true]);
    $this->assertEquals('http://magic-url=s40-c', $url);
    $this->apiProxyMock->verify();
  }

  # getImageServingUrl backend error tests.
  private function executeGetImageUrlErrorTest($error_code, $expected_message) {
    $this->expectFilenameTranslation('/gs/mybucket/photo.jpg', 'some_blob_key');
    $req = new \google\appengine\ImagesGetUrlBaseRequest();
    $resp = new \google\appengine\ImagesGetUrlBaseResponse();
    $req->setBlobKey('some_blob_key');
    $req->setCreateSecureUrl(false);
    $exception = new \google\appengine\runtime\ApplicationError(
        $error_code, 'a message');

    $this->setExpectedException(
        '\google\appengine\api\cloud_storage\CloudStorageException',
        $expected_message);
    $this->apiProxyMock->expectCall('images',
                                    'GetUrlBase',
                                    $req,
                                    $exception);
    CloudStorageTools::getImageServingUrl('gs://mybucket/photo.jpg');
    $this->apiProxyMock->verify();
  }

  public function testGetImageUrlUnspecifiedError() {
    $this->executeGetImageUrlErrorTest(
        ImagesServiceError\ErrorCode::UNSPECIFIED_ERROR,
        'Unspecified error with image.');
  }

  public function testGetImageUrlBadTransform() {
    $this->executeGetImageUrlErrorTest(
        ImagesServiceError\ErrorCode::BAD_TRANSFORM_DATA,
        'Bad image transform data.');
  }

  public function testGetImageUrlNotImage() {
    $this->executeGetImageUrlErrorTest(
        ImagesServiceError\ErrorCode::NOT_IMAGE,
        'Not an image.');
  }

  public function testGetImageUrlBadImage() {
    $this->executeGetImageUrlErrorTest(
        ImagesServiceError\ErrorCode::BAD_IMAGE_DATA,
        'Bad image data.');
  }

  public function testGetImageUrlImageTooLarge() {
    $this->executeGetImageUrlErrorTest(
        ImagesServiceError\ErrorCode::IMAGE_TOO_LARGE,
        'Image too large.');
  }

  public function testGetImageUrlInvalidBlobKey() {
    $this->executeGetImageUrlErrorTest(
        ImagesServiceError\ErrorCode::INVALID_BLOB_KEY,
        'Invalid blob key for image.');
  }

  public function testGetImageUrlAccessDenied() {
    $this->executeGetImageUrlErrorTest(
        ImagesServiceError\ErrorCode::ACCESS_DENIED,
        'Access denied to image.');
  }

  public function testGetImageUrlObjectNotFound() {
    $this->executeGetImageUrlErrorTest(
        ImagesServiceError\ErrorCode::OBJECT_NOT_FOUND,
        'Image object not found.');
  }

  public function testGetImageUrlUnknownErrorCode() {
    $this->executeGetImageUrlErrorTest(999, 'Images Error Code: 999');
  }

  // deleteImageServingUrl tests.

  public function testDeleteImageUrlInvalidFilenameType() {
    $this->setExpectedException('\InvalidArgumentException',
        'filename must be a string. Actual type: integer');
    $url = CloudStorageTools::deleteImageServingUrl(2468);
  }

  public function testDeleteImageUrlSuccess() {
    $this->expectFilenameTranslation('/gs/mybucket/photo.jpg', 'some_blob_key');
    $req = new \google\appengine\ImagesDeleteUrlBaseRequest();
    $resp = new \google\appengine\ImagesDeleteUrlBaseResponse();
    $req->setBlobKey('some_blob_key');
    $this->apiProxyMock->expectCall('images',
                                    'DeleteUrlBase',
                                    $req,
                                    $resp);

    CloudStorageTools::deleteImageServingUrl('gs://mybucket/photo.jpg');
    $this->apiProxyMock->verify();
  }

  public function testDeleteImageUrlAccessDenied() {
    $this->expectFilenameTranslation('/gs/mybucket/photo.jpg', 'some_blob_key');
    $req = new \google\appengine\ImagesDeleteUrlBaseRequest();
    $resp = new \google\appengine\ImagesDeleteUrlBaseResponse();
    $req->setBlobKey('some_blob_key');
    $exception = new \google\appengine\runtime\ApplicationError(
        ImagesServiceError\ErrorCode::ACCESS_DENIED, 'a message');

    $this->setExpectedException(
        '\google\appengine\api\cloud_storage\CloudStorageException',
        'Access denied to image.');
    $this->apiProxyMock->expectCall('images',
                                    'DeleteUrlBase',
                                    $req,
                                    $exception);
    CloudStorageTools::deleteImageServingUrl('gs://mybucket/photo.jpg');
    $this->apiProxyMock->verify();
  }
}

