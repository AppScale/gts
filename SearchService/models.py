""" This module stores data models for Search API. """

import re
import time

from google.appengine.datastore.document_pb import Field, FieldValue

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
    """

    pb_value = pb_field.value()

    if pb_field.value().has_language():
      self.language = pb_value.language()
    # TODO: handle the case when passed field has no language

    self.set_pb_value(pb_value)

  def set_pb_value(self, pb_value):
    """ Sets value for Field object.

    Args:
      pb_value: An object of Protocol Buffer FieldValue class.
    """

    field_type = FieldValue.ContentType_Name(pb_value.type())
    self.type = field_type

    if field_type in ["TEXT", "HTML", "ATOM"]:
      self.value = pb_value.string_value()
    elif field_type == "NUMBER":
      self.value = float(pb_value.string_value())
    elif field_type == "DATE":
      self.value = time.gmtime(int(pb_value.string_value()) // 1000)
    elif field_type == "GEO":
      geo = pb_value.geo()
      lat = geo.lat()
      lng = geo.lng()
      self.value = (lat, lng)