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
 * Return true if the first paramater contains the second parameter at the end
 *
 * @param string $input The input string which may contain the suffix
 * @param string $suffix The string to look for at the end of the input
 *
 * @return true if the input contains the suffix at the end or false otherwise
 */
function endsWith($input, $suffix) {
  return substr($input, -strlen($suffix)) === $suffix;
}