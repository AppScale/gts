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
 */

namespace google\appengine\api\app_identity;

use \google\appengine\AppIdentityServiceError\ErrorCode;
use \google\appengine\GetAccessTokenRequest;
use \google\appengine\GetAccessTokenResponse;
use \google\appengine\GetPublicCertificateForAppRequest;
use \google\appengine\GetPublicCertificateForAppResponse;
use \google\appengine\GetServiceAccountNameRequest;
use \google\appengine\GetServiceAccountNameResponse;
use \google\appengine\SignForAppRequest;
use \google\appengine\SignForAppResponse;
use \google\appengine\runtime\ApiProxy;
use \google\appengine\runtime\ApplicationError;

require_once 'google/appengine/api/app_identity/app_identity_service_pb.php';
require_once 'google/appengine/api/app_identity/AppIdentityException.php';
require_once 'google/appengine/api/app_identity/PublicCertificate.php';
require_once 'google/appengine/runtime/ApiProxy.php';
require_once 'google/appengine/runtime/ApplicationError.php';

/**
 * The AppIdentityService allows you to sign arbitrary byte
 * array using per app private key maintained by App Engine. You can also
 * retrieve a list of public certificates which can be used to
 * verify the signature.
 *
 * App Engine is responsible for maintaining per-application
 * private key. App Engine will keep rotating private keys
 * periodically. App Engine never releases these private keys externally.
 *
 * Since private keys are rotated periodically,
 * getPublicCertificates() could return a list of public
 * certificates. It's the caller's responsibility to try these
 * certificates one by one when doing signature verification.
 */
final class AppIdentityService {

  const PACKAGE_NAME = 'app_identity_service';
  const PARTITION_SEPARATOR = "~";
  const DOMAIN_SEPARATOR = ":";
  const MEMCACHE_KEY_PREFIX = '_ah_app_identity_';

  /**
   * Signs arbitrary byte array using per app private key.
   *
   * @param string $bytes_to_sign The bytes to generate the signature for.
   *
   * @throws \InvalidArgumentException If $bytes_to_sign is not a string.
   * @throws AppIdentityException If there is an error using the AppIdentity
   * service.
   *
   * @return array An array containing the elements
   * 'key_name' - the name of the key used to sign the bytes
   * 'signature' - the signature of the bytes.
   *
   */
  public static function signForApp($bytes_to_sign) {
    $req = new SignForAppRequest();
    $resp = new SignForAppResponse();

    if (!is_string($bytes_to_sign)) {
      throw new \InvalidArgumentException('$bytes_to_sign must be a string.');
    }

    $req->setBytesToSign($bytes_to_sign);

    try {
      ApiProxy::makeSyncCall(self::PACKAGE_NAME, 'SignForApp', $req, $resp);
    } catch (ApplicationError $e) {
      throw AppIdentityService::applicationErrorToException($e);
    }

    return [
      'key_name' => $resp->getKeyName(),
      'signature' => $resp->getSignatureBytes(),
    ];
  }

  /**
   * Get the service account name for the application.
   *
   * @throws AppIdentityException If there is an error using the AppIdentity
   * service.
   *
   * @return string The service account name.
   */
  public static function getServiceAccountName() {
    $req = new GetServiceAccountNameRequest();
    $resp = new GetServiceAccountNameResponse();

    try {
      ApiProxy::makeSyncCall(self::PACKAGE_NAME, 'GetServiceAccountName', $req,
          $resp);
    } catch (ApplicationError $e) {
      throw AppIdentityService::applicationErrorToException($e);
    }

    return $resp->getServiceAccountName();
  }

  /**
   * Get the list of public certifates for the application.
   *
   * @throws AppIdentityException If there is an error using the AppIdentity
   * service.
   *
   * @return PublicCertificate[] An array of the applications public
   * certificates.
   */
  public static function getPublicCertificates() {
    $req = new GetPublicCertificateForAppRequest();
    $resp = new GetPublicCertificateForAppResponse();

    try {
      ApiProxy::makeSyncCall(self::PACKAGE_NAME, 'GetPublicCertificatesForApp',
          $req, $resp);
    } catch (ApplicationError $e) {
      throw AppIdentityService::applicationErrorToException($e);
    }

    $result = [];

    foreach ($resp->getPublicCertificateListList() as $cert) {
      $result[] = new PublicCertificate($cert->getKeyName(),
                                        $cert->getX509CertificatePem());
    }

    return $result;
  }

  /**
   * Gets an OAuth2 access token for the application's service account from
   * memcache or generates and caches one by calling
   * getAccessTokenUncached($scopes)
   *
   * Each application has an associated Google account. This function returns
   * OAuth2 access token corresponding to the running app. Access tokens are
   * safe to cache and reuse until they expire.
   *
   * @param array $scopes The scopes to acquire the access token for.
   * Can be either a single string or an array of strings.
   *
   * @throws \InvalidArgumentException If $scopes is not a string or an array of
   * strings.
   * @throws AppIdentityException If there is an error using the AppIdentity
   * service.
   *
   * @return array An array with the following key/value pairs.
   * 'access_token' - The access token for the application.
   * 'expiration_time' - The expiration time for the access token.
   */
  public static function getAccessToken($scopes) {
    $memcache_key = self::MEMCACHE_KEY_PREFIX . self::DOMAIN_SEPARATOR;
    if (is_string($scopes)) {
       $memcache_key .= $scopes;
    } else if (is_array($scopes)) {
      $memcache_key .= implode(self::DOMAIN_SEPARATOR, $scopes);
    } else {
      throw new \InvalidArgumentException('Invalid scope ' . $scopes);
    }

    $memcache = new \Memcache();
    $result = $memcache->get($memcache_key);

    if ($result === False) {
      $result = self::getAccessTokenUncached($scopes);

      // Cache in memcache allowing for 5 minute clock skew.
      $memcache->set($memcache_key,
                     $result,
                     null,
                     $result['expiration_time'] - 300);
    }
    return $result;
  }

  /**
   * Get an OAuth2 access token for the applications service account without
   * caching the result. Usually getAccessToken($scopes) should be used instead
   * which calls this method and caches the result in memcache.
   *
   * @param array $scopes The scopes to acquire the access token for.
   * Can be either a single string or an array of strings.
   *
   * @throws InvalidArgumentException If $scopes is not a string or an array of
   * strings.
   * @throws AppIdentityException If there is an error using the AppIdentity
   * service.
   *
   * @return array An array with the following key/value pairs.
   * 'access_token' - The access token for the application.
   * 'expiration_time' - The expiration time for the access token.
   */
  private static function getAccessTokenUncached($scopes) {
    $req = new GetAccessTokenRequest();
    $resp = new GetAccessTokenResponse();

    if (is_string($scopes)) {
      $req->addScope($scopes);
    } else if (is_array($scopes)) {
      foreach($scopes as $scope) {
        if (is_string($scope)) {
          $req->addScope($scope);
        } else {
          throw new \InvalidArgumentException(
            'Invalid scope ' . $scope);
        }
      }
    } else {
      throw new \InvalidArgumentException('Invalid scope ' . $scopes);
    }

    try {
      ApiProxy::makeSyncCall(self::PACKAGE_NAME, 'GetAccessToken', $req, $resp);
    } catch (ApplicationError $e) {
      throw AppIdentityService::applicationErrorToException($e);
    }

    return [
        'access_token' => $resp->getAccessToken(),
        'expiration_time' => $resp->getExpirationTime(),
    ];
  }

  /**
   * Get the application id of an app.
   *
   * @return string The application id of the app.
   */
  public static function getApplicationId() {
    $app_id = getenv("APPLICATION_ID");
    $psep = strpos($app_id, self::PARTITION_SEPARATOR);
    if ($psep > 0) {
      $app_id = substr($app_id, $psep + 1);
    }
    return $app_id;
  }

  /**
   * Get the standard hostname of the default version of the app.
   *
   * @return string The standard hostname of the default version of the
   * application, or FALSE if the call failed.
   */
  public static function getDefaultVersionHostname() {
    return getenv("DEFAULT_VERSION_HOSTNAME");
  }

  /**
   * Converts an application error to the service specific exception.
   *
   * @param ApplicationError $application_error The application error
   *
   * @return mixed An exception that corresponds to the application error.
   *
   * @access private
   */
  private static function applicationErrorToException($application_error) {
    switch ($application_error->getApplicationError()) {
      case ErrorCode::UNKNOWN_SCOPE:
        return new \InvalidArgumentException(
          'An unknown scope was supplied.');
      case ErrorCode::BLOB_TOO_LARGE:
        return new \InvalidArgumentException(
          'The supplied blob was too long.');
      case ErrorCode::DEADLINE_EXCEEDED:
        return new AppIdentityException(
          'The deadline for the call was exceeded.');
      case ErrorCode::NOT_A_VALID_APP:
        return new AppIdentityException(
          'The application is not valid.');
      case ErrorCode::UNKNOWN_ERROR:
        return new AppIdentityException(
          'There was an unknown error using the AppIdentity service.');
      case ErrorCode::GAIAMINT_NOT_INITIAILIZED:
        return new AppIdentityException(
          'There was a GAIA error using the AppIdentity service.');
      case ErrorCode::NOT_ALLOWED:
        return new AppIdentityException('The call is not allowed.');
      default:
        return new AppIdentityException(
          'The AppIdentity service threw an unexpected error.');
    }
  }
}
