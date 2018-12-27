""" This module stores data models for Search API. """

import calendar
import time

from google.appengine.datastore import document_pb

class Field(object):
  """ Class representing basic field object. """

  def __init__(self):
    """ Constructor for Field type.
    """
    pass

  def from_pb(self, pb_field, doc_lang):
    """ Converter from Protocol Buffer field.

    Args:
      pb_field: An object of Protocol Buffer Field class.
      doc_lang: Documents' language.
    """

    self.name = pb_field.name()
    pb_value = pb_field.value()

    if pb_field.value().has_language():
      self.language = pb_value.language()
    else:
      self.language = doc_lang

    self._set_pb_value(pb_value)

  def _set_pb_value(self, pb_value):
    """ Sets value for Field object.

    Args:
      pb_value: An object of Protocol Buffer FieldValue class.
    """

    # Number between 0 and 5
    field_type = pb_value.type()
    self.type = field_type
    field_type = document_pb.FieldValue.ContentType_Name(field_type)

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

    pb_field = document_pb.Field()

    pb_field.set_name(self.name)

    pb_value = pb_field.mutable_value()
    pb_value.set_language(self.language)
    pb_value.set_type(self.type)

    field_type = document_pb.FieldValue.ContentType_Name(self.type)

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

    return pb_field


class Document(object):
  """ Class representing basic document object. """

  def __init__(self):
    """ Constructor for Document type.
    """
    pass

  def from_pb(self, pb_doc):
    """ Converter from Protocol Buffer document.

    Args:
      pb_doc: An object of Protocol Buffer Document class.
    """

    self.id = pb_doc.id()
    self.language = pb_doc.language()
    self.fields = []

    for field in pb_doc.field_list():
      self.fields.append(Field().from_pb(field, self.language))

  def to_pb(self):
    """ Converter to Protocol Buffer document.

    Returns:class Doc
      pb_doc: An object of Protocol Buffer Field class.
    """

    pb_doc = document_pb.Document()

    pb_doc.set_id(self.id)
    pb_doc.set_language(self.language)

    for field in self.fields:
      f = pb_doc.add_field()
      f = field.to_pb()

    return pb_doc
