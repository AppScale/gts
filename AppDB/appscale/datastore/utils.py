import datetime
import itertools
import logging
import mmh3
import struct
import sys
import time

from appscale.common.constants import LOG_FORMAT
from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from tornado import ioloop

from appscale.datastore import dbconstants, helper_functions
from appscale.datastore.appscale_datastore_batch import DatastoreFactory
from appscale.datastore.dbconstants import (
  AppScaleDBConnectionError, BadRequest, ID_KEY_LENGTH, ID_SEPARATOR,
  KEY_DELIMITER, KIND_SEPARATOR, METADATA_TABLE, TERMINATING_STRING
)

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore import appscale_stub_util
from google.appengine.datastore import datastore_index
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import entity_pb
from google.appengine.datastore import sortable_pb_encoder


logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
logger = logging.getLogger(__name__)


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
    if self.__binary_results or self.__last_ent:
      self._EncodeCompiledCursor(result.mutable_compiled_cursor())


def fetch_and_delete_entities(database, table, schema, first_key,
                              entities_only=False):
  """ Deletes all data from datastore.

  Args:
    database: The datastore type (e.g. cassandra).
    first_key: A str, the first key to be deleted.
      Either the app ID or "" to delete all db data.
    entities_only: True to delete entities from APP_ENTITY/PROPERTY tables,
      False to delete every trace of the given app ID.
  """
  # The amount of time to wait before retrying to fetch entities.
  backoff_timeout = 30

  # The default number of rows to fetch at a time.
  batch_size = 1000

  last_key = first_key + '\0' + TERMINATING_STRING

  logger.debug("Deleting application data in the range: {0} - {1}".
    format(first_key, last_key))

  db = DatastoreFactory.getDatastore(database)

  # Do not delete metadata, just entities.
  if entities_only and table == METADATA_TABLE:
    return

  # Loop through the datastore tables and delete data.
  logger.info("Deleting data from {0}".format(table))

  start_inclusive = True
  while True:
    try:
      entities = db.range_query_sync(
        table, schema, first_key, last_key, batch_size,
        start_inclusive=start_inclusive)
      if not entities:
        logger.info("No entities found for {}".format(table))
        break

      for ii in entities:
        db.batch_delete_sync(table, ii.keys())
      logger.info("Deleted {0} entities".format(len(entities)))

      first_key = entities[-1].keys()[0]
      start_inclusive = False
    except AppScaleDBConnectionError:
      logger.exception('Error while deleting data')
      time.sleep(backoff_timeout)


def encode_index_pb(pb):
  """ Returns an encoded protocol buffer.

  Args:
      pb: The protocol buffer to encode.
  Returns:
      An encoded protocol buffer.
  """

  def _encode_path(pb):
    """ Takes a protocol buffer and returns the encoded path. """
    path = []
    for e in pb.element_list():
      if e.has_name():
        key_id = e.name()
      elif e.has_id():
        key_id = str(e.id()).zfill(ID_KEY_LENGTH)
      else:
        raise BadRequest('Entity path must contain name or ID')

      if ID_SEPARATOR in e.type():
        raise BadRequest('Kind names must not include ":"')

      path.append(ID_SEPARATOR.join([e.type(), key_id]))
    val = dbconstants.KIND_SEPARATOR.join(path)
    val += dbconstants.KIND_SEPARATOR
    return val

  if isinstance(pb, entity_pb.PropertyValue) and pb.has_uservalue():
    userval = entity_pb.PropertyValue()
    userval.mutable_uservalue().set_email(pb.uservalue().email())
    userval.mutable_uservalue().set_auth_domain("")
    userval.mutable_uservalue().set_gaiaid(0)
    pb = userval

  def remove_nulls(value):
    """ Remove null values from a given string and byte stuff encode. """
    return buffer(
      str(value).replace('\x01', '\x01\x02').replace('\x00', '\x01\x01'))

  encoder = sortable_pb_encoder.Encoder()
  pb.Output(encoder)

  if isinstance(pb, entity_pb.PropertyValue):
    value = encoder.buffer().tostring()
    # We strip off null strings because it is our delimiter.
    value = remove_nulls(value)
    return buffer(value)
  elif isinstance(pb, entity_pb.Path):
    return buffer(_encode_path(pb))


def get_entity_kind(key_path):
  """ Returns the Kind of the Entity. A Kind is like a type or a
      particular class of entity.

  Args:
      key_path: A str, the key path of entity.
  Returns:
      A str, the kind of the entity.
  """
  if isinstance(key_path, entity_pb.EntityProto):
    key_path = key_path.key()
  return key_path.path().element_list()[-1].type()


def get_index_key_from_params(params):
  """Returns the index key from params.

  Args:
     params: a list of strings to be concatenated to form the key made of:
            prefix, kind, property name, and path
  Returns:
     a string
  Raises:
     ValueError: if params are not of the correct cardinality
  """
  if len(params) != 5 and len(params) != 4:
    raise ValueError("Bad number of params")

  if params[-1] is None:
    # strip off the last None item
    key = dbconstants.KEY_DELIMITER.join(params[:-1]) + \
      dbconstants.KEY_DELIMITER
  else:
    key = dbconstants.KEY_DELIMITER.join(params)
  return key


def get_scatter_prop(element_list):
  """ Gets the scatter property for an entity's key path.

  This will return a property for only a small percentage of entities.

  Args:
    element_list: A list of entity_pb.Path_Element objects.
  Returns:
    An entity_pb.Property object or None.
  """
  def id_from_element(element):
    if element.has_name():
      return element.name()
    elif element.has_id():
      return str(element.id())
    else:
      return ''

  to_hash = ''.join([id_from_element(element) for element in element_list])
  full_hash = mmh3.hash(to_hash)
  hash_bytes = struct.pack('i', full_hash)[0:2]
  hash_int = struct.unpack('H', hash_bytes)[0]
  if hash_int >= dbconstants.SCATTER_PROPORTION:
    return None

  scatter_property = entity_pb.Property()
  scatter_property.set_name('__scatter__')
  scatter_property.set_meaning(entity_pb.Property.BYTESTRING)
  scatter_property.set_multiple(False)
  property_value = scatter_property.mutable_value()
  property_value.set_stringvalue(hash_bytes)

  return scatter_property


def get_index_kv_from_tuple(tuple_list, reverse=False):
  """ Returns keys/value of indexes for a set of entities.

  Args:
     tuple_list: A list of tuples of prefix and pb entities
     reverse: if these keys are for the descending table
  Returns:
     A list of keys and values of indexes
  """
  all_rows = []
  for prefix, entity in tuple_list:
    # Give some entities a property that makes it easy to sample keys.
    scatter_prop = get_scatter_prop(entity.key().path().element_list())
    if scatter_prop is not None:
      # Prevent the original entity from being modified.
      prop_list = [prop for prop in entity.property_list()] + [scatter_prop]
    else:
      prop_list = entity.property_list()

    for prop in prop_list:
      val = str(encode_index_pb(prop.value()))

      if reverse:
        val = helper_functions.reverse_lex(val)

      params = [prefix,
                get_entity_kind(entity),
                prop.name(),
                val,
                str(encode_index_pb(entity.key().path()))]

      index_key = get_index_key_from_params(params)
      p_vals = [index_key,
                buffer(prefix + dbconstants.KEY_DELIMITER) + \
                encode_index_pb(entity.key().path())]
      all_rows.append(p_vals)
  return tuple(all_rows)


def get_ancestor_paths_from_ent_key(ent_key):
  """ Get a list of key string for the ancestor portion of a composite key.
  All subpaths are required.

  Args:
    ent_key: A string of the entire path of an entity.
  Returns:
    A list of strs of the path of the ancestor.
  """
  ancestor_list = []
  tokens = str(ent_key).split(dbconstants.KIND_SEPARATOR)
  # Strip off the empty placeholder and also do not include the last kind.
  tokens = tokens[:-2]
  for num_elements in range(0, len(tokens)):
    ancestor = ""
    for token in tokens[0:num_elements + 1]:
      ancestor += token + dbconstants.KIND_SEPARATOR
    ancestor_list.append(ancestor)
  return ancestor_list


def get_composite_index_keys(index, entity):
  """ Creates keys to the composite index table for a given entity.

  Keys are built as such:
    app_id/ns/composite_id/ancestor/valuevaluevalue..../entity_key
  Components explained:
  ns: The namespace of the entity.
  composite_id: The composite ID assigned to this index upon creation.
  ancestor: The root ancestor path (only if the query this index is for
    has an ancestor)
  value(s): The string representation of mulitiple properties.
  entity_key: The entity key (full path) used as a means of having a unique
    identifier. This prevents two entities with the same values from
    colliding.

  Args:
    index: A datastore_pb.CompositeIndex.
    entity: A entity_pb.EntityProto.
  Returns:
    A list of strings representing keys to the composite table.
  """
  composite_id = index.id()
  definition = index.definition()
  app_id = clean_app_id(entity.key().app())
  name_space = entity.key().name_space()
  ent_key = encode_index_pb(entity.key().path())
  pre_comp_index_key = "{0}{1}{2}{4}{3}{4}".format(app_id,
                                                   dbconstants.KEY_DELIMITER,
                                                   name_space, composite_id,
                                                   dbconstants.KEY_DELIMITER)
  if definition.ancestor() == 1:
    ancestor_list = get_ancestor_paths_from_ent_key(ent_key)

  property_list_names = [prop.name() for prop in entity.property_list()]
  multivalue_dict = {}
  for prop in entity.property_list():
    if prop.name() not in property_list_names:
      continue
    value = str(encode_index_pb(prop.value()))

    if prop.name() in multivalue_dict:
      multivalue_dict[prop.name()].append(value)
    else:
      multivalue_dict[prop.name()] = [value]
  # Build lists for which we'll get all combinations of indexes.
  lists_of_prop_list = []
  for prop in definition.property_list():
    # Check to make sure the entity has the required items. If not then we
    # do not create an index for the composite index.
    # The definition can also have a key as a part of the index, but this
    # is not repeated.
    if prop.name() == "__key__":
      value = str(encode_index_pb(entity.key().path()))
      if prop.direction() == entity_pb.Index_Property.DESCENDING:
        value = helper_functions.reverse_lex(value)
      lists_of_prop_list.append([value])
    elif prop.name() not in multivalue_dict:
      return []
    else:
      my_list = multivalue_dict[prop.name()]
      if prop.direction() == entity_pb.Index_Property.DESCENDING:
        for index, item in enumerate(my_list):
          my_list[index] = helper_functions.reverse_lex(item)
      lists_of_prop_list.append(my_list)

  # Get all combinations of the composite indexes.
  all_combinations = []
  if len(lists_of_prop_list) == 1:
    for item in lists_of_prop_list[0]:
      all_combinations.append([item])
  elif len(lists_of_prop_list) > 1:
    all_combinations = list(itertools.product(*lists_of_prop_list))

  # We should throw an exception if the number of combinations is
  # more than 20000. We currently do not.
  # https://developers.google.com/appengine/docs/python/datastore/
  # #Python_Quotas_and_limits

  all_keys = []
  for combo in all_combinations:
    index_value = ""
    for prop_value in combo:
      index_value += str(prop_value) + dbconstants.KEY_DELIMITER

    # We append the ent key to have unique keys if entities happen
    # to share the same index values (and ancestor).
    if definition.ancestor() == 1:
      for ancestor in ancestor_list:
        pre_comp_key = pre_comp_index_key + "{0}{1}".format(
          ancestor, dbconstants.KEY_DELIMITER)
        composite_key = "{0}{1}{2}".format(pre_comp_key, index_value,
                                           ent_key)
        all_keys.append(composite_key)
    else:
      composite_key = "{0}{1}{2}".format(pre_comp_index_key, index_value,
                                         ent_key)
      all_keys.append(composite_key)

  return all_keys


def get_composite_indexes_rows(entities, composite_indexes):
  """ Get the composite indexes keys in the DB for the given entities.

  Args:
     entities: A list of EntityProto for which their indexes are to be
       deleted.
     compsite_indexes: A list of datastore_pb.CompositeIndex.
  Returns:
    A list of keys.
  """
  if len(entities) == 0:
    return []

  row_keys = []
  for ent in entities:
    for index_def in composite_indexes:
      kind = get_entity_kind(ent.key())
      if index_def.definition().entity_type() != kind:
        continue
      # Make sure the entity contains the required entities for the composite
      # definition.
      prop_name_def_list = [index_prop.name() for index_prop in \
                            index_def.definition().property_list()]
      all_prop_names_in_ent = [prop.name() for prop in \
                               ent.property_list()]

      has_values = True
      for index_prop_name in prop_name_def_list:
        if index_prop_name not in all_prop_names_in_ent:
          has_values = False
        # Special property name which does not show up in the list but
        # is a part of the key of the entity.
        if index_prop_name == "__key__":
          has_values = True
      if not has_values:
        continue

      composite_index_keys = get_composite_index_keys(index_def, ent)
      row_keys.extend(composite_index_keys)

  return row_keys


def get_entity_key(prefix, pb):
  """ Returns the key for the entity table.

  Args:
      prefix: A str, the app name and namespace string
        example-- 'guestbook/mynamespace'.
      pb: Protocol buffer that we will encode the index name.
  Returns:
      A str, the key for entity table.
  """
  return dbconstants.KEY_DELIMITER.join([prefix, str(encode_index_pb(pb))])


def get_kind_key(prefix, key_path):
  """ Returns a key for the kind table.

  Args:
    prefix: A str, the app name and namespace.
    key_path: A str, the key path to build row key with.
  Returns:
    A str, the row key for kind table.
  """
  path = []
  path.append(key_path.element_list()[-1].type())
  for e in key_path.element_list():
    if e.has_name():
      key_id = e.name()
    else:
      # make sure ids are ordered lexigraphically by making sure they
      # are of set size i.e. 2 > 0003 but 0002 < 0003
      key_id = str(e.id()).zfill(ID_KEY_LENGTH)
    path.append("{0}{2}{1}".format(e.type(), key_id,
                                   dbconstants.ID_SEPARATOR))
  encoded_path = dbconstants.KIND_SEPARATOR.join(path)
  encoded_path += dbconstants.KIND_SEPARATOR

  return prefix + dbconstants.KEY_DELIMITER + encoded_path


def group_for_key(key):
  """ Extract the root path for a given key.

  Args:
    key: An encoded or decoded Reference object.
  Returns:
    A Reference object containing the root key.
  """
  if not isinstance(key, entity_pb.Reference):
    key = entity_pb.Reference(key)

  first_element = key.path().element(0)

  # Avoid modifying the original object.
  key_copy = entity_pb.Reference()
  key_copy.CopyFrom(key)

  # Groups without a namespace should match groups with an empty namespace.
  if not key_copy.name_space():
    key_copy.set_name_space('')

  key_copy.path().clear_element()
  element = key_copy.path().add_element()
  element.MergeFrom(first_element)
  return key_copy


def tx_partition(app, txid):
  """ Return a blob hash for a given application and transaction ID.

  Args:
    app: A string specifying the application ID.
    txid: An integer specifying the transaction ID.
  Returns:
    A bytearray that can be used as the transaction partition key.
  """
  murmur_int = mmh3.hash64(app + str(txid))[0]
  # Distribute the integer range evenly across the byte ordered token range.
  return bytearray(struct.pack('<q', murmur_int))


def encode_entity_table_key(key):
  """ Create a key that can be used for the entities table.

  Args:
    key: An encoded or decoded Reference object.
  Returns:
    A string containing an entities table key.
  """
  if not isinstance(key, entity_pb.Reference):
    key = entity_pb.Reference(key)

  prefix = dbconstants.KEY_DELIMITER.join([key.app(), key.name_space()])
  return get_entity_key(prefix, key.path())


def create_key(app, namespace, path):
  """ Create Reference object from app, namespace, and path.

  Args:
    app: A string specifying an application ID.
    namespace: A string specifying the namespace.
    path: An encoded Path object.
  Returns:
    A Reference object.
  """
  key = entity_pb.Reference()
  key.set_app(app)
  key.set_name_space(namespace)
  key_path = key.mutable_path()
  key_path.MergeFromString(path)
  return key


def get_write_time(txid):
  """ Get the timestamp the datastore should use to write entity data.

  Args:
    txid: An integer specifying a transaction ID.
  Returns:
    An integer specifying a timestamp to use (in microseconds from unix epoch).
  """
  # Try to prevent future writes from getting buried under past writes.
  epoch = datetime.datetime.utcfromtimestamp(0)
  offset = datetime.datetime(2022, 2, 1) - epoch
  usec_offset = offset.total_seconds() * 1000000
  return int(usec_offset + txid)


def encode_path_from_filter(query_filter):
  """ Encode a reference path from a query filter.

  Args:
    query_filter: A datastore_pb.Query_Filter.
  Returns:
    A string containing an encoded reference path.
  """
  path = entity_pb.Path()
  ref_value = query_filter.property(0).value().referencevalue()
  for element in ref_value.pathelement_list():
    path.add_element().MergeFrom(element)

  return str(encode_index_pb(path))


def tornado_synchronous(coroutine):
  def synchronous_coroutine(*args, **kwargs):
    async = lambda: coroutine(*args, **kwargs)
    # Like synchronous HTTPClient, create separate IOLoop for sync code
    io_loop = ioloop.IOLoop(make_current=False)
    try:
      return io_loop.run_sync(async)
    finally:
      io_loop.close()
  return synchronous_coroutine


def decode_path(encoded_path):
  """ Parse a Cassandra-encoded reference path.

  Args:
    encoded_path: A string specifying the encoded path.
  Returns:
    An entity_pb.Path object.
  """
  path = entity_pb.Path()

  for element in encoded_path.split(dbconstants.KIND_SEPARATOR):
    # For some reason, encoded keys have a trailing separator, so ignore the
    # last empty element.
    if not element:
      continue

    kind, identifier = element.split(dbconstants.ID_SEPARATOR, 1)

    new_element = path.add_element()
    new_element.set_type(kind)

    # Encoded paths do not differentiate between IDs and names, so we can only
    # guess which one it is. IDs often exceed the ID_KEY_LENGTH.
    if len(identifier) >= ID_KEY_LENGTH and identifier.isdigit():
      new_element.set_id(int(identifier))
    else:
      new_element.set_name(identifier)

  return path


def kind_from_encoded_key(encoded_key):
  """ Extract kind from an encoded reference string.

  Args:
    encoded_key: A string specifying an encoded entity key.
  Returns:
    A string specifying an entity kind.
  """
  path_section = encoded_key.rsplit(KEY_DELIMITER, 1)[-1]
  last_element = path_section.split(KIND_SEPARATOR)[-2]
  return last_element.split(ID_SEPARATOR, 1)[0]


def __IndexListForQuery(query):
  """Get the composite index definition used by the query, if any, as a list.

  Args:
    query: the datastore_pb.Query to compute the index list for

  Returns:
    A singleton list of the composite index definition pb used by the query,
  """
  required, kind, ancestor, props = (
      datastore_index.CompositeIndexForQuery(query))
  if not required:
    return []

  index_pb = entity_pb.Index()
  index_pb.set_entity_type(kind)
  index_pb.set_ancestor(bool(ancestor))
  for name, direction in datastore_index.GetRecommendedIndexProperties(props):
    prop_pb = entity_pb.Index_Property()
    prop_pb.set_name(name)
    prop_pb.set_direction(direction)
    index_pb.property_list().append(prop_pb)
  return [index_pb]


def _FindIndexToUse(query, indexes):
  """ Matches the query with one of the composite indexes.

  Args:
    query: A datastore_pb.Query.
    indexes: A list of entity_pb.CompsiteIndex.
  Returns:
    The composite index of the list for which the composite index matches
    the query. Returns None if there is no match.
  """
  if not query.has_kind():
    return None

  index_list = __IndexListForQuery(query)
  if index_list == []:
    return None

  index_match = index_list[0]
  for index in indexes:
    if index_match.Equals(index.definition()):
      return index

  raise dbconstants.NeedsIndex('Query requires an index')
