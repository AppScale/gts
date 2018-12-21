""" This module stores data models for Search API. """

import datetime
import re

from search_exceptions import (
  InvalidFieldException, InvalidNameException, UnknownFieldTypeException
)

from google.appengine.datastore.document_pb import Field

class Field(object):
  """ Class repressenting basic field object. """

  FIELD_NAME_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]{1,499}$')

  MAX_VALUE_LEN = 1048576
  MAX_ATOM_LENGTH = 500

  def __init__(self, init_field=None):
    """ Constructor for Field type.

    Args:
        init_field: Protocol Buffer Field object or dict with SOLR data
    """
    if init_field != None:
      if isinstance(init_field, Field):
        self.from_pb()

  def from_pb(self, pb_field):
    """ Converter from Protocol Buffer field.

    Args:
      pb_field: An object of Protocol Buffer Field class.
    Raises:
      InvalidFieldException: If passed field has no value.
      InvalidNameException: If passed fields' name is not valid.
    """

    if not pb_field.has_value():
      raise InvalidFieldException("Invalid field: field without a value.")

    if not self.FIELD_NAME_RE.match(pb_field.name()):
      raise InvalidNameException("Invalid field name. "
                                 "Must begin with a letter, contain only "
                                 "letters, digits, and underscores, "
                                 "and be no longer than 500 characters.")
    self.name = pb_field.name()
    pb_value = pb_field.value()

    if pb_field.value().has_language():
      self.language = pb_value.language()
    # TODO: handle the case when passed field has no language

    self.set_pb_value(pb_value)

  def set_pb_value(self, pb_value):
    """ Sets value for Field object.

    Args:
      pb_value: An object of Protocol Buffer FieldValue class.
    Raises:
      ValueError: If value is invalid.
      TypeError: If value type does not match expected.
      UnknownFieldTypeException: If default field is not found.
    """

    # Integer from 0 to 5
    field_type = pb_value.type()

    if field_type == 0:
      if len(pb_value.string_value()) > self.MAX_VALUE_LEN:
        raise ValueError("Value exceeds maximum allowable length: "
                         "{} characters." % (self.MAX_VALUE_LEN))
      self.value = pb_value.string_value()
      self.type = "TEXT"
    elif field_type == 1:
      if len(pb_value.string_value()) > self.MAX_VALUE_LEN:
        raise ValueError("Value exceeds maximum allowable length: "
                         "{} characters." % (self.MAX_VALUE_LEN))
      self.value = pb_value.string_value()
      self.type = "HTML"
    elif field_type == 2:
      if len(pb_value.string_value()) > self.MAX_ATOM_LENGTH:
        raise ValueError("Value exceeds maximum allowable length: "
                         "{} characters." % (self.MAX_ATOM_LENGTH))
      self.value = pb_value.string_value()
      self.type = "ATOM"
    elif field_type == 3:
      if len(pb_value.string_value()) > self.MAX_VALUE_LEN:
        raise ValueError("Value exceeds maximum allowable length: "
                         "{} characters." % (self.MAX_VALUE_LEN))
      try:
        self.value = float(pb_value.string_value())
        self.type = "NUMBER"
      except TypeError:
        raise TypeError("Value supplied is not numeric.")
    elif field_type == 4:
      # TODO: implement it
      pass
    elif field_type == 5:
      if not pb_value.has_geo():
        raise ValueError("No geo data.")
      geo = pb_value.geo()
      if not geo.has_lat():
        raise ValueError("No latitude.")
      if not geo.has_lng():
        raise ValueError("No longitude.")
      lat = geo.lat()
      lng = geo.lng()
      if lat < -90 or lat > 90:
        raise ValueError("Invalid latitude.")
      if lng < -180 or lng > 180:
        raise ValueError("Invalid longitude.")
      self.value = (lat, lng)
      self.type = "GEO"
    else:
      raise UnknownFieldTypeException("Unknown field type: {}".
                                      format(field_type))