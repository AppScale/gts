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

namespace google\appengine\api\users;

use \google\appengine\CreateLoginURLRequest;
use \google\appengine\CreateLoginURLResponse;
use \google\appengine\CreateLogoutURLRequest;
use \google\appengine\CreateLogoutURLResponse;
use \google\appengine\runtime\ApiProxy;
use \google\appengine\runtime\ApplicationError;
use \google\appengine\UserServiceError\ErrorCode;

require_once 'google/appengine/api/user_service_pb.php';
require_once 'google/appengine/api/users/User.php';
require_once 'google/appengine/api/users/UsersException.php';
require_once 'google/appengine/runtime/ApiProxy.php';
require_once 'google/appengine/runtime/ApplicationError.php';

final class UserService {
  /**
   * Computes the login URL for redirection.
   *
   * @param string $destination_url The desired final destination URL for the
   *               user once login is complete. If 'destinationURL' does not
   *               have a host specified, we will use the host from the
   *               current request.
   *
   * @param string $federated_identity The parameter is used to trigger OpenId
   *               Login flow, an empty value will trigger Google OpenID Login
   *               by default.
   *
   * @return string Login URL. If federatedIdentity is set, this will be
   *         a federated login using the specified identity. If not, this
   *         will use Google Accounts.
   *
   * @throws UsersException If there was a problem using the Users service.
   */
  public static function createLoginURL(
      $destination_url = null, $federated_identity = null) {
    $req = new CreateLoginURLRequest();
    $resp = new CreateLoginURLResponse();
    if ($destination_url !== null) {
      $req->setDestinationUrl($destination_url);
    } else {
      $req->setDestinationUrl('');
    }
    if ($federated_identity !== null) {
      $req->setFederatedIdentity($federated_identity);
    }

    try {
      ApiProxy::makeSyncCall('user', 'CreateLoginURL', $req, $resp);
    } catch (ApplicationError $e) {
      throw self::applicationErrorToException($e, $destination_url);
    }
    return $resp->getLoginUrl();
  }

  /**
   * Computes the logout URL for this request and specified destination URL,
   *  for both federated login App and Google Accounts App.
   *
   * @param string $destination_url The desired final destination
   *               URL for the user once logout is complete.
   *               If 'destinationURL' does not have a host specified, we will
   *               use the host from the current request.
   *
   * @return string Logout URL.
   *
   * @throws UsersException If there was a problem using the Users service.
   */
  public static function createLogoutURL($destination_url) {
    $req = new CreateLogoutURLRequest();
    $resp = new CreateLogoutURLResponse();
    $req->setDestinationUrl($destination_url);

    try {
      ApiProxy::makeSyncCall('user', 'CreateLogoutURL', $req, $resp);
    } catch (ApplicationError $e) {
      throw self::applicationErrorToException($e, $destination_url);
    }
    return $resp->getLogoutUrl();
  }

  /**
   * @return User The object representing the current signed in user, or null
   * if no user is signed in.
   */
  public static function getCurrentUser() {
    $email = getenv('USER_EMAIL');
    $userId =  getenv('USER_ID');
    $federatedIdentity =  getenv('FEDERATED_IDENTITY');
    $federatedProvider =  getenv('FEDERATED_PROVIDER');

    if (!$email && !$federatedIdentity) {
      return null;
    }

    if (!$federatedIdentity) {
      $federatedIdentity = null;
    }

    if (!$federatedProvider) {
      $federatedProvider = null;
    }

    // We set this to maintain compatibility with the
    // datastore_types.FromPropertyPb creation of a User object, which will set
    // an empty string for the email (since it is a required field of the
    // underlying data representation of this class in the datastore.
    if ($email === FALSE) {
      $email = '';
    }

    // User.user_id() should only return a
    // string of length > 0 or null.
    if (!$userId || $userId == '') {
      $userId = null;
    }

    return new User($email, $federatedIdentity, $federatedProvider, $userId);
  }

  /**
   * Return true if the user making this request is an admin for this
   * application, false otherwise.
   *
   * We specifically make this a separate function, and not a member function
   * of the User class, because admin status is not persisted in the
   * datastore. It only exists for the user making this request right now.
   *
   * @return boolean Whether the current user is an administrator of the
   * application.
   */
  public static function isCurrentUserAdmin() {
    return getenv('USER_IS_ADMIN') == '1';
  }

  private static function applicationErrorToException($error,
                                                      $destination_url) {
    switch ($error->getApplicationError()) {
      case ErrorCode::REDIRECT_URL_TOO_LONG:
        return new UsersException('URL too long: ' . $destination_url);
      case ErrorCode::NOT_ALLOWED:
        return new UsersException('Action not allowed.');
      default:
        return new UsersException(
            'Error code: ' . $error->getApplicationError());
    }
  }
}  // class UserService
