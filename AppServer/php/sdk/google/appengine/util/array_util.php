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
 * Various utilities for working with PHP arrays.
 *
 */
namespace google\appengine\util;

/**
 * Find an item in a hash table by a key value, or return null if not found.
 *
 * @param array $array - The array to search
 * @param mixed $key - The key to search for.
 *
 * @return mixed The value of the item in the array with the given key, or null
 * if not found.
 */
function FindByKeyOrNull($array, $key) {
  if (array_key_exists($key, $array)) {
    return $array[$key];
  }
  return null;
}

