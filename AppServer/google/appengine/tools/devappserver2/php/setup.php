<?php
$setup = function() {
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
  $updateScriptFilename();
  $setupApiProxy();
  $setupBuiltins();
};
$setup();
unset($setup);
// Use require rather than include so a missing script produces a fatal error
// instead of a warning.
require($_ENV['SCRIPT_FILENAME']);
