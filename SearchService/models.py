""" This module stores data models for Search API. """

import attr

@attr.s
class Field(object):
  """ Class representing basic field object. """
  name = attr.ib()
  language = attr.ib()
  type = attr.ib()
  value = attr.ib()

  # According to numbers in document_pb.FieldValue class
  _FIELD_NUMBERS = {
    "TEXT": 0, "HTML": 1, "ATOM": 2, "DATE": 3, "NUMBER": 4, "GEO": 5
  }

  def get_type_number(self):
    """ Returns field type number.

      Returns:
        An int, number of field type according to document_pb.FieldValue class.
    """
    return self._FIELD_NUMBERS[self.type]


@attr.s
class Document(object):
  """ Class representing basic document object. """
  id = attr.ib(default=None)
  language = attr.ib(default="en")
  fields = attr.ib(factory=list)
