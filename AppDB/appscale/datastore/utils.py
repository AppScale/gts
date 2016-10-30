import sys

from .unpackaged import APPSCALE_PYTHON_APPSERVER

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore import appscale_stub_util
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import entity_pb


def clean_app_id(app_id):
  """ Google App Engine uses a special prepended string to signal that it
  is an HRD application. AppScale does not use this string so we remove it.
  
  Args:
    app_id: A str, the application identifier.
  Returns:
    An application identifier without the HRD string.
  """
  if app_id.startswith("s~"):
    return app_id[2:]
  return app_id


def reference_property_to_reference(refprop):
  """ Creates a Reference from a ReferenceProperty. 

  Args:
    refprop: A entity_pb.ReferenceProperty object.
  Returns:
    A entity_pb.Reference object. 
  """
  ref = entity_pb.Reference()
  app_id = clean_app_id(refprop.app())
  ref.set_app(app_id)
  if refprop.has_name_space():
    ref.set_name_space(refprop.name_space())
  for pathelem in refprop.pathelement_list():
    ref.mutable_path().add_element().CopyFrom(pathelem)
  return ref


class UnprocessedQueryResult(datastore_pb.QueryResult):
  """ A QueryResult that avoids decoding and re-encoding results.

  This is only meant as a faster container for returning results from
  datastore queries. Since it does not process or check results in any way,
  it is not safe to use as a general purpose QueryResult replacement.
  """
  def __init__(self, contents=None):
    """ Initializes an UnprocessedQueryResult object.

    Args:
      contents: An optional string to initialize a QueryResult object.
    """
    datastore_pb.QueryResult.__init__(self, contents=contents)
    self.binary_results_ = []

  def result_list(self):
    """ Returns a reference to the stored list of results.

    Unlike the original function, this returns the binary results instead of
    the decoded results.
    """
    return self.binary_results_

  def OutputUnchecked(self, out):
    """ Encodes QueryResult object and outputs it to a buffer object.

    This is called during the Encode process. The only difference from the
    original function is outputting the binary results instead of encoding
    result objects.

    Args:
      out: A buffer object to store the output.
    """
    if (self.has_cursor_):
      out.putVarInt32(10)
      out.putVarInt32(self.cursor_.ByteSize())
      self.cursor_.OutputUnchecked(out)
    for i in xrange(len(self.binary_results_)):
      out.putVarInt32(18)
      out.putVarInt32(len(self.binary_results_[i]))
      out.buf.fromstring(self.binary_results_[i])
    out.putVarInt32(24)
    out.putBoolean(self.more_results_)
    if (self.has_keys_only_):
      out.putVarInt32(32)
      out.putBoolean(self.keys_only_)
    if (self.has_compiled_query_):
      out.putVarInt32(42)
      out.putVarInt32(self.compiled_query_.ByteSize())
      self.compiled_query_.OutputUnchecked(out)
    if (self.has_compiled_cursor_):
      out.putVarInt32(50)
      out.putVarInt32(self.compiled_cursor_.ByteSize())
      self.compiled_cursor_.OutputUnchecked(out)
    if (self.has_skipped_results_):
      out.putVarInt32(56)
      out.putVarInt32(self.skipped_results_)
    for i in xrange(len(self.index_)):
      out.putVarInt32(66)
      out.putVarInt32(self.index_[i].ByteSize())
      self.index_[i].OutputUnchecked(out)
    if (self.has_index_only_):
      out.putVarInt32(72)
      out.putBoolean(self.index_only_)
    if (self.has_small_ops_):
      out.putVarInt32(80)
      out.putBoolean(self.small_ops_)


class UnprocessedQueryCursor(appscale_stub_util.QueryCursor):
  """ A QueryCursor that takes encoded entities.

  This is only meant to accompany the UnprocessedQueryResult class.
  """
  def __init__(self, query, binary_results, last_entity):
    """ Initializes an UnprocessedQueryCursor object.

    Args:
      query: A query protocol buffer object.
      binary_results: A list of strings that contain encoded protocol buffer
        results.
      last_entity: A string that contains the last entity. It is used to
        generate the cursor, and it can be defined even if there are no
        results.
    """
    self.__binary_results = binary_results
    self.__query = query
    self.__last_ent = last_entity
    if len(binary_results) > 0:
      # _EncodeCompiledCursor just uses the last entity.
      results = [entity_pb.EntityProto(binary_results[-1])]
    else:
      results = []
    super(UnprocessedQueryCursor, self).__init__(query, results, last_entity)

  def PopulateQueryResult(self, count, offset, result):
    """ Populates a QueryResult object with results the QueryCursor has been
    storing.

    Args:
      count: The number of results requested in the query.
      offset: The number of results to skip.
      result: A QueryResult object to populate.
    """
    result.set_skipped_results(min(count, offset))
    result_list = result.result_list()
    if self.__binary_results:
      if self.__query.keys_only():
        for binary_result in self.__binary_results:
          entity = entity_pb.EntityProto(binary_result)
          entity.clear_property()
          entity.clear_raw_property()
          result_list.append(entity.Encode())
      else:
        result_list.extend(self.__binary_results)
    else:
      result_list = []
    result.set_keys_only(self.__query.keys_only())
    result.set_more_results(offset < count)
    if self.__binary_results or self.__last_ent:
      self._EncodeCompiledCursor(result.mutable_compiled_cursor())
