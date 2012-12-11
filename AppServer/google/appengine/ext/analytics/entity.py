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




"""Helper file to manipulate entity keys and names."""


def EntityKind(key):
  """Given entity primary key as Reference Proto, returns entity kind.

  Args:
    key: primary key of entity in ReferenceProto form.

  Returns:
    Kind of entity in string format. Returns '' if
    kind cannot be determined in some unexpected scenario.
  """
  if key.path().element_list():
    return key.path().element_list()[-1].type()
  else:
    return ''


def EntityGroupKind(key):
  """Given entity primary key as Reference Proto, returns kind of entity group.

  Args:
    key: primary key of entity in ReferenceProto form.

  Returns:
    Kind of entity group that entity belongs to in string format.
  """
  return key.path().element(0).type()


def EntityListKind(keylist):
  """Given list of entity keys, return entity kind.

  Args:
    keylist: list of primary keys of entities in ReferenceProto form.

  Returns:
    Kind of entity. Returns 'None' if list is empty and 'Multi' if
    entities in the list are of different kinds.
  """
  kinds = map(EntityKind, keylist)
  unique_kinds = set(kinds)
  numkinds = len(unique_kinds)
  if numkinds > 1:
    return 'Multi'
  elif numkinds == 1:
    return unique_kinds.pop()
  else:
    return 'None'


def EntityGroupName(entity):
  """Given entity primary key as Reference Proto, returns entity group.

  Args:
    entity: primary key of entity in ReferenceProto form

  Returns:
    Name of entitygroup in string format.
  """
  element = entity.path().element(0)
  if element.has_id():
    return str(element.id())
  elif element.has_name():
    return element.name()
  else:

    return 'None'


def EntityFullName(entity):
  """Given entity primary key as a Reference Proto, returns full name.

  This is a concatenation of entity information along the entire
  path, and includes entity kind and entity name (or id) at each level.

  Args:
    entity: primary key of entity in ReferenceProto form

  Returns:
    Full name of entity in string format with dots delimiting each element in
    the path. Each element is represented as 'entity_kind:entity_id' or
    'entity_kind:entity_name' as applicable.
  """
  names = []
  for element in entity.path().element_list():
    if element.has_id():
      name = '%s:%s' %(element.type(), str(element.id()))
    elif element.has_name():
      name = '%s:%s' %(element.type(), str(element.name()))
    else:

      name = '%s:None' %(element.type())
    names.append(name)
  fullname = '.'.join(names)
  return fullname
