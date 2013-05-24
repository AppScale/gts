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

/**
 * A user.
 *
 * We provide the email address, nickname, and id for a user.
 *
 * A nickname is a human-readable string which uniquely identifies a Google
 * user, akin to a username. It will be an email address for some users, but
 * not all.
 *
 * A user could be a Google Accounts user or a federated login user.
 *
 * federatedIdentity and federatedProvider are only avaliable for
 * federated users.
 */
class User {
  private $userId = null;
  private $federatedIdentity = null;
  private $federatedProvider = null;

  /**
   * Constructor.
   *
   * @param string email An optional string of the user's email address. It
   *               defaults to the current user's email address.
   * @param string federatedIdentity The federated identity of user. It
   *               defaults to the current user's federated identity.
   * @param string federatedProvider The federated provider url of user.
   *
   * @throws UserNotFoundError Thrown if both email and federated identity
   *         are empty.
   */
  public function __construct(
      $email = null,
      $federatedIdentity = null,
      $federatedProvider = null,
      $userId = null) {

    $authDomain = getenv('AUTH_DOMAIN');
    assert($authDomain !== FALSE);

    if ($email === null and $federatedIdentity === null) {
      throw new UserNotFoundError();
    }

    $this->email = $email;
    $this->federatedIdentity = $federatedIdentity;
    $this->federatedProvider = $federatedProvider;
    $this->authDomain = $authDomain;
    $this->userId = $userId;
  }

  /**
   * Return this user's nickname.
   *
   * The nickname will be a unique, human readable identifier for this user
   * with respect to this application. It will be an email address for some
   * users, part of the email address for some users, and the federated identity
   * for federated users who have not asserted an email address.
   */
  public function getNickname() {
    // TODO: create an utility class and endsWith() function, use it here:
    if ($this->email != null && $this->authDomain != null && substr(
        $this->email, -strlen($this->authDomain)) === $this->authDomain) {
      $suffixLen = strlen($this->authDomain) + 1;
      return substr($this->email, 0, -$suffixLen);
    } elseif ($this->federatedIdentity) {
      return $this->federatedIdentity;
    } else {
      return $this->email;
    }
  }

  /**
   * Return this user's email address.
   */
  public function getEmail() {
    return $this->email;
  }

  /**
   * Return either a permanent unique identifying string or null.
   *
   * If the email address was set explicity, this will return null.
   */
  public function getUserId() {
    return $this->userId;
  }

  /**
   * Return this user's auth domain.
   *
   * This method is internal and should not be used by client applications.
   */
  public function getAuthDomain() {
    return $this->authDomain;
  }

  /**
   * Return this user's federated identity, null if not a federated user.
   */
  public function getFederatedIdentity() {
    return $this->federatedIdentity;
  }

  /**
   * Return this user's federated provider, null if not a federated user.
   */
  public function getFederatedProvider() {
    return $this->federatedProvider;
  }

  public function  __toString() {
    $res = array();
    if ($this->email != null) {
      $res[] = sprintf("email='%s'", $this->email);
    }
    if ($this->federatedIdentity != null) {
      $res[] = sprintf("federatedIdentity='%s'", $this->federatedIdentity);
    }
    if ($this->userId != null) {
      $res[] = sprintf("userId='%s'", $this->userId);
    }
    return sprintf('User(%s)', join(',', $res));
  }

  // TODO: PHP doesn't allow to redefine equals() operations. Need to
  // figure out how to handle this.
}  // class User
