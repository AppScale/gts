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
 * An API for fetching information about and controlling App Engine Modules.
 *
 */

namespace google\appengine\api\modules;

require_once 'google/appengine/api/modules/modules_service_pb.php';
require_once "google/appengine/api/modules/InvalidModuleStateException.php";
require_once "google/appengine/api/modules/ModulesException.php";
require_once "google/appengine/api/modules/TransientModulesException.php";
require_once 'google/appengine/runtime/ApiProxy.php';
require_once 'google/appengine/runtime/ApplicationError.php';

use \google\appengine\runtime\ApiProxy;
use \google\appengine\runtime\ApplicationError;
use \google\appengine\GetDefaultVersionRequest;
use \google\appengine\GetDefaultVersionResponse;
use \google\appengine\GetHostnameRequest;
use \google\appengine\GetHostnameResponse;
use \google\appengine\GetModulesRequest;
use \google\appengine\GetModulesResponse;
use \google\appengine\GetNumInstancesRequest;
use \google\appengine\GetNumInstancesResponse;
use \google\appengine\GetVersionsRequest;
use \google\appengine\GetVersionsResponse;
use \google\appengine\ModulesServiceError\ErrorCode;
use \google\appengine\SetNumInstancesRequest;
use \google\appengine\SetNumInstancesResponse;
use \google\appengine\StartModuleRequest;
use \google\appengine\StartModuleResponse;
use \google\appengine\StopModuleRequest;
use \google\appengine\StopModuleResponse;

final class ModulesService {
  private static function errorCodeToException($error) {
    switch($error) {
      case ErrorCode::INVALID_MODULE:
        return new ModulesException('Invalid module.');
      case ErrorCode::INVALID_VERSION:
        return new ModulesException('Invalid version.');
      case ErrorCode::INVALID_INSTANCES:
        return new ModulesException('Invalid instances.');
      case ErrorCode::TRANSIENT_ERROR:
        return new TransientModulesException();
      case ErrorCode::UNEXPECTED_STATE:
        return new InvalidModuleStateException();
      default:
        return new ModulesException('Error Code: ' . $error);
    }
  }

  /**
   * Gets the name of the currently running module.
   *
   * @return string The name of the current module. For example, if this is
   * version "v1" of module "module5" for app "my-app", this function
   * will return "module5".
   */
  public static function getCurrentModuleName() {
    return $_SERVER['CURRENT_MODULE_ID'];
  }

  /**
   * Gets the version of the currently running module.
   *
   * @return string The name of the current module. For example, if this is
   * version "v1" of module "module5" for app "my-app", this function
   * will return "v1".
   */
  public static function getCurrentVersionName() {
    return explode('.', $_SERVER['CURRENT_VERSION_ID'])[0];
  }

  /**
   * Gets the id of the currently running instance.
   *
   * @return string The name of the current module. For example, if this is
   * instance 2 of version "v1" of module "module5" for app "my-app", this
   * function will return "2". Will return null for automatically-scaled
   * modules.
   */
  public static function getCurrentInstanceId() {
    if (array_key_exists('INSTANCE_ID', $_SERVER)) {
      return $_SERVER['INSTANCE_ID'];
    }
    return null;
  }

  /**
   * Gets an array of all the modules for the application.
   *
   * @return string[] An array of string containing the names of the modules
   * associated with the application. The 'default' module will be included if
   * it exists, as will the name of the module that is associated with the
   * instance that calls this function.
   */
  public static function getModules() {
    $req = new GetModulesRequest();
    $resp = new GetModulesResponse();

    ApiProxy::makeSyncCall('modules', 'GetModules', $req, $resp);
    return $resp->getModuleList();
  }

  /**
   * Get an array of all versions associated with a module.
   *
   * @param string $module The name of the module to retrieve the versions for.
   * If null then the versions for the current module will be retrieved.
   *
   * @return string[] An array of strings containing the names of versions
   * associated with the module. The current version will also be included in
   * this list.
   *
   * @throws \InvalidArgumentException If $module is not a string.
   * @throws ModulesException If the given $module isn't valid.
   * @throws TransientModulesException if there is an issue fetching the
   * information.
   */
  public static function getVersions($module=null) {
    $req = new GetVersionsRequest();
    $resp = new GetVersionsResponse();

    if ($module !== null) {
      if (!is_string($module)) {
        throw new \InvalidArgumentException(
            '$module must be a string. Actual type: ' . gettype($module));
      }
      $req->setModule($module);
    }

    try {
      ApiProxy::makeSyncCall('modules', 'GetVersions', $req, $resp);
    } catch (ApplicationError $e) {
      throw errorCodeToException($e->getApplicationError());
    }
    return $resp->getVersionList();
  }

  /**
   * Get the default version of a module.
   *
   * @param string $module The name of the module to retrieve the default
   * versions for. If null then the default versions for the current module
   * will be retrieved.
   *
   * @return string The default version of the module.
   *
   * @throws \InvalidArgumentException If $module is not a string.
   * @throws ModulesException If the given $module is invalid or if no default
   * version could be found.
   */
  public static function getDefaultVersion($module=null) {
    $req = new GetDefaultVersionRequest();
    $resp = new GetDefaultVersionResponse();

    if ($module !== null) {
      if (!is_string($module)) {
        throw new \InvalidArgumentException(
            '$module must be a string. Actual type: ' . gettype($module));
      }
      $req->setModule($module);
    }

    try {
      ApiProxy::makeSyncCall('modules', 'GetDefaultVersion', $req, $resp);
    } catch (ApplicationError $e) {
      throw errorCodeToException($e->getApplicationError());
    }
    return $resp->getVersion();
  }

  /**
   * Get the number of instances set for a version of a module.
   *
   * This function does not work on automatically-scaled modules.
   *
   * @param string $module The name of the module to retrieve the count for. If
   * null then the count for the current module will be retrieved.
   *
   * @param string $version The version of the module to retrieve the count for.
   * If null then the count for the version of the current instance will be
   * retrieved.
   *
   * @return integer The number of instances set for the current module
   * version.
   *
   * @throws \InvalidArgumentException If $module or $version is not a string.
   * @throws ModulesException if the given combination of $module and $version
   * is invalid.
   */
  public static function getNumInstances($module=null, $version=null) {
    $req = new GetNumInstancesRequest();
    $resp = new GetNumInstancesResponse();

    if ($module !== null) {
      if (!is_string($module)) {
        throw new \InvalidArgumentException(
            '$module must be a string. Actual type: ' . gettype($module));
      }
      $req->setModule($module);
    }

    if ($version !== null) {
      if (!is_string($version)) {
        throw new \InvalidArgumentException(
            '$version must be a string. Actual type: ' . gettype($version));
      }
      $req->setVersion($version);
    }

    try {
      ApiProxy::makeSyncCall('modules', 'GetNumInstances', $req, $resp);
    } catch (ApplicationError $e) {
      throw self::errorCodeToException($e->getApplicationError());
    }
    return (int) $resp->getInstances();
  }

  /**
   * Set the number of instances for a version of a module.
   *
   * This function does not work on automatically-scaled modules.
   *
   * @param string $module The name of the module to set the instance count for.
   * If null then the instance count for the current module will be set.
   *
   * @param string $version The version of the module to set the instance count
   * for. If null then the count for the version of the current instance will
   * be set.
   *
   * @throws \InvalidArgumentException If $instances is not an integer or if
   * $module or $version is not a string.
   * @throws ModulesException if the given combination of $module and $version
   * is invalid.
   * @throws TransientModulesException if there is an issue setting the
   * instance count.
  */
  public static function setNumInstances($instances,
                                         $module=null,
                                         $version=null) {
    $req = new SetNumInstancesRequest();
    $resp = new SetNumInstancesResponse();

    if (!is_int($instances)) {
      throw new \InvalidArgumentException(
          '$instances must be an integer. Actual type: ' . gettype($instances));
    }
    $req->setInstances($instances);

    if ($module !== null) {
      if (!is_string($module)) {
        throw new \InvalidArgumentException(
            '$module must be a string. Actual type: ' . gettype($module));
      }
      $req->setModule($module);
    }

    if ($version !== null) {
      if (!is_string($version)) {
        throw new \InvalidArgumentException(
            '$version must be a string. Actual type: ' . gettype($version));
      }
      $req->setVersion($version);
    }

    try {
      ApiProxy::makeSyncCall('modules', 'SetNumInstances', $req, $resp);
    } catch (ApplicationError $e) {
      throw self::errorCodeToException($e->getApplicationError());
    }
  }

  /**
   * Starts all instances of the given version of a module.
   * *
   * @param string $module The name of the module to start.
   *
   * @param string $version The version of the module to start.
   *
   * @throws \InvalidArgumentException If $module or $version is not a string.
   * @throws ModulesException if the given combination of $module and $version
   * is invalid.
   * @throws InvalidModuleStateException if the given $module is already
   * started or cannot be started.
   * @throws TransientModulesException if there is an issue starting the module
   * version.
  */
  public static function startModule($module, $version) {
    $req = new StartModuleRequest();
    $resp = new StartModuleResponse();

    if (!is_string($module)) {
      throw new \InvalidArgumentException(
          '$module must be a string. Actual type: ' . gettype($module));
    }
    $req->setModule($module);

    if (!is_string($version)) {
      throw new \InvalidArgumentException(
          '$version must be a string. Actual type: ' . gettype($version));
    }
    $req->setVersion($version);

    try {
      ApiProxy::makeSyncCall('modules', 'StartModule', $req, $resp);
    } catch (ApplicationError $e) {
      throw self::errorCodeToException($e->getApplicationError());
    }
  }

  /**
   * Stops all instances of the given version of a module.
   * *
   * @param string $module The name of the module to stop. If null then the
   * current module will be stopped.
   *
   * @param string $version The version of the module to stop. If null then the
   * current version will be stopped.
   *
   * @throws \InvalidArgumentException If $module or $version is not a string.
   * @throws ModulesException if the given combination of $module and $version
   * instance is invalid.
   * @throws InvalidModuleStateException if the given $module is already
   * stopped or cannot be stopped.
   * @throws TransientModulesException if there is an issue stopping the module
   * version.
  */
  public static function stopModule($module=null, $version=null) {
    $req = new StopModuleRequest();
    $resp = new StopModuleResponse();

    if ($module !== null) {
      if (!is_string($module)) {
        throw new \InvalidArgumentException(
            '$module must be a string. Actual type: ' . gettype($module));
      }
      $req->setModule($module);
    }

    if ($version !== null) {
      if (!is_string($version)) {
        throw new \InvalidArgumentException(
            '$version must be a string. Actual type: ' . gettype($version));
      }
      $req->setVersion($version);
    }

    try {
      ApiProxy::makeSyncCall('modules', 'StopModule', $req, $resp);
    } catch (ApplicationError $e) {
      throw self::errorCodeToException($e->getApplicationError());
    }
  }

  /**
   * Returns the hostname to use when contacting a module.
   * *
   * @param string $module The name of the module whose hostname should be
   * returned. If null then the hostname of the current module will be returned.
   *
   * @param string $version The version of the module whose hostname should be
   * returned. If null then the hostname for the version of the current
   * instance will be returned.
   *
   * @param string $instance The instance whose hostname should be returned. If
   * null then the load balanced hostname for the module will be returned. If
   * the module is not a fixed module then the instance parameter is ignored.
   *
   * @throws \InvalidArgumentException If $module or $version is not a string
   * or if $instance is not a string or integer.
   * @throws ModulesException if the given combination of $module and $instance
   * is invalid.
  */
  public static function getHostname($module=null,
                                     $version=null,
                                     $instance=null) {
    $req = new GetHostnameRequest();
    $resp = new GetHostnameResponse();

    if ($module !== null) {
      if (!is_string($module)) {
        throw new \InvalidArgumentException(
            '$module must be a string. Actual type: ' . gettype($module));
      }
      $req->setModule($module);
    }

    if ($version !== null) {
      if (!is_string($version)) {
        throw new \InvalidArgumentException(
            '$version must be a string. Actual type: ' . gettype($version));
      }
      $req->setVersion($version);
    }

    if ($instance !== null) {
      if (!is_int($instance) && !is_string($instance)) {
        throw new \InvalidArgumentException(
            '$instance must be an integer or string. Actual type: ' .
            gettype($instance));
      }
      $req->setInstance((string) $instance);
    }

    try {
      ApiProxy::makeSyncCall('modules', 'GetHostname', $req, $resp);
    } catch (ApplicationError $e) {
      throw self::errorCodeToException($e->getApplicationError());
    }

    return $resp->getHostname();
  }
}
