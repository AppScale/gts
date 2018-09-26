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
 * Template for rendering the frontpage of the PHP shell.
 * TODO: get rid of the logic and use a templating system, like Smarty.
 */
require_once 'google/appengine/api/users/UserService.php';

use google\appengine\api\users\UserService;

session_start();
?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
 "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
<head>
<meta http-equiv="content-type" content="text/html; charset=utf-8" />
<title> Interactive Shell </title>
<link rel="stylesheet" type="text/css" href="/static/style.css">
<script type="text/javascript" src="/static/shell.js"></script>
</head>

<body>

<p> Interactive server-side PHP shell for
<a href="http://code.google.com/appengine/">Google App Engine</a>.
<!-- TODO: update this link with one to codesite. -->
</p>

<textarea id="output" rows="22" readonly="readonly">
<?php echo "$_SERVER[SERVER_SOFTWARE]\n"; ?>
PHP <?php echo phpversion(); ?>
</textarea>

<?php
  $salt = sprintf("%s%d", getenv("HTTP_X_APPENGINE_CITY"), mt_rand());
  $token = md5(uniqid($salt, true));
  $_SESSION['token'] = $token;
?>

<form id="form" action="shell.do" method="get">
  <nobr>
  <textarea class="prompt" id="caret" readonly="readonly" rows="4"
            onfocus="document.getElementById('statement').focus()"
            >&gt;&gt;&gt;</textarea>
  <textarea class="prompt" name="statement" id="statement" rows="4"
            onkeydown="return shell.onPromptKeyDown(event);"></textarea>
  </nobr>
  <input type="hidden" name="token" value="<?php echo $token; ?>" />
  <input type="submit" style="display: none" />
</form>

<p id="ajax-status"></p>

<p id="toolbar">
<?php $user = UserService::getCurrentUser();
if ($user) {
?>
  <span class="username"><?php echo $user->getNickname(); ?></span>
  <a href="<?php echo UserService::createLogoutURL('', "google.com");?>">log out</a>
<?php } else { ?>
  <a href="<?php echo UserService::createLoginURL('');?>">log in</a>
<?php } ?>
 | <a href="reset.do">Reset Session</a>
 | Shift-Enter for newline
 | Ctrl-Up/Down for history
 | <a href="http://code.google.com/appengine/">
      <img id="logo" src="/static/appengine_button_noborder.gif" width="120px" height="30px" /></a>
</p>

<script type="text/javascript">
document.getElementById('statement').focus();
</script>

</body>
</html>
