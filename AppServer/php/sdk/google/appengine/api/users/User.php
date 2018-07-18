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

require_once 'google/appengine/util/string_util.php';

use \google\appengine\util as util;

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
 * Federated identity and federated provider are only avaliable for
 * federated users.
 */
final class User {
  private $user_id = null;
  private $federated_identity = null;
  private $federated_provider = null;

  /**
   * Constructor.
   *
   * @param string $email An optional string of the user's email address. It
   *               defaults to the current user's email address.
   * @param string $federated_identity The federated identity of user. It
   *               defaults to the current user's federated identity.
   * @param string $federated_provider The federated provider url of user.
   *
   * @throws \InvalidArgumentException Thrown if both email and federated
   * identity are empty.
   */
  public function __construct(
      $email = null,
      $federated_identity = null,
      $federated_provider = null,
      $user_id = null) {

    $auth_domain = getenv('AUTH_DOMAIN');
    assert($auth_domain !== FALSE);

    if ($email === null and $federated_identity === null) {
      throw new \InvalidArgumentException(
          'One of $email or $federated_identity must be set.');
    }

    $this->email = $email;
    $this->federated_identity = $federated_identity;
    $this->federated_provider = $federated_provider;
    $this->auth_domain = $auth_domain;
    $this->user_id = $user_id;
  }

  /**
   * Return this user's nickname.
   *
   * The nickname will be a unique, human readable identifier for this user
   * with respect to this application. It will be an email address for some
   * users, part of the email address for some users, and the federated identity
   * for federated users who have not asserted an email address.
   *
   * @return string The user's nickname.
   */
  public function getNickname() {
    if ($this->email != null && $this->auth_domain != null &&
        util\endsWith($this->email, $this->auth_domain)) {
      $suffixLen = strlen($this->auth_domain) + 1;
      return substr($this->email, 0, -$suffixLen);
    } elseif ($this->federated_identity) {
      return $this->federated_identity;
    } else {
      return $this->email;
    }
  }

  /**
   * Return this user's email address.
   *
   * @return string The user's email address.
   */
  public function getEmail() {
    return $this->email;
  }

  /**
   * Return either a permanent unique identifying string or null.
   *
   * If the email address was set explicity, this will return null.
   *
   * @return string The user's UserId.
   */
  public function getUserId() {
    return $this->user_id;
  }

  /**
   * Return this user's auth domain.
   *
   * This method is internal and should not be used by client applications.
   *
   * @return string The user's authentication domain.
   */
  public function getAuthDomain() {
    return $this->auth_domain;
  }

  /**
   * Return this user's federated identity, null if not a federated user.
   *
   * @return string The user's federated identity.
   */
  public function getFederatedIdentity() {
    return $this->federated_identity;
  }

  /**
   * Return this user's federated provider, null if not a federated user.
   *
   * @return string The user's federated provider.
   */
  public function getFederatedProvider() {
    return $this->federated_provider;
  }

  /**
   * Magic method that PHP uses when the object is treated like a string.
   *
   * @return string The attributes of this user.
   */
  public function  __toString() {
    $res = array();
    if ($this->email != null) {
      $res[] = sprintf("email='%s'", $this->email);
    }
    if ($this->federated_identity != null) {
      $res[] = sprintf("federated_identity='%s'", $this->federated_identity);
    }
    if ($this->user_id != null) {
      $res[] = sprintf("user_id='%s'", $this->user_id);
    }
    return sprintf('User(%s)', join(',', $res));
  }

  // TODO: PHP doesn't allow to redefine equals() operations. Need to
  // figure out how to handle this.
}  // class User
