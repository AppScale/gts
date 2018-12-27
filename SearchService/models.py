""" This module stores data models for Search API. """

import calendar
import time

from google.appengine.datastore.document_pb import Field, FieldValue

class Field(object):
  """ Class repressenting basic field object. """

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
    """

    # Number between 0 and 5
    field_type = pb_value.type()
    self.type = field_type
    field_type = FieldValue.ContentType_Name(field_type)

    if field_type in ["TEXT", "HTML", "ATOM"]:
      self.value = pb_value.string_value()
    elif field_type == "NUMBER":
      self.value = float(pb_value.string_value())
    elif field_type == "DATE":
      self.value = time.gmtime(int(pb_value.string_value()) // 1000)
    elif field_type == "GEO":
      geo = pb_value.geo()
      lat = float(geo.lat())
      lng = float(geo.lng())
      self.value = (lat, lng)

  def to_pb(self):
    """ Converter to Protocol Buffer field.

    Returns:
      pb_field: An object of Protocol Buffer Field class.
    """

    pb_field = Field()

    pb_field.set_name(self.name)

    pb_value = FieldValue()
    pb_value.set_language(self.language)
    pb_value.set_type(self.type)

    field_type = FieldValue.ContentType_Name(self.type)

    if field_type in ["TEXT", "HTML", "ATOM"]:
      pb_value.set_string_value(self.value)
    elif field_type == "NUMBER":
      pb_value.set_string_value(str(self.value))
    elif field_type == "DATE":
      value = calendar.timegm(self.value)
      pb_value.set_string_value(str(int(value * 1000)))
    elif field_type == "GEO":
      geo = pb_value.mutable_geo()
      lat, lng = self.value
      geo.set_lat(lat)
      geo.set_lng(lng)

    pb_field.set_pb_value(pb_value)

    return pb_field