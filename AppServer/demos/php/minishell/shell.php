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
 * Handles the /shell.do url.
 * It executes the received statement using the globals, constants and locals 
 * stored for this user. Statements declaring classes and functions are
 * persisted and run every time.
 */

class Session {
  /**
   * Stores a serialized version of both local and global variables.
   */

  private $globals = "";
  private $locals = "";
  private $statements = array();
  private $use_statements = array();
  private $constants = "";

  function __construct() {
    $this->locals = serialize(array());
    $this->storeGlobals();
    $this->functions = get_defined_functions();
    $this->classes = get_declared_classes();
    $this->storeConstants();
  }

  /** Stores a serialized version of the globals. */
  function storeGlobals() {
    $this->globals = serialize($GLOBALS);
  }

  /** Replace the globals with the serialized stored ones. */
  function loadGlobals() {
    $GLOBALS = unserialize($this->globals);
  }

  /** Stores a serialized version of the passed locals. */
  function storeLocals($locals) {
    foreach (array("_shell_statement",
                   "_shell_session") as $nonLocal) {
      unset($locals[$nonLocal]);
    }
    $this->locals = serialize($locals);
  }

  /** Returns an array with the locals. */
  function getLocals() {
    return unserialize($this->locals);
  }

  /**
   * Stores a statement if it declares a function, a class or if it is a
   * use statment or a require/include statement.
   */
  function storeStatementIfNeeded($statement) {
    $nonSerializableTokens = array(T_CLASS, T_FUNCTION,
                                     T_REQUIRE, T_REQUIRE_ONCE,
                                     T_INCLUDE, T_INCLUDE_ONCE);
    foreach(token_get_all("<?php $statement ?>") as $token) {
      if (in_array($token[0], $nonSerializableTokens)) {
        array_push($this->statements, $statement);
      } else if ($token[0] == T_USE) {
        array_push($this->use_statements, $statement);
      }
    }
  }

  /** Stores a serialized version of the constants. */
  function storeConstants() {
    $this->constants = serialize(get_defined_constants());
  }

  /** Replace the constants with the serialized stored ones. */
  function loadConstants() {
    $constants = unserialize($this->constants);
    foreach(array_diff($constants, get_defined_constants()) as $constant=>$value) {
      define($constant, $value);
    }
  }

  static function scrubOutput($output) {
    return htmlentities($output);
  }

  /** Evaluate all saved statements.*/
  function loadStatements() {
    foreach ($this->statements as $statement) {
      ob_start(['Session', 'scrubOutput']);
      eval($statement);
      ob_clean();
    }
  }

  /** Prepend all the use statements to the given statement. */
  function prependUseStatements($statement) {
    return implode("\n", $this->use_statements) . "\n$statement";
  }

  /** Method to initialize user scope.*/
  function start() {
    // Must goes first, or otherwise the unserialized objects will be incomplete.
    $this->loadStatements();
    $this->loadGlobals();
    $this->functions = get_defined_functions();
    $this->classes = get_declared_classes();
    $this->loadConstants();
  }

  /** Method to save user scope.*/
  function end($statement, $locals) {
    $this->storeGlobals();
    $this->storeLocals($locals);
    $this->storeStatementIfNeeded($statement);
    $this->storeConstants();
  }
}

/**
 * Handler to catch exceptions raised when evaluation the code.
 * We just return the error and not the line, as they are not meaningful in this
 *  context.
 */
function error_handler($errno, $errstr, $errfile, $errline) {
    echo $errstr, "\n";
}

/**
 * Handler to catch fatal errors (like function not defined) and print them
 * nicely.
 */
function shutdown_handler() {
  $error = error_get_last();
  if($error !== NULL){
    echo $error["message"], "\n";
  }
}

/**
 * Executes a statement for the given session.
 * All locals must be prefixed with _shell_, to avoid messing up with the user's
 * local.
 */
function shell($_shell_statement, $_shell_session) {
  $_shell_session->start();
  header("Content-Type: text/html; charset=utf-8");
  extract($_shell_session->getLocals(), EXTR_SKIP);
  // Disable all error reporting, otherwise it mess with the output.
  error_reporting(0);
  // Errors are handled with an error handler and a fatal error handler, because
  // exceptions are not catchable when evaluating code.
  register_shutdown_function('shutdown_handler');
  set_error_handler('error_handler');
  ob_start(['Session', 'scrubOutput']);
  eval($_shell_session->prependUseStatements($_shell_statement));
  ob_end_flush();
  $_shell_session->end($_shell_statement, get_defined_vars());
}

session_start();
if (!isset($_SESSION["session"])) {
  $_SESSION["session"] = new Session();
}

if (isset($_SESSION['token']) && ($_GET['token'] === $_SESSION['token'])) {
  // Append a semi-colon just in case the statement doen't have one. An extra
  // semi-colon makes no harm.
  shell($_GET["statement"] . ";", $_SESSION["session"]);
} else if (!isset($_SESSION['token'])) {
  syslog(LOG_ERR, 'Missing session token');
  echo "Session token missing - Please reset your session.";
} else {
  syslog(LOG_ERR, 'Mismatch session token.');
  echo "Invalid session token - Please reset your session.";
}
