#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#




"""Validators for v4 datastore protocol buffers.

This module is internal and should not be used by client applications.
"""
















import re

from google.appengine.datastore import datastore_pbs


RESERVED_NAME = re.compile('^__(.*)__$')



class ValidationError(Exception):
  """Raised when validation fails."""
  pass


def _assert_condition(condition, message):
  """Asserts a validation condition and raises an error if it's not met.

  Args:
    condition: (boolean) condition to enforce
    message: error message

  Raises:
    ValidationError: if condition is not met
  """
  if not condition:
    raise ValidationError(message)


def _assert_initialized(pb):
  """Asserts that a protocol buffer is initialized.

  Args:
    pb: a protocol buffer

  Raises:
    ValidationError: if protocol buffer is not initialized
  """
  errors = []
  if not pb.IsInitialized(errors):
    _assert_condition(False, 'not initialized: %s' % '\n\t'.join(errors))


def _assert_valid_utf8(string, desc):
  """Asserts that a string is valid UTF8.

  Args:
    string: string to check
    desc: description of the string (used in error message)

  Raises:
    ValidationError: if the string is not valid UTF8
  """
  _assert_condition(datastore_pbs.is_valid_utf8(string),
                    'The %s is not valid UTF-8.' % desc)


def _assert_string_not_empty(string, desc):
  """Asserts that a string is not empty.

  Args:
    string: string to check
    desc: description of the string (used in error message)

  Raises:
    ValidationError: if the string is empty
  """
  _assert_condition(string, 'The %s is the empty string.' % desc)


def _assert_string_not_reserved(string, desc):
  """Asserts that a string is not a reserved name.

  Args:
    string: string to check
    desc: description of the string (used in error message)

  Raises:
    ValidationError: if the string is a reserved name
  """
  _assert_condition(not RESERVED_NAME.match(string),
                    'The %s "%s" is reserved.'  % (desc, string))


class _ValidationConstraint(object):
  """Container for a set of validation constraints."""

  def __init__(self, incomplete_key_path_allowed=True,
               complete_key_path_allowed=False,
               reserved_key_allowed=False):
    self.__incomplete_key_path_allowed = incomplete_key_path_allowed
    self.__complete_key_path_allowed = complete_key_path_allowed
    self.__reserved_key_allowed = reserved_key_allowed

  @property
  def incomplete_key_path_allowed(self):
    """Allow key paths to be incomplete."""
    return self.__incomplete_key_path_allowed

  @property
  def complete_key_path_allowed(self):
    """Allow key paths to be complete."""
    return self.__complete_key_path_allowed

  @property
  def reserved_key_allowed(self):
    """Allow reserved keys and reserved partition ids."""
    return self.__reserved_key_allowed



CONSTRAINT_WRITE = _ValidationConstraint(
    incomplete_key_path_allowed=False,
    complete_key_path_allowed=True,
    reserved_key_allowed=False)



CONSTRAINT_ALLOCATE_KEY_ID = _ValidationConstraint(
    incomplete_key_path_allowed=True,
    complete_key_path_allowed=False,
    reserved_key_allowed=False)



class _EntityValidator(object):
  """Validator for v4 entities and keys."""

  def validate_keys(self, constraint, keys):
    """Validates a list of keys.

    Args:
      constraint: a _ValidationConstraint to apply
      keys: a list of datastore_v4_pb.Key objects

    Raises:
      ValidationError: if any of the keys is invalid
    """
    for key in keys:
      self.validate_key(constraint, key)

  def validate_key(self, constraint, key):
    """Validates a key.

    Args:
      constraint: a _ValidationConstraint to apply
      key: a datastore_v4_pb.Key

    Raises:
      ValidationError: if the key is invalid
    """
    _assert_condition(key.has_partition_id(), 'Key is missing partition id.')
    self.validate_partition_id(constraint, key.partition_id())
    num_key_path_elements = len(key.path_element_list())
    _assert_condition(num_key_path_elements, 'Key path is empty.')
    num_incomplete_elements = 0
    for path_element in key.path_element_list():
      _assert_valid_utf8(path_element.kind(), 'key path kind')
      kind = path_element.kind()
      self.validate_kind(constraint, kind)
      has_name = path_element.has_name()
      if path_element.has_id():
        _assert_condition(not has_name,
                          'Key path element has both id (%d) and name ("%s").'
                          % (path_element.id(), path_element.name()))
      else:
        if has_name:
          _assert_valid_utf8(path_element.name(), 'key path name')
          name = path_element.name()
          _assert_string_not_empty(name, 'key path name')
          if not constraint.reserved_key_allowed:
            _assert_string_not_reserved(name, 'key path name')
        else:
          num_incomplete_elements += 1
    final_element = key.path_element(num_key_path_elements - 1)
    final_element_complete = final_element.has_id() or final_element.has_name()
    if not constraint.complete_key_path_allowed:
      _assert_condition(not final_element_complete,
                        'Key path is complete: %s.'
                        % datastore_pbs.v4_key_to_string(key))
    if not constraint.incomplete_key_path_allowed:
      _assert_condition(final_element_complete,
                        'Key path is incomplete: %s.'
                        % datastore_pbs.v4_key_to_string(key))
    if final_element_complete:
      num_expected_incomplete = 0
    else:
      num_expected_incomplete = 1
    if num_incomplete_elements != num_expected_incomplete:

      _assert_condition(False, 'Key path element is incomplete: %s.'
                        % datastore_pbs.v4_key_to_string(key))

  def validate_partition_id(self, constraint, partition_id):
    """Validates a partition ID.

    Args:
      constraint: a _ValidationConstraint to apply
      partition_id: a datastore_v4_pb.PartitionId

    Raises:
      ValidationError: if the partition ID is invalid
    """
    _assert_condition(partition_id.has_dataset_id(),
                      'Partition id is missing dataset id.')
    if partition_id.has_dataset_id():
      self.validate_partition_id_dimension(constraint,
                                           partition_id.dataset_id(),
                                           'dataset id')
    if partition_id.has_namespace():
      self.validate_partition_id_dimension(constraint, partition_id.namespace(),
                                           'namespace')

  def validate_partition_id_dimension(self, constraint, partition_dimension,
                                      desc):
    """Validates a dimension (namespace or dataset) or a partition ID.

    Args:
      constraint: a _ValidationConstraint to apply
      partition_dimension: string representing one dimension of a partition ID
      desc: description of the dimension (used in error messages)

    Raises:
      ValidationError: if the partition ID dimension is invalid
    """
    _assert_valid_utf8(partition_dimension, desc)
    _assert_string_not_empty(partition_dimension, desc)
    if not constraint.reserved_key_allowed:
      _assert_string_not_reserved(partition_dimension, desc)
    _assert_condition('!' not in partition_dimension,
                      'The %s "%s" contains invalid character \'!\'.'
                      % (desc, partition_dimension))

  def validate_kind(self, constraint, kind):
    """Validates a kind.

    Args:
      constraint: a _ValidationConstraint to apply
      kind: kind string

    Raises:
      ValidationError: if the kind is invalid
    """
    _assert_string_not_empty(kind, 'kind')
    if not constraint.reserved_key_allowed:
      _assert_string_not_reserved(kind, 'kind')


__entity_validator = _EntityValidator()


def get_entity_validator():
  """Validator for entities and keys."""
  return __entity_validator


class _ServiceValidator(object):
  """Validator for request/response protos."""

  def __init__(self, entity_validator):
    self.__entity_validator = entity_validator

  def validate_allocate_ids_req(self, req):
    _assert_initialized(req)
    _assert_condition(not req.allocate_list() or not req.reserve_list(),
                      'Cannot reserve and allocate ids in the same request.')
    self.__entity_validator.validate_keys(CONSTRAINT_ALLOCATE_KEY_ID,
                                          req.allocate_list())
    self.__entity_validator.validate_keys(CONSTRAINT_WRITE,
                                          req.reserve_list())



__service_validator = _ServiceValidator(__entity_validator)


def get_service_validator():
  """Returns a validator for v4 service request/response protos.

  Returns:
    a _ServiceValidator
  """
  return __service_validator
