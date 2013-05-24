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
 * Tests for the Cloud SQL session handler.
 *
 */

namespace google\appengine\ext\session;

require_once 'google/appengine/ext/session/CloudSqlSessionHandler.php';

class CloudSqlSessionHandlerTest extends \PHPUnit_Framework_TestCase {

  public function testInvalidInstanceName() {
    $this->setExpectedException('\InvalidArgumentException');
    $handler = new CloudSqlSessionHandler('', 'user', 'password', 'database');
  }

  // TODO: Work out how to test session gc.
  public function testSession() {
    $stub = $this->getMock('Mysql', array('connect', 'select_db', 'close',
        'escape_string', 'query'));
    $host = 'my_instance';
    $user = 'user';
    $passwd = 'password';
    $db = 'database';

    $linkId = "my_link_id";
    $mySessionId = "my_session_id";
    $escapedSessionId = "escaped_session_id";

    configureCloudSqlSessionHandler($host, $user, $passwd, $db, $stub);

    // Expectations for starting the session
    $stub->expects($this->at(0))
        ->method('connect')
        ->with($this->equalTo($host),
               $this->equalTo($user),
               $this->equalTo($passwd))
        ->will($this->returnValue($linkId));

    $stub->expects($this->at(1))
        ->method('select_db')
        ->with($this->equalTo($db),
               $this->equalTo($linkId))
        ->will($this->returnValue(true));

    $stub->expects($this->at(2))
        ->method('escape_string')
        ->with($this->equalTo($mySessionId), $this->equalTo($linkId))
        ->will($this->returnValue($escapedSessionId));

    $stub->expects($this->at(3))
        ->method('query')
        ->with($this->equalTo(
            "select data from sessions where id = '$escapedSessionId'"))
        ->will($this->returnValue(false));

    // Expectations for writing & closing the session
    $escapedAccess = 'escaped_access';
    $escapedData = 'escaped_data';

    $stub->expects($this->at(4))
        ->method('escape_string')
        ->with($this->equalTo($mySessionId), $this->equalTo($linkId))
        ->will($this->returnValue($escapedSessionId));

    $stub->expects($this->at(5))
        ->method('escape_string')
        ->with($this->anything(), $this->equalTo($linkId))
        ->will($this->returnValue($escapedAccess));

    $stub->expects($this->at(6))
        ->method('escape_string')
        ->with($this->anything(), $this->equalTo($linkId))
        ->will($this->returnValue($escapedData));

    $query = "replace into sessions values ('$escapedSessionId', " .
        "'$escapedAccess', '$escapedData')";
    $stub->expects($this->at(7))
        ->method('query')
        ->with($this->equalTo($query), $this->equalTo($linkId))
        ->will($this->returnValue(true));

    $stub->expects($this->at(8))
      ->method('close')
      ->with($this->equalTo($linkId))
      ->will($this->returnValue(true));

    session_id($mySessionId);
    // Supress errors to overcome 'cannot write header' error.
    @session_start();
    $_SESSION['Foo'] = 'Bar';
    session_write_close();
  }
}


