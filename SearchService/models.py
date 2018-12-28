""" This module stores data models for Search API. """

import attr

@attr.s
class Field(object):
  """ Class representing basic field object. """
  name = attr.ib()
  language = attr.ib()
  type = attr.ib()
  value = attr.ib()


@attr.s
class Document(object):
  """ Class representing basic document object. """
  id = attr.ib(default=None)
  language = attr.ib(default="en")
  fields = attr.ib(factory=list)
