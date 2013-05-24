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
 * Google Cloud Sql PHP Session Handler.
 *
 * Based on the session handler described at http://phpsecurity.org/code/ch08-2
 *
 * Provides a handler to record php sessions in a Google Cloud SQL database.
 * To use this handler the database table needs to be created using the
 * following SQL statement.
 *
 * CREATE TABLE sessions
 * (
 *   id varchar(40) NOT NULL,
 *   access int(10) unsigned,
 *   data text,
 *   PRIMARY KEY (id)
 * );
 *
 * Configure the session handler early in your script (before calling
 * session_start) by calling
 *
 * require_once "google/appengine/ext/session/CloudSqlSessionHandler.php";
 *
 * $instance = 'my_cloud_sql_instance';
 * $user = 'my_user_name';
 * $passwd = 'my_password';
 * $db = 'my_databse';
 *
 * google\appengine\ext\session\configureCloudSqlSessionHandler($instance,
 *     $user, $passwd, $db);
 *
 */

namespace google\appengine\ext\session;

/**
 * We use a DAO model for accessing the sql commands so that we can mock them
 * out in the test.
 */
class Mysql {
  /**
   * Connects to Mysql database.
   * @param string $host Host to connect to
   * @param string $user Username to authenticate
   * @param string $password Password to authenticate
   * @return link Link to the Mysql instance
   */
  public function connect($host, $user, $password) {
    return mysql_connect($host, $user, $password);
  }

  /**
   * Selects a Mysql database.
   * @param string $db Database to select
   * @param link $link Instance link to use
   * @return bool true if successful, false otherwise
   */
  public function select_db($db, $link) {
    return mysql_select_db($db, $link);
  }

  /**
   * Close a link to a Mysql instance.
   * @param link $link Link to close
   * @return bool true if successful, false otherwise
   */
  public function close($link) {
    return mysql_close($link);
  }

  /**
   * Escape a string for insertion in the database.
   * @param string $str String to escape
   * @param link $link Link to the Mysql instance
   * @return string The escaped string
   */
  public function escape_string($str, $link) {
    return mysql_real_escape_string($str, $link);
  }

  /**
   * Run a database query.
   * @param string $query Query to run
   * @param link $link Mysql instance to run query against
   * @return resource The query result
   */
  public function query($query, $link) {
    return mysql_query($query, $link);
  }

  /**
   * Give the number of rows in a query result resource.
   * @param resource $result Result to operate on
   * @return int Number of rows in the result
   */
  public function num_rows($result) {
    return mysql_num_rows($result);
  }

  /**
   * Fetches an associative array of results from a result resource.
   * @param resource $result Result to return array for
   * @return array Associative array for result row
   */
  public function fetch_assoc($result) {
    return mysql_fetch_assoc($result);
  }
}

class CloudSqlSessionHandler implements \SessionHandlerInterface {

  private $link = null;  // The connection to the database.
  private $instanceName = null;
  private $userName = "";
  private $password = "";
  private $db = "session_data";
  private $table = "sessions";
  private $mysql;

  /**
   * Constructs the session handler instance.
   * @param string $host Hostname to connect too
   * @param string $usernName Username to authenticate with
   * @param string $password Password to authenticate with
   * @param string $db Database to select
   * @param Mysql $mysql Optional Mysql class instance for stubbing in test
   */
  public function __construct($host, $userName, $password, $db, $mysql=null) {
    if (!isset($host) || trim($host)==='') {
      throw new \InvalidArgumentException("host cannot be null or empty.");
    }

    $this->instanceName = $host;

    if (isset($userName)) {
      $this->userName = $userName;
    }

    if (isset($password)) {
      $this->password = $password;
    }

    if (isset($db)) {
      $this->db = $db;
    }

    // Allow the database connection to be mocked for testing.
    if (isset($mysql)) {
      $this->mysql = $mysql;
    } else {
      $this->mysql = new Mysql();
    }
  }

  /**
   * Opens the session handler.
   * @param string $savePath Not used
   * @param string $sessionName Not used
   * @return bool true if successful, false otherwise
   */
  public function open($savePath, $sessionName) {
    $this->link = $this->mysql->connect($this->instanceName,
                                        $this->userName,
                                        $this->password);
    if ($this->link) {
      return $this->mysql->select_db($this->db, $this->link);
    }
    return false;
  }

  /**
   * Closes the session handler.
   * @return bool true if successful, false otherwise
   */
  public function close() {
    return $this->mysql->close($this->link);
  }

  /**
   * Read an element from Memcache with the given ID.
   * @param string $id Session ID associated with the data to be retrieved
   * @return string data associated with that ID or empty string otherwise
   */
  public function read($id) {
    $id = $this->mysql->escape_string($id, $this->link);

    $query = "select data from $this->table where id = '$id'";

    if ($result = $this->mysql->query($query, $this->link)) {
      if ($this->mysql->num_rows($result)) {
        $record = $this->mysql->fetch_assoc($result);
        return $record['data'];
      }
    }
    return '';
  }

  /**
   * Write an element to Cloud SQL with the given ID and data.
   * @param string $id Session ID associated with the data to be stored
   * @param string $data Data to be stored
   * @return bool true if successful, false otherwise
   */
  public function write($id, $data) {
    $access = time();
    $id = $this->mysql->escape_string($id, $this->link);
    $access = $this->mysql->escape_string($access, $this->link);
    $data = $this->mysql->escape_string($data, $this->link);
    $query = "replace into $this->table values ('$id', '$access', '$data')";
    return $this->mysql->query($query, $this->link);
  }

  /**
   * Destroy the data associated with a particular session ID.
   * @param string $id Session ID associated with the data to be destroyed
   * @return bool true if successful, false otherwise
   */
  public function destroy($id) {
    $id = $this->mysql->escape_string($id, $this->link);
    $query = "delete from $this->table where id = '$id'";
    return $this->mysql->query($query, $this->link);
  }

  /**
   * Remove data that has expired.
   * @param int $maxlifetime Maximum age for data in the session handler
   * @return bool true if successful, false otherwise
   */
  public function gc($maxlifetime) {
    $old_time = time() - $maxlifetime;
    $old_time = $this->mysql->escape_string($old_time, $this->link);
    $query = "delete from $this->table where access < '$old_time'";
    return $this->mysql->query($query, $this->link);
  }
}

/**
 * Configure the session handler to use a Cloud Storage Database.
 * @param string $instanceName Cloud SQL instance name to connect to
 * @param string $userName Username to authenticate with
 * @param string $password Password to authenticate with
 * @param string $db Database to select
 * @param Mysql $mysql Mysql class instance for mocking in test
 */
function configureCloudSqlSessionHandler($instanceName,
  $userName, $password, $db, $mysql = null) {
  $handler = new CloudSqlSessionHandler($instanceName, $userName, $password,
      $db, $mysql);

  session_set_save_handler($handler, true);
}

