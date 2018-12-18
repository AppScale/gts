"""" This module stores data models for Search API. """

class Field(object):
  """" Class repressenting basic field object. """

  def __init__(self):
    """" Constructor for Field type. """
    pass

  def from_pb(self, pb_document):
    """" Converter from Protocol Buffer field.

    Args:
      pb_document: An object of Protocol Buffer Field class
    """
    pass