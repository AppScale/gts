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
 * Various utilities for working with Strings.
 *
 */
namespace google\appengine\util;

/**
 * Return true if the first paramater contains the second parameter at the end.
 *
 * @param string $input The input string which may contain the suffix.
 * @param string $suffix The string to look for at the end of the input.
 *
 * @return boolean <code>true</code> iff the input contains the suffix at the
 * end.
 */
function endsWith($input, $suffix) {
  return substr($input, -strlen($suffix)) === $suffix;
}

/**
 * @param string $input The string which may contain the prefix at the start.
 * @param string $prefix The string to look for at the start of the input.
 *
 * @return boolean <code>true</code> iff the input contains the prefix at the
 * start.
 */
function startsWith($input, $prefix) {
  return substr($input, 0, strlen($prefix)) === $prefix;
}
