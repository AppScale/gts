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


"""Provides utility methods used by modules in the FTS API stub."""



import datetime
import re

from google.appengine.datastore import document_pb

from google.appengine.api.search import QueryParser


DEFAULT_MAX_SNIPPET_LENGTH = 160

TEXT_DOCUMENT_FIELD_TYPES = [
    document_pb.FieldValue.ATOM,
    document_pb.FieldValue.TEXT,
    document_pb.FieldValue.HTML,
    ]

TEXT_QUERY_TYPES = [
    QueryParser.STRING,
    QueryParser.TEXT,
    ]

NUMBER_DOCUMENT_FIELD_TYPES = [
    document_pb.FieldValue.NUMBER,
    ]


BASE_DATE = datetime.datetime(1970, 1, 1, tzinfo=None)


class UnsupportedOnDevError(Exception):
  """Indicates attempt to perform an action unsupported on the dev server."""


def GetFieldInDocument(document, field_name):
  """Find and return the first field with the provided name in the document."""
  for f in document.field_list():
    if f.name() == field_name:
      return f
  return None


def GetAllFieldInDocument(document, field_name):
  """Find and return all fields with the provided name in the document."""
  fields = []
  for f in document.field_list():
    if f.name() == field_name:
      fields.append(f)
  return fields


def AddFieldsToDocumentPb(doc_id, fields, document):
  """Add the id and fields to document.

  Args:
    doc_id: The document id.
    fields: List of tuples of field name, value and optionally type.
    document: The document to add the fields to.
  """
  if doc_id is not None:
    document.set_id(doc_id)
  for field_tuple in fields:
    name = field_tuple[0]
    value = field_tuple[1]
    field = document.add_field()
    field.set_name(name)
    field_value = field.mutable_value()
    field_value.set_string_value(value)
    if len(field_tuple) > 2:
      field_value.set_type(field_tuple[2])


def GetFieldCountInDocument(document, field_name):
  count = 0
  for field in document.field_list():
    if field.name() == field_name:
      count += 1
  return count


def GetFieldValue(field):
  """Returns the value of a field as the correct type.

  Args:
    field: The field whose value is extracted.  If the given field is None, this
      function also returns None. This is to make it easier to chain with
      GetFieldInDocument().

  Returns:
    The value of the field with the correct type (float for number fields,
    datetime.datetime for date fields, etc).

  Raises:
    TypeError: if the type of the field isn't recognized.
  """
  if not field:
    return None
  value = field.value().string_value()
  value_type = field.value().type()

  if value_type in TEXT_DOCUMENT_FIELD_TYPES:
    return value
  if value_type == document_pb.FieldValue.DATE:
    return DeserializeDate(value)
  if value_type == document_pb.FieldValue.NUMBER:
    return float(value)
  raise TypeError('No conversion defined for type %s' % value_type)


def EpochTime(date):
  """Returns millisecond epoch time for a date or datetime."""
  if isinstance(date, datetime.datetime):
    td = date - BASE_DATE
  else:
    td = date - BASE_DATE.date()
  milliseconds_since_epoch = long(
      (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**3)
  return milliseconds_since_epoch


def SerializeDate(date):
  return str(EpochTime(date))


def DeserializeDate(date_str):



  if re.match(r'^\d+\-\d+\-\d+$', date_str):
    return datetime.datetime.strptime(date_str, '%Y-%m-%d')
  else:
    dt = BASE_DATE + datetime.timedelta(milliseconds=long(date_str))
    return dt


def Repr(class_instance, ordered_dictionary):
  """Generates an unambiguous representation for instance and ordered dict."""
  return 'search.%s(%s)' % (class_instance.__class__.__name__, ', '.join(
      ["%s='%s'" % (key, value)
       for (key, value) in ordered_dictionary if value]))


def TreeRepr(tree, depth=0):
  """Generate a string representation of an ANTLR parse tree for debugging."""

  def _NodeRepr(node):
    text = str(node.getType())
    if node.getText():
      text = '%s: %s' % (text, node.getText())
    return text

  children = ''
  if tree.children:
    children = '\n' + '\n'.join([TreeRepr(child, depth=depth+1)
                                 for child in tree.children if child])
  return depth * '  ' + _NodeRepr(tree) + children
