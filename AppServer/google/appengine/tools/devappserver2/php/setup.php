<?php

function _gae_syslog($priority, $format_string, $message) {
  // TODO(bquinlan): Use the logs service to persist this message.
}

$setup = function() {
  $setupGaeExtension = function() {
    $allowed_buckets = '';
    $ini_file = getenv('APPLICATION_ROOT') . DIRECTORY_SEPARATOR . 'php.ini';
    $config_values = @parse_ini_file($ini_file);
    if ($config_values &&
        array_key_exists('google_app_engine.allow_include_gs_buckets',
                         $config_values)) {
      $allowed_buckets =
          $config_values['google_app_engine.allow_include_gs_buckets'];
    }
    define('GAE_INCLUDE_REQUIRE_GS_STREAMS',
           // All values are considered true except the empty string.
           $allowed_buckets ? 1 : 0);
    define('GAE_INCLUDE_GS_BUCKETS', $allowed_buckets);

    unset($_ENV['APPLICATION_ROOT']);
    unset($_SERVER['APPLICATION_ROOT']);
  };

  $configureDefaults = function() {
    if (!ini_get('date.timezone')) {
      date_default_timezone_set('UTC');
    }
  };

  $updateScriptFilename = function() {
    putenv('SCRIPT_FILENAME=' . getenv('REAL_SCRIPT_FILENAME'));
    $_ENV['SCRIPT_FILENAME'] = getenv('REAL_SCRIPT_FILENAME');

    $relativePath = dirname(getenv('REAL_SCRIPT_FILENAME'));
    // $actualPath = full path to file, discovered using
    // stream_resolve_include_path checking include paths against
    // $relativePath to see if directory exists.
    $actualPath = stream_resolve_include_path($relativePath);
    chdir($actualPath);

    $_SERVER['SCRIPT_FILENAME'] = getenv('REAL_SCRIPT_FILENAME');
    putenv('REAL_SCRIPT_FILENAME');
    unset($_ENV['REAL_SCRIPT_FILENAME']);
    unset($_SERVER['REAL_SCRIPT_FILENAME']);
  };

  $setupApiProxy = function() {
    require_once 'google/appengine/runtime/ApiProxy.php';
    require_once 'google/appengine/runtime/RemoteApiProxy.php';
    \google\appengine\runtime\ApiProxy::setApiProxy(
      new \google\appengine\runtime\RemoteApiProxy(
        getenv('REMOTE_API_PORT'), getenv('REMOTE_REQUEST_ID')));
    putenv('REMOTE_API_PORT');
    putenv('REMOTE_REQUEST_ID');
    unset($_SERVER['REMOTE_API_PORT']);
    unset($_SERVER['REMOTE_REQUEST_ID']);
    unset($_ENV['REMOTE_API_PORT']);
    unset($_ENV['REMOTE_REQUEST_ID']);
  };

  $setupBuiltins = function() {
    require_once 'google/appengine/runtime/Setup.php';
  };
  $setupGaeExtension();
  $configureDefaults();
  $updateScriptFilename();
  $setupApiProxy();
  $setupBuiltins();
};
$setup();
unset($setup);
// Use require rather than include so a missing script produces a fatal error
// instead of a warning.
require($_ENV['SCRIPT_FILENAME']);
