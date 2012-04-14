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




"""Type conversions for rdbms.

This module defines a dictionary called 'converters' which provides a mapping
for the encoders and decoders used for type conversion by rdbms.  The type of
key used in the dictionary determines whether the mapping represents an encoder
or decoder.

If the key is a Python type (from the types module) or class, the
mapping represents the callback function that will be used to encode values of
that type or class to a str for use in a database query.  The callback function
should match the following specification:

Encoder
  Args:
    arg: The argument to encode
    conversions_dict: The conversions dictionary that contains the mapping for
      this callback (useful for performing subsequent encodings for sequence
      types).

  Returns:
    The encoded value as a str.


If the key is a JDBC type constant int, the mapping represents the callback
function that will be used to decode values of that JDBC type to its respective
Python type.  The callback function should match the following specification:

Decoder
  Args:
    arg: The argument to decode.

  Returns:
    The decoded value as its appropriate Python type.
"""


import datetime
import types

from google.storage.speckle.proto import jdbc_type


class Blob(str):
  """A blob type, appropriate for storing binary data of any length."""
  pass


def SwallowArgs(func):
  """Decorator to allow a single arg function to accept multiple arguments."""

  def Decorator(arg, *unused_args):
    return func(arg)
  return Decorator


@SwallowArgs
def Bool2Str(arg):
  return str(arg).lower()


@SwallowArgs
def Unicode2Str(arg):
  return arg.encode('utf-8')


@SwallowArgs
def Datetime2Str(arg):
  return ('%d-%02d-%02d %02d:%02d:%02d.%06d' %
          (arg.year, arg.month, arg.day, arg.hour,
           arg.minute, arg.second, arg.microsecond))


@SwallowArgs
def Date2Str(arg):
  return arg.strftime('%Y-%m-%d')


@SwallowArgs
def Time2Str(arg):
  return ('%02d:%02d:%02d.%06d' %
          (arg.hour, arg.minute, arg.second, arg.microsecond))


def Tuple2Str(arg, conversions_dict):
  if len(arg) > 1:
    raise TypeError('tuples of more than 1 element are not supported.')
  arg = arg[0]
  return conversions_dict[type(arg)](arg, conversions_dict)


def Str2Unicode(arg):
  return unicode(arg, 'utf-8')


def _Strptime(arg, strptime_format):
  """Wraps strptime to provide microsecond support on Python 2.5."""
  split_arg = arg.split('.')
  datetime_obj = datetime.datetime.strptime(split_arg[0], strptime_format)
  if len(split_arg) == 2:
    datetime_obj = datetime_obj.replace(microsecond=int(split_arg[1]))
  return datetime_obj


def Str2Date(arg):
  return _Strptime(arg, '%Y-%m-%d').date()


def Str2Time(arg):
  return _Strptime(arg, '%H:%M:%S').time()


def Str2Datetime(arg):
  return _Strptime(arg, '%Y-%m-%d %H:%M:%S')


conversions = {

    types.IntType: SwallowArgs(str),
    types.LongType: SwallowArgs(str),
    types.FloatType: SwallowArgs(str),
    types.TupleType: Tuple2Str,
    types.BooleanType: Bool2Str,
    types.StringType: SwallowArgs(str),
    types.UnicodeType: Unicode2Str,
    datetime.date: Date2Str,
    datetime.datetime: Datetime2Str,
    datetime.time: Time2Str,
    Blob: SwallowArgs(str),


    jdbc_type.BIT: int,
    jdbc_type.SMALLINT: int,
    jdbc_type.INTEGER: int,
    jdbc_type.BIGINT: int,
    jdbc_type.TINYINT: int,
    jdbc_type.REAL: float,
    jdbc_type.DOUBLE: float,
    jdbc_type.NUMERIC: float,
    jdbc_type.DECIMAL: float,
    jdbc_type.FLOAT: float,
    jdbc_type.CHAR: Str2Unicode,
    jdbc_type.VARCHAR: Str2Unicode,
    jdbc_type.LONGVARCHAR: Str2Unicode,
    jdbc_type.DATE: Str2Date,
    jdbc_type.TIME: Str2Time,
    jdbc_type.TIMESTAMP: Str2Datetime,
    jdbc_type.BINARY: Blob,
    jdbc_type.VARBINARY: Blob,
    jdbc_type.LONGVARBINARY: Blob,
    jdbc_type.BLOB: Blob,
    jdbc_type.CLOB: Str2Unicode,
    jdbc_type.NCLOB: Str2Unicode,
    jdbc_type.NCHAR: Str2Unicode,
    jdbc_type.NVARCHAR: Str2Unicode,
    jdbc_type.LONGNVARCHAR: Str2Unicode,

    jdbc_type.ARRAY: Str2Unicode,
    jdbc_type.NULL: Str2Unicode,
    jdbc_type.OTHER: Str2Unicode,
    jdbc_type.JAVA_OBJECT: Str2Unicode,
    jdbc_type.DISTINCT: Str2Unicode,
    jdbc_type.STRUCT: Str2Unicode,
    jdbc_type.REF: Str2Unicode,
    jdbc_type.DATALINK: Str2Unicode,
    jdbc_type.BOOLEAN: Str2Unicode,
    jdbc_type.ROWID: Str2Unicode,
    jdbc_type.SQLXML: Str2Unicode,
    }
