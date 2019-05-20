import array
import datetime
import itertools
import logging
import md5
import sys
import uuid

from tornado import gen
from tornado.ioloop import IOLoop

from appscale.datastore import dbconstants, helper_functions

from appscale.common.datastore_index import DatastoreIndex, merge_indexes
from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from kazoo.client import KazooState
from appscale.datastore.dbconstants import (
  APP_ENTITY_SCHEMA, BadRequest, ID_KEY_LENGTH, InternalError, MAX_TX_DURATION,
  Timeout
)
from appscale.datastore.cassandra_env.cassandra_interface import (
  batch_size, LARGE_BATCH_THRESHOLD)
from appscale.datastore.cassandra_env.entity_id_allocator import EntityIDAllocator
from appscale.datastore.cassandra_env.entity_id_allocator import ScatteredAllocator
from appscale.datastore.cassandra_env.large_batch import BatchNotApplied
from appscale.datastore.cassandra_env.utils import deletions_for_entity
from appscale.datastore.cassandra_env.utils import mutations_for_entity
from appscale.datastore.index_manager import IndexInaccessible
from appscale.datastore.taskqueue_client import EnqueueError, TaskQueueClient
from appscale.datastore.utils import _FindIndexToUse
from appscale.datastore.utils import clean_app_id
from appscale.datastore.utils import decode_path
from appscale.datastore.utils import encode_entity_table_key
from appscale.datastore.utils import encode_index_pb
from appscale.datastore.utils import encode_path_from_filter
from appscale.datastore.utils import get_composite_index_keys
from appscale.datastore.utils import get_entity_key
from appscale.datastore.utils import get_entity_kind
from appscale.datastore.utils import get_index_key_from_params
from appscale.datastore.utils import get_kind_key
from appscale.datastore.utils import group_for_key
from appscale.datastore.utils import kind_from_encoded_key
from appscale.datastore.utils import reference_property_to_reference
from appscale.datastore.utils import UnprocessedQueryCursor
from appscale.datastore.range_iterator import RangeExhausted, RangeIterator
from appscale.datastore.zkappscale import entity_lock
from appscale.datastore.zkappscale import zktransaction

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api import datastore_errors
from google.appengine.api.datastore_distributed import _MAX_ACTIONS_PER_TXN
from google.appengine.datastore import appscale_stub_util
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import datastore_index
from google.appengine.datastore import entity_pb
from google.appengine.datastore import sortable_pb_encoder
from google.appengine.datastore.datastore_stub_util import IdToCounter
from google.appengine.datastore.datastore_stub_util import SEQUENTIAL
from google.appengine.runtime import apiproxy_errors
from google.appengine.ext import db
from google.appengine.ext.db.metadata import Namespace
from google.net.proto.ProtocolBuffer import ProtocolBufferDecodeError

logger = logging.getLogger(__name__)


class DatastoreDistributed():
  """ AppScale persistent layer for the datastore API. It is the
      replacement for the AppServers to persist their data into
      a distributed datastore instead of a flat file.
  """
  # Max number of results for a query
  _MAXIMUM_RESULTS = 10000

  # Maximum amount of filter and orderings allowed within a query
  _MAX_QUERY_COMPONENTS = 63

  # For enabling and disabling range inclusivity
  _ENABLE_INCLUSIVITY = True
  _DISABLE_INCLUSIVITY = False

  # Delimiter between app names and namespace and the rest of an entity key
  _NAMESPACE_SEPARATOR = dbconstants.KEY_DELIMITER

  # Delimiter between parameters in index keys.
  _SEPARATOR = dbconstants.KEY_DELIMITER

  # This is the terminating string for range queries
  _TERM_STRING = dbconstants.TERMINATING_STRING

  # Smallest possible value that is considered non-null and indexable.
  MIN_INDEX_VALUE = '\x01'

  # When assigning the first allocated ID, give this value
  _FIRST_VALID_ALLOCATED_ID = 1

  # The key we use to lock for allocating new IDs
  _ALLOCATE_ROOT_KEY = "__allocate__"

  # Number of times to retry acquiring a lock for non transactions.
  NON_TRANS_LOCK_RETRY_COUNT = 5

  # How long to wait before retrying to grab a lock
  LOCK_RETRY_TIME = .5

  # Maximum number of allowed composite indexes any one application can
  # register.
  _MAX_NUM_INDEXES = dbconstants.MAX_NUMBER_OF_COMPOSITE_INDEXES

  # The position of the prop name when splitting an index entry by the
  # delimiter.
  PROP_NAME_IN_SINGLE_PROP_INDEX = 3

  # The cassandra index column that stores the reference to the entity.
  INDEX_REFERENCE_COLUMN = 'reference'

  # The number of entities to fetch at a time when updating indices.
  BATCH_SIZE = 100

  def __init__(self, datastore_batch, transaction_manager, zookeeper=None,
               log_level=logging.INFO, taskqueue_locations=()):
    """
       Constructor.

     Args:
       datastore_batch: A reference to the batch datastore interface.
       zookeeper: A reference to the zookeeper interface.
    """
    class_name = self.__class__.__name__
    self.logger = logging.getLogger(class_name)
    self.logger.setLevel(log_level)

    assert datastore_batch.valid_data_version_sync()

    self.logger.info('Starting {}'.format(class_name))

    # datastore accessor used by this class to do datastore operations.
    self.datastore_batch = datastore_batch

    # zookeeper instance for accesing ZK functionality.
    self.zookeeper = zookeeper

    # Maintain a scattered allocator for each project.
    self.scattered_allocators = {}

    # Maintain a sequential allocator for each project.
    self.sequential_allocators = {}

    self.taskqueue_client = TaskQueueClient(taskqueue_locations)
    self.transaction_manager = transaction_manager
    self.index_manager = None
    self.zookeeper.handle.add_listener(self._zk_state_listener)

  def get_limit(self, query):
    """ Returns the limit that should be used for the given query.

    Args:
      query: A datastore_pb.Query.
    Returns:
      A tuple containing the number of entities the datastore should retrieve
      and a boolean indicating whether or not the datastore should check for
      results beyond what it returns.
    """
    # The datastore should check for more results beyond what it returns when
    # the current request is not able to satisfy the full query. This can
    # happen during batch queries if "count" is less than the full query's
    # limit. It can also happen when the limit is greater than the maximum
    # results that the datastore returns per request.
    check_more_results = False
    limit = None
    if query.has_limit():
      limit = query.limit()

    if query.has_count() and (limit is None or limit > query.count()):
      check_more_results = True
      limit = query.count()

    if limit is None or limit > self._MAXIMUM_RESULTS:
      check_more_results = True
      limit = self._MAXIMUM_RESULTS

    if query.has_offset():
      limit += query.offset()

    # We can not scan with 0 or less, hence we set it to one.
    if limit <= 0:
      limit = 1

    return limit, check_more_results

  @staticmethod
  def __decode_index_str(value, prop_value):
    """ Takes an encoded string and converts it to a PropertyValue.

    Args:
      value: An encoded str.
      prop_value: PropertyValue to fill in.
    """
    value = str(value).replace('\x01\x01', '\x00').replace('\x01\x02', '\x01')
    decoded_value = sortable_pb_encoder.Decoder(
      array.array('B', str(value)))
    prop_value.Merge(decoded_value)

  @staticmethod
  def validate_app_id(app_id):
    """ Verify that this is the stub for app_id.

    Args:
      app_id: An application ID.
    Raises:
      AppScaleBadArg: If the application id is not set.
    """
    if not app_id:
      raise dbconstants.AppScaleBadArg("Application name must be set")

  @staticmethod
  def validate_key(key):
    """ Validate this key by checking to see if it has a name or id.

    Args:
      key: entity_pb.Reference
    Raises:
      datastore_errors.BadRequestError: if the key is invalid
      TypeError: if key is not of entity_pb.Reference
    """

    if not isinstance(key, entity_pb.Reference):
      raise TypeError("Expected type Reference")

    DatastoreDistributed.validate_app_id(key.app())

    for elem in key.path().element_list():
      if elem.has_id() and elem.has_name():
        raise datastore_errors.BadRequestError(
            'Each key path element should have id or name but not both: {0}' \
            .format(key))

  def get_table_prefix(self, data):
    """ Returns the namespace prefix for a query.

    Args:
      data: An Entity, Key or Query PB, or an (app_id, ns) tuple.
    Returns:
      A valid table prefix.
    """
    if isinstance(data, entity_pb.EntityProto):
      app_id = clean_app_id(data.key().app())
      namespace = data.key().name_space()
    elif isinstance(data, tuple):
      app_id = data[0]
      namespace = data[1]
    else:
      app_id = clean_app_id(data.app())
      namespace = data.name_space()

    return self._SEPARATOR.join([app_id, namespace])

  @staticmethod
  def get_ancestor_key_from_ent_key(ent_key):
    """ Get the key string for the ancestor portion of a composite key.

    Args:
      ent_key: A string of the entire path of an entity.
    Returns:
      A str of the path of the ancestor.
    """
    ancestor = ""
    tokens = str(ent_key).split(dbconstants.KIND_SEPARATOR)
    # Strip off the empty placeholder and also do not include the last kind.
    for token in tokens[:-2]:
      ancestor += token + dbconstants.KIND_SEPARATOR
    return ancestor

  @staticmethod
  def get_composite_index_key(index, entity, position_list=None,
    filters=None):
    """ Creates a key to the composite index table for a given entity
    for a composite cursor.

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
      index: A datstore_pb.CompositeIndex.
      entity: A entity_pb.EntityProto.
      position_list: A list of datastore_pb.CompiledCursor_Position items.
        Contains values for property items from a cursor.
      filters: A list of datastore_pb.Query_Filters, used to attain equality
        values not present in position_list.
    Returns:
      A string representing a key to the composite table.
    """
    composite_id = index.id()
    definition = index.definition()
    app_id = clean_app_id(entity.key().app())
    name_space = entity.key().name_space()
    ent_key = encode_index_pb(entity.key().path())
    pre_comp_index_key = "{0}{1}{2}{4}{3}{4}".format(app_id,
      DatastoreDistributed._NAMESPACE_SEPARATOR, name_space, composite_id,
      DatastoreDistributed._SEPARATOR)
    if definition.ancestor() == 1:
      ancestor = DatastoreDistributed.get_ancestor_key_from_ent_key(ent_key)
      pre_comp_index_key += "{0}{1}".format(ancestor,
        DatastoreDistributed._SEPARATOR)

    value_dict = {}
    for prop in entity.property_list():
      value_dict[prop.name()] = \
        str(encode_index_pb(prop.value()))

    # Position list and filters are used if we're creating a composite
    # key for a cursor.
    if position_list:
      for indexvalue in position_list[0].indexvalue_list():
        value_dict[indexvalue.property()] = \
          str(encode_index_pb(indexvalue.value()))
    if filters:
      for filt in filters:
        if filt.op() == datastore_pb.Query_Filter.EQUAL:
          value_dict[filt.property(0).name()] = \
            str(encode_index_pb(filt.property(0).value()))

    index_value = ""
    for prop in definition.property_list():
      name = prop.name()
      value = ''
      if name in value_dict:
        value = value_dict[name]
      elif name == "__key__":
        value = ent_key
      else:
        logger.warning("Given entity {0} is missing a property value {1}.".\
          format(entity, prop.name()))
      if prop.direction() == entity_pb.Index_Property.DESCENDING:
        value = helper_functions.reverse_lex(value)

      index_value += str(value) + DatastoreDistributed._SEPARATOR

    # We append the ent key to have unique keys if entities happen
    # to share the same index values (and ancestor).
    composite_key = "{0}{1}{2}".format(pre_comp_index_key, index_value,
      ent_key)
    return composite_key

  @gen.coroutine
  def insert_composite_indexes(self, entities, composite_indexes):
    """ Creates composite indexes for a set of entities.

    Args:
      entities: A list entities.
      composite_indexes: A list of datastore_pb.CompositeIndex.
    """
    if not composite_indexes:
      return
    row_keys = []
    row_values = {}
    # Create default composite index for all entities. Here we take each
    # of the properties in one
    for ent in entities:
      for index_def in composite_indexes:
        # Skip any indexes if the kind does not match.
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
          # is apart of the key of the entity.
          if index_prop_name == "__key__":
            has_values = True
        if not has_values:
          continue

        # Get the composite index key.
        composite_index_keys = get_composite_index_keys(index_def, ent)
        row_keys.extend(composite_index_keys)

        # Get the reference value for the composite table.
        entity_key = str(encode_index_pb(ent.key().path()))
        prefix = self.get_table_prefix(ent.key())
        reference = "{0}{1}{2}".format(prefix, self._SEPARATOR,  entity_key)
        for composite_key in composite_index_keys:
          row_values[composite_key] = {'reference': reference}

    yield self.datastore_batch.batch_put_entity(
      dbconstants.COMPOSITE_TABLE, row_keys,
      dbconstants.COMPOSITE_SCHEMA, row_values)

  @gen.coroutine
  def delete_composite_index_metadata(self, app_id, index):
    """ Deletes a index for the given application identifier.

    Args:
      app_id: A string representing the application identifier.
      index: A entity_pb.CompositeIndex object.
    """
    self.logger.info('Deleting composite index:\n{}'.format(index))
    try:
      project_index_manager = self.index_manager.projects[app_id]
    except KeyError:
      raise BadRequest('project_id: {} not found'.format(app_id))

    # TODO: Remove actual index entries.
    project_index_manager.delete_index_definition(index.id())

  @gen.coroutine
  def create_composite_index(self, app_id, index):
    """ Stores a new index for the given application identifier.

    Args:
      app_id: A string representing the application identifier.
      index: A entity_pb.CompositeIndex object.
    Returns:
      A unique number representing the composite index ID.
    """
    new_index = DatastoreIndex.from_pb(index)

    # The ID must be a positive number that fits in a signed 64-bit int.
    new_index.id = uuid.uuid1().int >> 65
    merge_indexes(self.zookeeper.handle, app_id, [new_index])
    raise gen.Return(new_index.id)

  @gen.coroutine
  def update_composite_index(self, app_id, index):
    """ Updates an index for a given app ID.

    Args:
      app_id: A string containing the app ID.
      index: An entity_pb.CompositeIndex object.
    """
    self.logger.info('Updating index: {}'.format(index))
    entries_updated = 0
    entity_type = index.definition().entity_type()

    # TODO: Adjust prefix based on ancestor.
    prefix = '{app}{delimiter}{entity_type}{kind_separator}'.format(
      app=app_id,
      delimiter=self._SEPARATOR * 2,
      entity_type=entity_type,
      kind_separator=dbconstants.KIND_SEPARATOR,
    )
    start_row = prefix
    end_row = prefix + self._TERM_STRING
    start_inclusive = True

    while True:
      # Fetch references from the kind table since entity keys can have a
      # parent prefix.
      references = yield self.datastore_batch.range_query(
        table_name=dbconstants.APP_KIND_TABLE,
        column_names=dbconstants.APP_KIND_SCHEMA,
        start_key=start_row,
        end_key=end_row,
        limit=self.BATCH_SIZE,
        offset=0,
        start_inclusive=start_inclusive,
      )

      pb_entities = yield self.__fetch_entities(references)
      entities = [entity_pb.EntityProto(entity) for entity in pb_entities]

      yield self.insert_composite_indexes(entities, [index])
      entries_updated += len(entities)

      # If we fetched fewer references than we asked for, we're done.
      if len(references) < self.BATCH_SIZE:
        break

      start_row = references[-1].keys()[0]
      start_inclusive = self._DISABLE_INCLUSIVITY

    self.logger.info('Updated {} index entries.'.format(entries_updated))

  @gen.coroutine
  def allocate_size(self, project, size):
    """ Allocates a block of IDs for a project.

    Args:
      project: A string specifying the project ID.
      size: An integer specifying the number of IDs to reserve.
    Returns:
      A tuple of integers specifying the start and end ID.
    """
    if project not in self.sequential_allocators:
      self.sequential_allocators[project] = EntityIDAllocator(
        self.datastore_batch.session, project)

    allocator = self.sequential_allocators[project]
    start_id, end_id = yield allocator.allocate_size(size)
    raise gen.Return((start_id, end_id))

  @gen.coroutine
  def allocate_max(self, project, max_id):
    """ Reserves all IDs up to the one given.

    Args:
      project: A string specifying the project ID.
      max_id: An integer specifying the maximum ID to allocated.
    Returns:
      A tuple of integers specifying the start and end ID.
    """
    if project not in self.sequential_allocators:
      self.sequential_allocators[project] = EntityIDAllocator(
        self.datastore_batch.session, project)

    allocator = self.sequential_allocators[project]
    start_id, end_id = yield allocator.allocate_max(max_id)
    raise gen.Return((start_id, end_id))

  @gen.coroutine
  def reserve_ids(self, project_id, ids):
    """ Ensures the given IDs are not re-allocated.

    Args:
      project_id: A string specifying the project ID.
      ids: An iterable of integers specifying entity IDs.
    """
    if project_id not in self.sequential_allocators:
      self.sequential_allocators[project_id] = EntityIDAllocator(
        self.datastore_batch.session, project_id)

    if project_id not in self.scattered_allocators:
      self.scattered_allocators[project_id] = ScatteredAllocator(
        self.datastore_batch.session, project_id)

    for id_ in ids:
      counter, space = IdToCounter(id_)
      if space == SEQUENTIAL:
        allocator = self.sequential_allocators[project_id]
      else:
        allocator = self.scattered_allocators[project_id]

      yield allocator.set_min_counter(counter)

  @gen.coroutine
  def put_entities(self, app, entities):
    """ Updates indexes of existing entities, inserts new entities and
        indexes for them.

    Args:
      app: A string containing the application ID.
      entities: List of entities.
    """
    self.logger.debug('Inserting {} entities'.format(len(entities)))

    composite_indexes = self.get_indexes(app)

    by_group = {}
    for entity in entities:
      group_key = group_for_key(entity.key()).Encode()
      if group_key not in by_group:
        by_group[group_key] = []
      by_group[group_key].append(entity)

    for encoded_group_key, entity_list in by_group.iteritems():
      group_key = entity_pb.Reference(encoded_group_key)

      txid = self.transaction_manager.create_transaction_id(app, xg=False)
      self.transaction_manager.set_groups(app, txid, [group_key])

      # Allow the lock to stick around if there is an issue applying the batch.
      lock = entity_lock.EntityLock(self.zookeeper.handle, [group_key], txid)
      try:
        yield lock.acquire()
      except entity_lock.LockTimeout:
        raise Timeout('Unable to acquire entity group lock')

      try:
        entity_keys = [
          get_entity_key(self.get_table_prefix(entity), entity.key().path())
          for entity in entity_list]
        try:
          current_values = yield self.datastore_batch.batch_get_entity(
            dbconstants.APP_ENTITY_TABLE, entity_keys, APP_ENTITY_SCHEMA)
        except dbconstants.AppScaleDBConnectionError:
          lock.release()
          self.transaction_manager.delete_transaction_id(app, txid)
          raise

        batch = []
        entity_changes = []
        for entity in entity_list:
          prefix = self.get_table_prefix(entity)
          entity_key = get_entity_key(prefix, entity.key().path())

          current_value = None
          if current_values[entity_key]:
            current_value = entity_pb.EntityProto(
              current_values[entity_key][APP_ENTITY_SCHEMA[0]])

          batch.extend(mutations_for_entity(entity, txid, current_value,
                                            composite_indexes))

          batch.append({'table': 'group_updates',
                        'key': bytearray(encoded_group_key),
                        'last_update': txid})

          entity_changes.append(
            {'key': entity.key(), 'old': current_value, 'new': entity})

        if batch_size(batch) > LARGE_BATCH_THRESHOLD:
          try:
            yield self.datastore_batch.large_batch(app, batch, entity_changes,
                                                   txid)
          except BatchNotApplied as error:
            # If the "applied" switch has not been flipped, the lock can be
            # released. The transaction ID is kept so that the groomer can
            # clean up the batch tables.
            lock.release()
            raise dbconstants.AppScaleDBConnectionError(str(error))
        else:
          try:
            yield self.datastore_batch.normal_batch(batch, txid)
          except dbconstants.AppScaleDBConnectionError:
            # Since normal batches are guaranteed to be atomic, the lock can
            # be released.
            lock.release()
            self.transaction_manager.delete_transaction_id(app, txid)
            raise

        lock.release()

      finally:
        # In case of failure entity group lock should stay acquired
        # as transaction groomer will handle it later.
        # But tornado lock must be released.
        lock.ensure_release_tornado_lock()

      self.transaction_manager.delete_transaction_id(app, txid)

  @gen.coroutine
  def delete_entities(self, group, txid, keys, composite_indexes=()):
    """ Deletes the entities and the indexes associated with them.

    Args:
      group: An entity group Reference object.
      txid: An integer specifying a transaction ID.
      keys: An interable containing entity Reference objects.
      composite_indexes: A list or tuple of CompositeIndex objects.
    """
    entity_keys = []
    for key in keys:
      prefix = self.get_table_prefix(key)
      entity_keys.append(get_entity_key(prefix, key.path()))

    # Must fetch the entities to get the keys of indexes before deleting.
    current_values = yield self.datastore_batch.batch_get_entity(
      dbconstants.APP_ENTITY_TABLE, entity_keys, APP_ENTITY_SCHEMA)

    for key in entity_keys:
      if not current_values[key]:
        continue

      current_value = entity_pb.EntityProto(
        current_values[key][APP_ENTITY_SCHEMA[0]])
      batch = deletions_for_entity(current_value, composite_indexes)

      batch.append({'table': 'group_updates',
                    'key': bytearray(group.Encode()),
                    'last_update': txid})

      yield self.datastore_batch.normal_batch(batch, txid)

  @gen.coroutine
  def dynamic_put(self, app_id, put_request, put_response):
    """ Stores and entity and its indexes in the datastore.

    Args:
      app_id: Application ID.
      put_request: Request with entities to store.
      put_response: The response sent back to the app server.
    Raises:
      ZKTransactionException: If we are unable to acquire/release ZooKeeper locks.
    """
    if app_id not in self.scattered_allocators:
      self.scattered_allocators[app_id] = ScatteredAllocator(
        self.datastore_batch.session, app_id)
    allocator = self.scattered_allocators[app_id]

    entities = put_request.entity_list()

    for entity in entities:
      self.validate_key(entity.key())

      for prop in itertools.chain(entity.property_list(),
                                  entity.raw_property_list()):
        if prop.value().has_uservalue():
          uid = md5.new(prop.value().uservalue().email().lower()).digest()
          uid = '1' + ''.join(['%02d' % ord(x) for x in uid])[:20]
          prop.mutable_value().mutable_uservalue().set_obfuscated_gaiaid(uid)

      last_path = entity.key().path().element_list()[-1]
      if last_path.id() == 0 and not last_path.has_name():
        allocated_id = yield allocator.next()
        last_path.set_id(allocated_id)
        group = entity.mutable_entity_group()
        root = entity.key().path().element(0)
        group.add_element().CopyFrom(root)

    if put_request.has_transaction():
      yield self.datastore_batch.put_entities_tx(
        app_id, put_request.transaction().handle(), entities)
    else:
      yield self.put_entities(app_id, entities)
      self.logger.debug('Updated {} entities'.format(len(entities)))

    put_response.key_list().extend([e.key() for e in entities])

  def get_root_key_from_entity_key(self, entity_key):
    """ Extract the root key from an entity key. We
        remove any excess children from a string to get to
        the root key.

    Args:
      entity_key: A string or Key object representing a row key.
    Returns:
      The root key extracted from the row key.
    Raises:
      TypeError: If the type is not supported.
    """
    if isinstance(entity_key, str):
      tokens = entity_key.split(dbconstants.KIND_SEPARATOR)
      return tokens[0] + dbconstants.KIND_SEPARATOR
    elif isinstance(entity_key, entity_pb.Reference):
      app_id = clean_app_id(entity_key.app())
      path = entity_key.path()
      element_list = path.element_list()
      return self.get_root_key(app_id, entity_key.name_space(), element_list)
    else:
      raise TypeError("Unable to get root key from given type of %s" % \
                      entity_key.__class__)

  def get_root_key(self, app_id, ns, ancestor_list):
    """ Gets the root key string from an ancestor listing.

    Args:
      app_id: The app ID of the listing.
      ns: The namespace of the entity.
      ancestor_list: The ancestry of a given entity.
    Returns:
      A string representing the root key of an entity.
    """
    prefix = self.get_table_prefix((app_id, ns))
    first_ent = ancestor_list[0]
    if first_ent.has_name():
      key_id = first_ent.name()
    elif first_ent.has_id():
      # Make sure ids are ordered lexigraphically by making sure they
      # are of set size i.e. 2 > 0003 but 0002 < 0003.
      key_id = str(first_ent.id()).zfill(ID_KEY_LENGTH)
    return "{0}{1}{2}:{3}{4}".format(prefix, self._NAMESPACE_SEPARATOR,
      first_ent.type(), key_id, dbconstants.KIND_SEPARATOR)

  def is_instance_wrapper(self, obj, expected_type):
    """ A wrapper for isinstance for mocking purposes.

    Return whether an object is an instance of a class or of a subclass thereof.
    With a type as second argument, return whether that is the object's type.

    Args:
      obj: The object to check.
      expected_type: A instance type we are comparing obj's type to.
    Returns:
      True if obj is of type expected_type, False otherwise.
    """
    return isinstance(obj, expected_type)

  def acquire_locks_for_trans(self, entities, txnid):
    """ Acquires locks for entities for one particular entity group.

    Args:
      entities: A list of entities (entity_pb.EntityProto or entity_pb.Reference)
                for which are are getting a lock for.
      txnid: The transaction ID handler.
    Returns:
      A hash mapping root keys to transaction IDs.
    Raises:
      ZKTransactionException: If lock is not obtainable.
      TypeError: If args are of incorrect types.
    """
    # Key tuples are the prefix and the root key for which we're getting locks.
    root_keys = []
    txn_hash = {}
    if not self.is_instance_wrapper(entities, list):
      raise TypeError("Expected a list and got {0}".format(entities.__class__))
    for ent in entities:
      if self.is_instance_wrapper(ent, entity_pb.Reference):
        root_keys.append(self.get_root_key_from_entity_key(ent))
      elif self.is_instance_wrapper(ent, entity_pb.EntityProto):
        root_keys.append(self.get_root_key_from_entity_key(ent.key()))
      else:
        raise TypeError("Excepted either a reference or an EntityProto"
           "got {0}".format(ent.__class__))

    if entities == []:
      return {}

    if self.is_instance_wrapper(entities[0], entity_pb.Reference):
      app_id = entities[0].app()
    else:
      app_id = entities[0].key().app()
    app_id = clean_app_id(app_id)
    # Remove all duplicate root keys.
    root_keys = list(set(root_keys))
    try:
      for root_key in root_keys:
        txn_hash[root_key] = txnid
        self.zookeeper.acquire_lock(app_id, txnid, root_key)
    except zktransaction.ZKTransactionException as zkte:
      self.logger.warning('Concurrent transaction: {}'.format(txnid))
      for root_key in txn_hash:
        self.zookeeper.notify_failed_transaction(app_id, txn_hash[root_key])
      raise zkte

    return txn_hash

  def release_locks_for_nontrans(self, app_id, entities, txn_hash):
    """  Releases locks for non-transactional puts.

    Args:
      entities: List of entities for which we are releasing locks. Can
                be either entity_pb.EntityProto or entity_pb.Reference.
      txn_hash: A hash mapping root keys to transaction IDs.
    Raises:
      ZKTransactionException: If we are unable to release locks.
    """
    root_keys = []
    for ent in entities:
      if isinstance(ent, entity_pb.EntityProto):
        ent = ent.key()
      root_keys.append(self.get_root_key_from_entity_key(ent))

    # Remove all duplicate root keys
    root_keys = list(set(root_keys))
    for root_key in root_keys:
      txnid = txn_hash[root_key]
      self.zookeeper.release_lock(app_id, txnid)

  @gen.coroutine
  def fetch_keys(self, key_list):
    """ Given a list of keys fetch the entities.

    Args:
      key_list: A list of keys to fetch.
    Returns:
      A tuple of entities from the datastore and key list.
    """
    row_keys = []
    for key in key_list:
      self.validate_app_id(key.app())
      index_key = str(encode_index_pb(key.path()))
      prefix = self.get_table_prefix(key)
      row_keys.append(self._SEPARATOR.join([prefix, index_key]))
    result = yield self.datastore_batch.batch_get_entity(
      dbconstants.APP_ENTITY_TABLE, row_keys, APP_ENTITY_SCHEMA)
    raise gen.Return((result, row_keys))

  @gen.coroutine
  def dynamic_get(self, app_id, get_request, get_response):
    """ Fetch keys from the datastore.

    Args:
       app_id: The application ID.
       get_request: Request with list of keys.
       get_response: Response to application server.
    Raises:
      ZKTransactionException: If a lock was unable to get acquired.
    """
    keys = get_request.key_list()
    if len(keys) < 5:
      self.logger.debug('Get:\n{}'.format(get_request))
    else:
      self.logger.debug('Get: {} keys'.format(len(keys)))

    if get_request.has_transaction():
      results, row_keys = yield self.fetch_keys(keys)
      fetched_groups = {group_for_key(key).Encode() for key in keys}
      yield self.datastore_batch.record_reads(
        app_id, get_request.transaction().handle(), fetched_groups)
    else:
      results, row_keys = yield self.fetch_keys(keys)

    result_count = 0
    for r in row_keys:
      group = get_response.add_entity()
      if r in results and APP_ENTITY_SCHEMA[0] in results[r]:
        result_count += 1
        group.mutable_entity().CopyFrom(
          entity_pb.EntityProto(results[r][APP_ENTITY_SCHEMA[0]]))
    self.logger.debug('Returning {} results'.format(result_count))

  @gen.coroutine
  def dynamic_delete(self, app_id, delete_request):
    """ Deletes a set of rows.

    Args:
      app_id: The application ID.
      delete_request: Request with a list of keys.
    """
    keys = delete_request.key_list()
    if not keys:
      return

    ent_kinds = []
    for key in delete_request.key_list():
      last_path = key.path().element_list()[-1]
      if last_path.type() not in ent_kinds:
        ent_kinds.append(last_path.type())

    filtered_indexes = [index for index in self.get_indexes(app_id)
                        if index.definition().entity_type() in ent_kinds]

    if delete_request.has_transaction():
      txid = delete_request.transaction().handle()
      yield self.datastore_batch.delete_entities_tx(app_id, txid, keys)
    else:
      by_group = {}
      for key in keys:
        group_key = group_for_key(key).Encode()
        if group_key not in by_group:
          by_group[group_key] = []
        by_group[group_key].append(key)

      for encoded_group_key, key_list in by_group.iteritems():
        group_key = entity_pb.Reference(encoded_group_key)

        txid = self.transaction_manager.create_transaction_id(app_id, xg=False)
        self.transaction_manager.set_groups(app_id, txid, [group_key])

        # Allow the lock to stick around if there is an issue applying the batch.
        lock = entity_lock.EntityLock(self.zookeeper.handle, [group_key], txid)
        try:
          yield lock.acquire()
        except entity_lock.LockTimeout:
          raise Timeout('Unable to acquire entity group lock')

        try:
          yield self.delete_entities(
            group_key,
            txid,
            key_list,
            composite_indexes=filtered_indexes
          )
          lock.release()
        finally:
          # In case of failure entity group lock should stay acquired
          # as transaction groomer will handle it later.
          # But tornado lock must be released.
          lock.ensure_release_tornado_lock()

        self.logger.debug('Removed {} entities'.format(len(key_list)))
        self.transaction_manager.delete_transaction_id(app_id, txid)

  def generate_filter_info(self, filters):
    """Transform a list of filters into a more usable form.

    Args:
      filters: A list of filter PBs.
    Returns:
      A dict mapping property names to lists of (op, value) tuples.
    """
    filter_info = {}
    for filt in filters:
      prop = filt.property(0)
      value = prop.value()
      if prop.name() == '__key__':
        value = reference_property_to_reference(value.referencevalue())
        value = value.path()
      filter_info.setdefault(prop.name(), []).\
        append((filt.op(), encode_index_pb(value)))
    return filter_info

  def generate_order_info(self, orders):
    """Transform a list of orders into a more usable form which
       is a tuple of properties and ordering directions.

    Args:
      orders: A list of order PBs.
    Returns:
      A list of (property, direction) tuples.
    """
    orders = [(order.property(), order.direction()) for order in orders]
    if orders and orders[-1] == ('__key__', datastore_pb.Query_Order.ASCENDING):
      orders.pop()
    return orders

  @gen.coroutine
  def __get_start_key(self, prefix, prop_name, order, last_result, query=None):
    """ Builds the start key for cursor query.

    Args:
      prefix: The start key prefix (app id and namespace).
      prop_name: Property name of the filter.
      order: Sort order the query requires.
      last_result: Last result encoded in cursor.
      query: A datastore_pb.Query object.
    Raises:
      AppScaleDBError if unable to retrieve original entity or original entity
        no longer has the requested property.
    """
    e = last_result
    path = str(encode_index_pb(e.key().path()))
    last_result_key = self._SEPARATOR.join([prefix, path])
    if not prop_name and not order:
      raise gen.Return(last_result_key)
    if e.property_list():
      plist = e.property_list()
    else:
      # Fetch the entity from the datastore in order to get the property
      # values.
      ret = yield self.datastore_batch.batch_get_entity(
        dbconstants.APP_ENTITY_TABLE, [last_result_key], APP_ENTITY_SCHEMA)

      if APP_ENTITY_SCHEMA[0] not in ret[last_result_key]:
        message = '{} not found in {}'.format(
          last_result_key, dbconstants.APP_ENTITY_TABLE)
        raise dbconstants.AppScaleDBError(message)

      ent = entity_pb.EntityProto(ret[last_result_key][APP_ENTITY_SCHEMA[0]])
      plist = ent.property_list()

    val = None

    # Use the value from the query if possible. This reduces ambiguity when
    # the entity provided by the cursor has multiple values for the property.
    if (query is not None and query.filter_size() == 1 and
        query.filter(0).op() == datastore_pb.Query_Filter.EQUAL):
      query_prop = query.filter(0).property(0)
      val = str(encode_index_pb(query_prop.value()))

    if val is None:
      for p in plist:
        if p.name() == prop_name:
          val = str(encode_index_pb(p.value()))
          break

    if val is None:
      raise dbconstants.AppScaleDBError('{} not in entity'.format(prop_name))

    if order == datastore_pb.Query_Order.DESCENDING:
      val = helper_functions.reverse_lex(val)
    params = [prefix, get_entity_kind(e), prop_name, val, path]
    raise gen.Return(get_index_key_from_params(params))

  def is_zigzag_merge_join(self, query, filter_info, order_info):
    """ Checks to see if the current query can be executed as a zigzag
    merge join.

    Args:
      query: A datastore_pb.Query.
      filter_info: dict of property names mapping to tuples of filter
        operators and values.
      order_info: tuple with property name and the sort order.
    Returns:
      True if it qualifies as a zigzag merge join, and false otherwise.
    """
    filter_info = self.remove_exists_filters(filter_info)

    order_properties = []
    for order in order_info:
      order_properties.append(order[0])

    property_names = []
    for property_name in filter_info:
      filt = filter_info[property_name]
      property_names.append(property_name)
      # We only handle equality filters for zigzag merge join queries.
      if filt[0][0] != datastore_pb.Query_Filter.EQUAL:
        return False

    if len(filter_info) < 2:
      return False

    for order_property_name in order_properties:
      if order_property_name not in property_names:
        return False

    return True

  @gen.coroutine
  def __fetch_entities_from_row_list(self, rowkeys):
    """ Given a list of keys fetch the entities from the entity table.

    Args:
      rowkeys: A list of strings which are keys to the entitiy table.
    Returns:
      A list of entities.
    """
    result = yield self.datastore_batch.batch_get_entity(
      dbconstants.APP_ENTITY_TABLE, rowkeys, APP_ENTITY_SCHEMA)
    entities = []
    for key in rowkeys:
      if key in result and APP_ENTITY_SCHEMA[0] in result[key]:
        entities.append(result[key][APP_ENTITY_SCHEMA[0]])
    raise gen.Return(entities)

  def __extract_rowkeys_from_refs(self, refs):
    """ Extract the rowkeys to fetch from a list of references.

    Args:
      refs: key/value pairs where the values contain a reference to the
            entitiy table.
    Returns:
      A list of rowkeys.
    """
    if len(refs) == 0:
      return []
    keys = [item.keys()[0] for item in refs]
    rowkeys = []
    for index, ent in enumerate(refs):
      key = keys[index]
      ent = ent[key]['reference']
      # Make sure not to fetch the same entity more than once.
      if ent not in rowkeys:
        rowkeys.append(ent)
    return rowkeys

  @gen.coroutine
  def __fetch_entities(self, refs):
    """ Given a list of references, get the entities.

    Args:
      refs: key/value pairs where the values contain a reference to
            the entitiy table.
    Returns:
      A list of validated entities.
    """
    rowkeys = self.__extract_rowkeys_from_refs(refs)
    result = yield self.__fetch_entities_from_row_list(rowkeys)
    raise gen.Return(result)

  @gen.coroutine
  def __fetch_entities_dict(self, refs):
    """ Given a list of references, return the entities as a dictionary.

    Args:
      refs: key/value pairs where the values contain a reference to
            the entitiy table.
    Returns:
      A dictionary of validated entities.
    """
    rowkeys = self.__extract_rowkeys_from_refs(refs)
    result = yield self.__fetch_entities_dict_from_row_list(rowkeys)
    raise gen.Return(result)

  @gen.coroutine
  def __fetch_entities_dict_from_row_list(self, rowkeys):
    """ Given a list of rowkeys, return the entities as a dictionary.

    Args:
      rowkeys: A list of strings which are keys to the entitiy table.
    Returns:
      A dictionary of validated entities.
    """
    results = yield self.datastore_batch.batch_get_entity(
      dbconstants.APP_ENTITY_TABLE, rowkeys, APP_ENTITY_SCHEMA)

    clean_results = {}
    for key in rowkeys:
      if key in results and APP_ENTITY_SCHEMA[0] in results[key]:
        clean_results[key] = results[key][APP_ENTITY_SCHEMA[0]]

    raise gen.Return(clean_results)

  @gen.coroutine
  def __fetch_and_validate_entity_set(self, index_dict, limit, app_id,
    direction):
    """ Fetch all the valid entities as needed from references.

    Args:
      index_dict: A dictionary containing a list of index entries for each
        reference.
      limit: An integer specifying the max number of entities needed.
      app_id: A string, the application identifier.
      direction: The direction of the index.
    Returns:
      A list of valid entities.
    """
    references = index_dict.keys()
    # Prevent duplicate entities across queries with a cursor.
    references.sort()
    offset = 0
    results = []
    to_fetch = limit
    added_padding = False
    while True:
      refs_to_fetch = references[offset:offset + to_fetch]

      # If we've exhausted the list of references, we can return.
      if len(refs_to_fetch) == 0:
        raise gen.Return(results[:limit])

      entities = yield self.__fetch_entities_dict_from_row_list(refs_to_fetch)

      # Prevent duplicate entities across queries with a cursor.
      entity_keys = entities.keys()
      entity_keys.sort()

      for reference in entity_keys:
        use_result = False
        indexes_to_check = index_dict[reference]
        for index_info in indexes_to_check:
          index = index_info['index']
          prop_name = index_info['prop_name']
          entry = {index: {'reference': reference}}
          if self.__valid_index_entry(entry, entities, direction, prop_name):
            use_result = True
          else:
            use_result = False
            break

        if use_result:
          results.append(entities[reference])
          if len(results) >= limit:
            raise gen.Return(results[:limit])

      offset = offset + to_fetch

      to_fetch -= len(results)

      # Pad the number of references to fetch to increase the likelihood of
      # getting all the valid references that we need.
      if not added_padding:
        to_fetch += dbconstants.MAX_GROUPS_FOR_XG
        added_padding = True

  def __extract_entities(self, kv):
    """ Given a result from a range query on the Entity table return a
        list of encoded entities.

    Args:
      kv: Key and values from a range query on the entity table.
    Returns:
      The extracted entities.
    """
    keys = [item.keys()[0] for item in kv]
    results = []
    for index, entity in enumerate(kv):
      key = keys[index]
      entity = entity[key][APP_ENTITY_SCHEMA[0]]
      results.append(entity)

    return results

  @gen.coroutine
  def ancestor_query(self, query, filter_info):
    """ Performs ancestor queries which is where you select
        entities based on a particular root entity.

    Args:
      query: The query to run.
      filter_info: Tuple with filter operators and values.
    Returns:
      A tuple containing a list of entities and a boolean indicating if there
      are more results for the query.
    Raises:
      ZKTransactionException: If a lock could not be acquired.
    """
    ancestor = query.ancestor()
    prefix = self.get_table_prefix(query)
    path = buffer(prefix + self._SEPARATOR) + encode_index_pb(ancestor.path())
    txn_id = 0
    if query.has_transaction():
      txn_id = query.transaction().handle()

    startrow = path
    endrow = path + self._TERM_STRING

    end_inclusive = self._ENABLE_INCLUSIVITY
    start_inclusive = self._ENABLE_INCLUSIVITY

    if '__key__' in filter_info:
      op = filter_info['__key__'][0][0]
      __key__ = str(filter_info['__key__'][0][1])
      if op and op == datastore_pb.Query_Filter.EQUAL:
        startrow = prefix + self._SEPARATOR + __key__
        endrow = prefix + self._SEPARATOR + __key__
      elif op and op == datastore_pb.Query_Filter.GREATER_THAN:
        start_inclusive = self._DISABLE_INCLUSIVITY
        startrow = prefix + self._SEPARATOR + __key__
      elif op and op == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
        startrow = prefix + self._SEPARATOR + __key__
      elif op and op == datastore_pb.Query_Filter.LESS_THAN:
        endrow = prefix + self._SEPARATOR  + __key__
        end_inclusive = self._DISABLE_INCLUSIVITY
      elif op and op == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
        endrow = prefix + self._SEPARATOR + __key__

    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
      cursor = appscale_stub_util.ListCursor(query)
      last_result = cursor._GetLastResult()
      startrow = yield self.__get_start_key(prefix, None, None, last_result)
      start_inclusive = self._DISABLE_INCLUSIVITY
      if query.compiled_cursor().position_list()[0].start_inclusive() == 1:
        start_inclusive = self._ENABLE_INCLUSIVITY

    more_results = False

    if startrow > endrow:
      raise gen.Return(([], more_results))

    request_limit, check_more_results = self.get_limit(query)
    fetch_count = request_limit
    if check_more_results:
      fetch_count += 1

    entities = []
    while True:
      results = yield self.datastore_batch.range_query(
        dbconstants.APP_ENTITY_TABLE,
        APP_ENTITY_SCHEMA,
        startrow,
        endrow,
        fetch_count,
        start_inclusive=start_inclusive,
        end_inclusive=end_inclusive)

      if query.has_kind():
        entities.extend([
          result.values()[0]['entity'] for result in results
          if kind_from_encoded_key(result.keys()[0]) == query.kind()])
      else:
        entities.extend([result.values()[0]['entity'] for result in results])

      if len(results) < fetch_count:
        break

      if len(entities) >= fetch_count:
        break

      # TODO: This can be made more efficient by skipping ahead to the next
      # possible match.
      startrow = results[-1].keys()[0]
      start_inclusive = False

    if query.has_transaction():
      yield self.datastore_batch.record_reads(
        query.app(), query.transaction().handle(), [group_for_key(ancestor)])

    if check_more_results and len(entities) > request_limit:
      more_results = True

    raise gen.Return((entities[:request_limit], more_results))

  @gen.coroutine
  def fetch_from_entity_table(self,
                              startrow,
                              endrow,
                              limit,
                              offset,
                              start_inclusive,
                              end_inclusive,
                              query,
                              txn_id):
    """
    Fetches entities from the entity table given a query and a set of parameters.
    It will validate the results and remove tombstoned items.

    Args:
       startrow: The key from which we start a range query.
       endrow: The end key that terminates a range query.
       limit: The maximum number of items to return from a query.
       offset: The number of entities we want removed from the front of the result.
       start_inclusive: Boolean if we should include the start key in the result.
       end_inclusive: Boolean if we should include the end key in the result.
       query: The query we are currently running.
       txn_id: The current transaction ID if there is one, it is 0 if there is not.
    Returns:
       A validated database result.
    """
    final_result = []
    while 1:
      result = yield self.datastore_batch.range_query(
        dbconstants.APP_ENTITY_TABLE,
        APP_ENTITY_SCHEMA,
        startrow,
        endrow,
        limit,
        offset=0,
        start_inclusive=start_inclusive,
        end_inclusive=end_inclusive)

      prev_len = len(result)
      last_result = None
      if result:
        last_result = result[-1].keys()[0]
      else:
        break

      final_result += result

      if len(result) != prev_len:
        startrow = last_result
        start_inclusive = self._DISABLE_INCLUSIVITY
        limit = limit - len(result)
        continue
      else:
        break

    raise gen.Return(self.__extract_entities(final_result))

  @gen.coroutine
  def kindless_query(self, query, filter_info):
    """ Performs kindless queries where queries are performed
        on the entity table and go across kinds.

    Args:
      query: The query to run.
      filter_info: Tuple with filter operators and values.
    Returns:
      A tuple containing entities that match the query and a boolean indicating
      if there are more results for the query.
    """
    prefix = self.get_table_prefix(query)

    filters = []
    if '__key__' in filter_info:
      for filter in filter_info['__key__']:
        filters.append({'key': str(filter[1]), 'op': filter[0]})

    order = None
    prop_name = None

    startrow = prefix + self._SEPARATOR
    endrow = prefix + self._SEPARATOR + self._TERM_STRING
    start_inclusive = self._ENABLE_INCLUSIVITY
    end_inclusive = self._ENABLE_INCLUSIVITY
    for filter in filters:
      if filter['op'] == datastore_pb.Query_Filter.EQUAL:
        startrow = prefix + self._SEPARATOR + filter['key']
        endrow = startrow
      if filter['op'] == datastore_pb.Query_Filter.GREATER_THAN:
        startrow = prefix + self._SEPARATOR + filters[0]['key']
        start_inclusive = self._DISABLE_INCLUSIVITY
      if filter['op'] == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
        startrow = prefix + self._SEPARATOR + filters[0]['key']
      if filter['op'] == datastore_pb.Query_Filter.LESS_THAN:
        endrow = prefix + self._SEPARATOR + filter['key']
        end_inclusive = self._DISABLE_INCLUSIVITY
      if filter['op'] == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
        endrow = prefix + self._SEPARATOR + filter['key']

    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
      cursor = appscale_stub_util.ListCursor(query)
      last_result = cursor._GetLastResult()
      startrow = yield self.__get_start_key(
        prefix, prop_name, order, last_result)
      start_inclusive = self._DISABLE_INCLUSIVITY
      if query.compiled_cursor().position_list()[0].start_inclusive() == 1:
        start_inclusive = self._ENABLE_INCLUSIVITY

    more_results = False
    request_limit, check_more_results = self.get_limit(query)
    fetch_count = request_limit
    if check_more_results:
      fetch_count += 1

    result = yield self.fetch_from_entity_table(
      startrow, endrow, fetch_count, offset=0, start_inclusive=start_inclusive,
      end_inclusive=end_inclusive, query=query, txn_id=0)

    if check_more_results and len(result) > request_limit:
      more_results = True

    raise gen.Return((result[:request_limit], more_results))

  def reverse_path(self, key):
    """ Use this function for reversing the key ancestry order.
        Needed for kind queries.

    Args:
      key: A string key which needs reversing.
    Returns:
      A string key which can be used on the kind table.
    """
    tokens = key.split(dbconstants.KIND_SEPARATOR)
    tokens.reverse()
    key = dbconstants.KIND_SEPARATOR.join(tokens)[1:] + \
      dbconstants.KIND_SEPARATOR
    return key

  def kind_query_range(self, query, filter_info, order_info):
    """ Gets start and end keys for kind queries, along with
        inclusivity of those keys.

    Args:
      query: The query to run.
      filter_info: __key__ filter.
      order_info: ordering for __key__.
    Returns:
      A tuple of the start row, end row, if its start inclusive,
      and if its end inclusive
    """
    ancestor_filter = ""
    if query.has_ancestor():
      ancestor = query.ancestor()
      ancestor_filter = encode_index_pb(ancestor.path())
    end_inclusive = self._ENABLE_INCLUSIVITY
    start_inclusive = self._ENABLE_INCLUSIVITY
    prefix = self.get_table_prefix(query)
    startrow = prefix + self._SEPARATOR + query.kind() + \
      dbconstants.KIND_SEPARATOR + \
      str(ancestor_filter)
    endrow = prefix + self._SEPARATOR + query.kind() + \
      dbconstants.KIND_SEPARATOR + \
      str(ancestor_filter) + \
      self._TERM_STRING
    if '__key__' not in filter_info:
      return startrow, endrow, start_inclusive, end_inclusive

    for key_filter in filter_info['__key__']:
      op = key_filter[0]
      __key__ = str(key_filter[1])
      if op and op == datastore_pb.Query_Filter.EQUAL:
        startrow = prefix + self._SEPARATOR + query.kind() + \
          dbconstants.KIND_SEPARATOR + __key__
        endrow = prefix + self._SEPARATOR + query.kind() + \
          dbconstants.KIND_SEPARATOR + __key__
      elif op and op == datastore_pb.Query_Filter.GREATER_THAN:
        start_inclusive = self._DISABLE_INCLUSIVITY
        startrow = prefix + self._SEPARATOR + query.kind() + \
          dbconstants.KIND_SEPARATOR + __key__
      elif op and op == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
        startrow = prefix + self._SEPARATOR + query.kind() + \
          dbconstants.KIND_SEPARATOR + __key__
      elif op and op == datastore_pb.Query_Filter.LESS_THAN:
        endrow = prefix + self._SEPARATOR + query.kind() + \
          dbconstants.KIND_SEPARATOR + __key__
        end_inclusive = self._DISABLE_INCLUSIVITY
      elif op and op == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
        endrow = prefix + self._SEPARATOR + query.kind() + \
          dbconstants.KIND_SEPARATOR + __key__
    return startrow, endrow, start_inclusive, end_inclusive

  def default_namespace(self):
    """ Returns the default namespace entry because the groomer does not
    generate it for each application.

    Returns:
      A entity proto of the default metadata.Namespace.
    """
    default_namespace = Namespace(id=1)
    protobuf = db.model_to_protobuf(default_namespace)
    last_path = protobuf.key().path().element_list()[-1]
    last_path.set_id(1)
    return protobuf.Encode()

  @gen.coroutine
  def __kind_query(self, query, filter_info, order_info):
    """ Performs kind only queries, kind and ancestor, and ancestor queries
        https://developers.google.com/appengine/docs/python/datastore/queries.

    Args:
      query: The query to run.
      filter_info: tuple with filter operators and values.
      order_info: tuple with property name and the sort order.
    Returns:
      A tuple containing an ordered list of entities matching the query and a
      boolean indicating if there are more results for the query.
    Raises:
      AppScaleDBError: An infinite loop is detected when fetching references.
    """
    self.logger.debug('Kind Query:\n{}'.format(query))

    more_results = False

    filter_info = self.remove_exists_filters(filter_info)
    # Detect quickly if this is a kind query or not.
    for fi in filter_info:
      if fi != "__key__":
        raise gen.Return((None, more_results))

    if query.has_ancestor():
      if len(order_info) > 0:
        # Ordered ancestor queries require an index.
        raise gen.Return((None, more_results))

      result, more_results = yield self.ancestor_query(query, filter_info)
      raise gen.Return((result, more_results))

    if not query.has_kind():
      result, more_results = yield self.kindless_query(query, filter_info)
      raise gen.Return((result, more_results))

    if query.kind().startswith("__") and query.kind().endswith("__"):
      # Use the default namespace for metadata queries.
      query.set_name_space("")

    startrow, endrow, start_inclusive, end_inclusive = \
      self.kind_query_range(query, filter_info, order_info)
    if startrow is None or endrow is None:
      raise gen.Return((None, more_results))

    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
      cursor = appscale_stub_util.ListCursor(query)
      last_result = cursor._GetLastResult()
      prefix = self.get_table_prefix(query)
      startrow = get_kind_key(prefix, last_result.key().path())
      start_inclusive = self._DISABLE_INCLUSIVITY
      if query.compiled_cursor().position_list()[0].start_inclusive() == 1:
        start_inclusive = self._ENABLE_INCLUSIVITY

    request_limit, check_more_results = self.get_limit(query)
    fetch_count = request_limit
    if check_more_results:
      fetch_count += 1

    if startrow > endrow:
      raise gen.Return(([], more_results))

    # Since the validity of each reference is not checked until after the
    # range query has been performed, we may need to fetch additional
    # references in order to satisfy the query.
    entities = []
    current_limit = fetch_count
    while True:
      references = yield self.datastore_batch.range_query(
        dbconstants.APP_KIND_TABLE,
        dbconstants.APP_KIND_SCHEMA,
        startrow,
        endrow,
        current_limit,
        offset=0,
        start_inclusive=start_inclusive,
        end_inclusive=end_inclusive
      )

      new_entities = yield self.__fetch_entities(references)
      entities.extend(new_entities)

      # If we have enough valid entities to satisfy the query, we're done.
      if len(entities) >= fetch_count:
        break

      # If we received fewer references than we asked for, they are exhausted.
      if len(references) < current_limit:
        break

      # If all of the references that we fetched were valid, we're done.
      if len(new_entities) == len(references):
        break

      invalid_refs = len(references) - len(new_entities)

      # Pad the limit to increase the likelihood of fetching all the valid
      # references that we need.
      current_limit = invalid_refs + dbconstants.MAX_GROUPS_FOR_XG

      self.logger.debug('{} references invalid. Fetching {} more references.'
        .format(invalid_refs, current_limit))

      # Start from the last reference fetched.
      last_startrow = startrow
      startrow = references[-1].keys()[0]
      start_inclusive = self._DISABLE_INCLUSIVITY

      if startrow == last_startrow:
        raise dbconstants.AppScaleDBError(
          'An infinite loop was detected while fetching references.')

    if query.kind() == "__namespace__":
      entities = [self.default_namespace()] + entities

    if check_more_results and len(entities) > request_limit:
      more_results = True

    results = entities[:request_limit]

    # Handle projection queries.
    if query.property_name_size() > 0:
      results = self.remove_extra_props(query, results)

    self.logger.debug('Returning {} entities'.format(len(results)))
    raise gen.Return((results, more_results))

  def remove_exists_filters(self, filter_info):
    """ Remove any filters that have EXISTS filters.

    Args:
      filter_info: dict of property names mapping to tuples of filter
        operators and values.
    Returns:
      A filter info dictionary without any EXIST filters.
    """
    filtered = {}
    for key in filter_info.keys():
      if filter_info[key][0][0] == datastore_pb.Query_Filter.EXISTS:
        continue
      else:
        filtered[key] = filter_info[key]
    return filtered

  def remove_extra_equality_filters(self, potential_filter_ops):
    """ Keep only the first equality filter for a given property.

    Args:
      potential_filter_ops: A list of tuples in the form (operation, value).
    Returns:
      A filter_ops list with only one equality filter.
    """
    filter_ops = []
    saw_equality_filter = False
    for operation, value in potential_filter_ops:
      if operation == datastore_pb.Query_Filter.EQUAL and saw_equality_filter:
        continue

      if operation == datastore_pb.Query_Filter.EQUAL:
        saw_equality_filter = True

      filter_ops.append((operation, value))

    return filter_ops

  @gen.coroutine
  def __single_property_query(self, query, filter_info, order_info):
    """Performs queries satisfiable by the Single_Property tables.

    Args:
      query: The query to run.
      filter_info: tuple with filter operators and values.
      order_info: tuple with property name and the sort order.
    Returns:
      A tuple containing a list of entities retrieved from the given query and
      a boolean indicating if there are more results for the query.
    """
    self.logger.debug('Single Property Query:\n{}'.format(query))
    if query.kind().startswith("__") and \
      query.kind().endswith("__"):
      # Use the default namespace for metadata queries.
      query.set_name_space("")

    more_results = False

    filter_info = self.remove_exists_filters(filter_info)
    ancestor = None
    property_names = set(filter_info.keys())
    property_names.update(x[0] for x in order_info)
    property_names.discard('__key__')
    if len(property_names) != 1:
      raise gen.Return((None, more_results))

    property_name = property_names.pop()
    potential_filter_ops = filter_info.get(property_name, [])

    # We will apply the other equality filters after fetching the entities.
    filter_ops = self.remove_extra_equality_filters(potential_filter_ops)

    multiple_equality_filters = self.__get_multiple_equality_filters(
      query.filter_list())

    if len(order_info) > 1 or (order_info and order_info[0][0] == '__key__'):
      raise gen.Return((None, more_results))

    # If there is an ancestor in the query, any filtering must be within a
    # single value when using a single-prop index.
    spans_multiple_values = order_info or (
      filter_ops and filter_ops[0][0] != datastore_pb.Query_Filter.EQUAL)
    if query.has_ancestor() and spans_multiple_values:
      raise gen.Return((None, more_results))

    if query.has_ancestor():
      ancestor = query.ancestor()

    if not query.has_kind():
      raise gen.Return((None, more_results))

    if order_info and order_info[0][0] == property_name:
      direction = order_info[0][1]
    else:
      direction = datastore_pb.Query_Order.ASCENDING

    prefix = self.get_table_prefix(query)

    request_limit, check_more_results = self.get_limit(query)

    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
      cursor = appscale_stub_util.ListCursor(query)
      last_result = cursor._GetLastResult()
      startrow = yield self.__get_start_key(
        prefix, property_name, direction, last_result, query=query)
    else:
      startrow = None

    end_compiled_cursor = None
    if query.has_end_compiled_cursor():
      end_compiled_cursor = query.end_compiled_cursor()

    # Since the validity of each reference is not checked until after the
    # range query has been performed, we may need to fetch additional
    # references in order to satisfy the query.
    entities = []
    fetch_count = request_limit
    if check_more_results:
      fetch_count += 1

    current_limit = fetch_count
    while True:
      references = yield self.__apply_filters(
        filter_ops, order_info, property_name, query.kind(), prefix,
        current_limit, startrow, ancestor=ancestor, query=query,
        end_compiled_cursor=end_compiled_cursor)

      potential_entities = yield self.__fetch_entities_dict(references)

      # Since the entities may be out of order due to invalid references,
      # we construct a new list in order of valid references.
      new_entities = []
      for reference in references:
        if self.__valid_index_entry(reference, potential_entities, direction,
          property_name):
          entity_key = reference[reference.keys()[0]]['reference']
          valid_entity = potential_entities[entity_key]
          new_entities.append(valid_entity)

      if len(multiple_equality_filters) > 0:
        self.logger.debug('Detected multiple equality filters on a repeated'
          'property. Removing results that do not match query.')
        new_entities = self.__apply_multiple_equality_filters(
          new_entities, multiple_equality_filters)

      entities.extend(new_entities)

      # If we have enough valid entities to satisfy the query, we're done.
      if len(entities) >= fetch_count:
        break

      # If we received fewer references than we asked for, they are exhausted.
      if len(references) < current_limit:
        break

      # If all of the references that we fetched were valid, we're done.
      if len(new_entities) == len(references):
        break

      invalid_refs = len(references) - len(new_entities)

      # Pad the limit to increase the likelihood of fetching all the valid
      # references that we need.
      current_limit = invalid_refs + dbconstants.MAX_GROUPS_FOR_XG

      self.logger.debug('{} references invalid. Fetching {} more references.'
        .format(invalid_refs, current_limit))

      last_startrow = startrow
      # Start from the last reference fetched.
      startrow = references[-1].keys()[0]

      if startrow == last_startrow:
        raise dbconstants.AppScaleDBError(
          'An infinite loop was detected while fetching references.')

    if check_more_results and len(entities) > request_limit:
      more_results = True

    results = entities[:request_limit]

    # Handle projection queries.
    # TODO: When the index has been confirmed clean, use those values directly.
    if query.property_name_size() > 0:
      results = self.remove_extra_props(query, results)

    self.logger.debug('Returning {} results'.format(len(results)))
    raise gen.Return((results, more_results))

  @gen.coroutine
  def __apply_filters(self,
                     filter_ops,
                     order_info,
                     property_name,
                     kind,
                     prefix,
                     limit,
                     startrow,
                     force_start_key_exclusive=False,
                     ancestor=None,
                     query=None,
                     end_compiled_cursor=None):
    """ Applies property filters in the query.

    Args:
      filter_ops: Tuple with property filter operator and value.
      order_info: Tuple with property name and sort order.
      kind: Kind of the entity.
      prefix: Prefix for the table.
      limit: Number of results.
      startrow: Start key for the range scan.
      force_start_key_exclusive: Do not include the start key.
      ancestor: Optional query ancestor.
      query: Query object for debugging.
      end_compiled_cursor: A compiled cursor to resume a query.
    Results:
      Returns a list of entity keys.
    Raises:
      NotImplementedError: For unsupported queries.
      AppScaleMisconfiguredQuery: Bad filters or orderings.
    """
    ancestor_filter = None
    if ancestor:
      ancestor_filter = str(encode_index_pb(ancestor.path()))

    end_inclusive = True
    start_inclusive = True

    endrow = None
    column_names = dbconstants.PROPERTY_SCHEMA

    if order_info and order_info[0][0] == property_name:
        direction = order_info[0][1]
    else:
      direction = datastore_pb.Query_Order.ASCENDING

    if direction == datastore_pb.Query_Order.ASCENDING:
      table_name = dbconstants.ASC_PROPERTY_TABLE
    else:
      table_name = dbconstants.DSC_PROPERTY_TABLE

    if startrow:
      start_inclusive = False

    if end_compiled_cursor:
      list_cursor = appscale_stub_util.ListCursor(query)
      last_result, _ = list_cursor._DecodeCompiledCursor(end_compiled_cursor)
      endrow = yield self.__get_start_key(
        prefix, property_name, direction, last_result)

    # This query is returning based on order on a specfic property name
    # The start key (if not already supplied) depends on the property
    # name and does not take into consideration its value. The end key
    # is based on the terminating string.
    if len(filter_ops) == 0 and (order_info and len(order_info) == 1):
      if not startrow:
        params = [prefix, kind, property_name, None]
        startrow = get_index_key_from_params(params)
      if not endrow:
        params = [prefix, kind, property_name, self._TERM_STRING, None]
        endrow = get_index_key_from_params(params)
      if force_start_key_exclusive:
        start_inclusive = False
      result = yield self.datastore_batch.range_query(
        table_name, column_names, startrow, endrow, limit,
        offset=0, start_inclusive=start_inclusive, end_inclusive=end_inclusive)
      raise gen.Return(result)

    # This query has a value it bases the query on for a property name
    # The difference between operators is what the end and start key are.
    if len(filter_ops) == 1:
      key_comparison = False
      oper = filter_ops[0][0]
      value = str(filter_ops[0][1])

      if direction == datastore_pb.Query_Order.DESCENDING:
        value = helper_functions.reverse_lex(value)
      if oper == datastore_pb.Query_Filter.EQUAL:
        if ancestor:  # Keep range within ancestor key.
          start_value = ''.join([value, self._SEPARATOR, ancestor_filter])
        else:  # Keep range within property value.
          start_value = ''.join([value, self._SEPARATOR])
        end_value = ''.join([start_value, self._TERM_STRING])

        # Single prop indexes can handle key inequality within a given value
        # (eg. color='blue', __key__<Key('Bike', 5)).
        key_comparison = (query.filter_size() == 2 and
                          query.filter(1).property(0).name() == '__key__')
        if key_comparison:
          encoded_path = encode_path_from_filter(query.filter(1))
          ops = datastore_pb.Query_Filter
          key_op = query.filter(1).op()
          if key_op in (ops.LESS_THAN, ops.LESS_THAN_OR_EQUAL):
            end_value = ''.join([value, self._SEPARATOR, encoded_path])
            end_inclusive = key_op == ops.LESS_THAN_OR_EQUAL
          elif key_op in (ops.GREATER_THAN, ops.GREATER_THAN_OR_EQUAL):
            start_value = ''.join([value, self._SEPARATOR, encoded_path])
            start_inclusive = key_op == ops.GREATER_THAN_OR_EQUAL
      elif oper == datastore_pb.Query_Filter.LESS_THAN:
        start_value = ""
        end_value = value
        if direction == datastore_pb.Query_Order.DESCENDING:
          start_value = value + self._TERM_STRING
          end_value = self._TERM_STRING
      elif oper == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
        start_value = ""
        end_value = value + self._SEPARATOR + self._TERM_STRING
        if direction == datastore_pb.Query_Order.DESCENDING:
          start_value = value
          end_value = self._TERM_STRING
      elif oper == datastore_pb.Query_Filter.GREATER_THAN:
        if value == '':
          start_value = self.MIN_INDEX_VALUE + self._TERM_STRING
        else:
          start_value = value + self._TERM_STRING
        end_value = self._TERM_STRING
        if direction == datastore_pb.Query_Order.DESCENDING:
          start_value = self.MIN_INDEX_VALUE
          end_value = value + self._SEPARATOR
      elif oper == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
        start_value = value
        end_value = self._TERM_STRING
        if direction == datastore_pb.Query_Order.DESCENDING:
          start_value = self.MIN_INDEX_VALUE
          end_value = value + self._SEPARATOR +  self._TERM_STRING
      else:
        raise NotImplementedError("Unsupported query of operation {0}".format(
          datastore_pb.Query_Filter.Operator_Name(oper)))

      if not startrow:
        params = [prefix, kind, property_name, start_value]
        startrow = get_index_key_from_params(params)
        if not key_comparison:
          start_inclusive = self._DISABLE_INCLUSIVITY
      if not endrow:
        params = [prefix, kind, property_name, end_value]
        endrow = get_index_key_from_params(params)

      if force_start_key_exclusive:
        start_inclusive = False

      if startrow > endrow:
        self.logger.error('Start row {} > end row {}'.
          format([startrow], [endrow]))
        raise gen.Return([])

      ret = yield self.datastore_batch.range_query(
        table_name, column_names, startrow, endrow, limit,
        offset=0, start_inclusive=start_inclusive, end_inclusive=end_inclusive)
      raise gen.Return(ret)

    # Here we have two filters and so we set the start and end key to
    # get the given value within those ranges.
    if len(filter_ops) > 1:
      if filter_ops[0][0] == datastore_pb.Query_Filter.EQUAL or \
        filter_ops[1][0] == datastore_pb.Query_Filter.EQUAL:
        # If one of the filters is EQUAL, set start and end key
        # to the same value.
        if filter_ops[0][0] == datastore_pb.Query_Filter.EQUAL:
          value1 = filter_ops[0][1]
          value2 = filter_ops[1][1]
          oper2 = filter_ops[1][0]
        else:
          value1 = filter_ops[1][1]
          value2 = filter_ops[0][1]
          oper2 = filter_ops[0][0]
        # Checking to see if filters/values are correct bounds.
        # value1 and oper1 are the EQUALS filter values.
        if oper2 == datastore_pb.Query_Filter.LESS_THAN:
          if value2 > value1 == False:
            raise gen.Return([])
        elif oper2 == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
          if value2 >= value1 == False:
            raise gen.Return([])
        elif oper2 == datastore_pb.Query_Filter.GREATER_THAN:
          if value2 < value1 == False:
            raise gen.Return([])
        elif oper2 == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
          if value2 <= value1 == False:
            raise gen.Return([])
        start_inclusive = self._ENABLE_INCLUSIVITY
        end_inclusive = self._DISABLE_INCLUSIVITY
        params = [prefix, kind, property_name, value1 + self._SEPARATOR]
        if not startrow:
          startrow = get_index_key_from_params(params)
        else:
          start_inclusive = self._DISABLE_INCLUSIVITY
        if not endrow:
          params = [prefix, kind, property_name, value1 + \
            self._SEPARATOR + self._TERM_STRING]
          endrow = get_index_key_from_params(params)

        ret = yield self.datastore_batch.range_query(
          table_name, column_names, startrow, endrow, limit,
          offset=0, start_inclusive=start_inclusive,
          end_inclusive=end_inclusive)
        raise gen.Return(ret)
      if filter_ops[0][0] == datastore_pb.Query_Filter.GREATER_THAN or \
         filter_ops[0][0] == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
        oper1 = filter_ops[0][0]
        oper2 = filter_ops[1][0]
        value1 = str(filter_ops[0][1])
        value2 = str(filter_ops[1][1])
      else:
        oper1 = filter_ops[1][0]
        oper2 = filter_ops[0][0]
        value1 = str(filter_ops[1][1])
        value2 = str(filter_ops[0][1])

      if direction == datastore_pb.Query_Order.ASCENDING:
        table_name = dbconstants.ASC_PROPERTY_TABLE
        # The first operator will always be either > or >=.
        if startrow:
          start_inclusive = self._DISABLE_INCLUSIVITY
        elif oper1 == datastore_pb.Query_Filter.GREATER_THAN:
          params = [prefix, kind, property_name, value1 + self._SEPARATOR + \
                    self._TERM_STRING]
          startrow = get_index_key_from_params(params)
        elif oper1 == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
          params = [prefix, kind, property_name, value1 ]
          startrow = get_index_key_from_params(params)
        else:
          raise dbconstants.AppScaleMisconfiguredQuery("Bad filter ordering")

        # The second operator will be either < or <=.
        if endrow:
          end_inclusive = self._ENABLE_INCLUSIVITY
        elif oper2 == datastore_pb.Query_Filter.LESS_THAN:
          params = [prefix, kind, property_name, value2]
          endrow = get_index_key_from_params(params)
          end_inclusive = self._DISABLE_INCLUSIVITY
        elif oper2 == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
          params = [prefix, kind, property_name, value2 + self._SEPARATOR + \
                    self._TERM_STRING]
          endrow = get_index_key_from_params(params)
          end_inclusive = self._ENABLE_INCLUSIVITY
        else:
          raise dbconstants.AppScaleMisconfiguredQuery("Bad filter ordering")

      if direction == datastore_pb.Query_Order.DESCENDING:
        table_name = dbconstants.DSC_PROPERTY_TABLE
        value1 = helper_functions.reverse_lex(value1)
        value2 = helper_functions.reverse_lex(value2)

        if endrow:
          end_inclusive = self._ENABLE_INCLUSIVITY
        elif oper1 == datastore_pb.Query_Filter.GREATER_THAN:
          params = [prefix, kind, property_name, value1]
          endrow = get_index_key_from_params(params)
          end_inclusive = self._DISABLE_INCLUSIVITY
        elif oper1 == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
          params = [prefix, kind, property_name, value1 + self._SEPARATOR + \
                    self._TERM_STRING]
          endrow = get_index_key_from_params(params)
          end_inclusive = self._ENABLE_INCLUSIVITY

        if startrow:
          start_inclusive = self._DISABLE_INCLUSIVITY
        elif oper2 == datastore_pb.Query_Filter.LESS_THAN:
          params = [prefix, kind, property_name, value2 + self._SEPARATOR + \
                    self._TERM_STRING]
          startrow = get_index_key_from_params(params)
        elif oper2 == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
          params = [prefix, kind, property_name, value2]
          startrow = get_index_key_from_params(params)

      if force_start_key_exclusive:
        start_inclusive = False
      if startrow > endrow:
        raise gen.Return([])

      result = yield self.datastore_batch.range_query(
        table_name, column_names, startrow, endrow, limit,
        offset=0, start_inclusive=start_inclusive, end_inclusive=end_inclusive)
      raise gen.Return(result)

    raise gen.Return([])

  @staticmethod
  @gen.coroutine
  def _common_refs_from_ranges(ranges, limit, path=None):
    """ Find common entries across multiple index ranges.

    Args:
      ranges: A list of RangeIterator objects.
      limit: An integer specifying the maximum number of references to find.
      path: An entity_pb.Path object that restricts the query to a single key.
    Returns:
      A dictionary mapping entity references to index entries.
    """
    if path is not None:
      limit = 1
      for range_ in ranges:
        range_.set_cursor(path, inclusive=True)

    reference_hash = {}
    min_common_path = ranges[0].get_cursor()
    entries_exhausted = False
    while True:
      common_keys = []
      entry = None
      for range_ in ranges:
        try:
          entry = yield range_.async_next()
        except RangeExhausted:
          # If any ranges have been exhausted, there are no more matches.
          entries_exhausted = True
          break

        # If this entry's path is ahead of the others, consider it the new
        # minimum acceptable path and adjust the other ranges.
        if entry.encoded_path > str(encode_index_pb(min_common_path)):
          min_common_path = entry.path
          break

        common_keys.append({'index': entry.key, 'prop_name': range_.prop_name})

      if entries_exhausted:
        break

      # If not all paths are common, adjust earlier ranges.
      if len(common_keys) < len(ranges):
        for range_ in ranges:
          range_.set_cursor(min_common_path, inclusive=True)

        continue

      reference_hash[entry.entity_reference] = common_keys

      # Ensure the chosen reference is excluded.
      for range_ in ranges:
        range_.set_cursor(min_common_path, inclusive=False)

      # If there are enough references to satisfy the query, stop fetching
      # entries.
      if len(reference_hash) == limit:
        break

    raise gen.Return(reference_hash)

  @gen.coroutine
  def zigzag_merge_join(self, query, filter_info, order_info):
    """ Performs a composite query for queries which have multiple
    equality filters. Uses a varient of the zigzag join merge algorithm.

    This method is used if there are only equality filters present.
    If there are inequality filters, orders on properties which are not also
    apart of a filter, or ancestors, this method does
    not apply.  Existing single property indexes are used and it does not
    require the user to establish composite indexes ahead of time.
    See http://www.youtube.com/watch?v=AgaL6NGpkB8 for Google's
    implementation.

    Args:
      query: A datastore_pb.Query.
      filter_info: dict of property names mapping to tuples of filter
        operators and values.
      order_info: tuple with property name and the sort order.
    Returns:
      A tuple containing a list of entities retrieved from the given query and
      a boolean indicating whether there are more results for the query.
    """
    self.logger.debug('ZigZag Merge Join Query:\n{}'.format(query))
    more_results = False

    if not self.is_zigzag_merge_join(query, filter_info, order_info):
      raise gen.Return((None, more_results))

    kind = query.kind()
    request_limit, check_more_results = self.get_limit(query)
    fetch_count = request_limit
    if check_more_results:
      fetch_count += 1

    app_id = clean_app_id(query.app())

    # We only use references from the ascending property table.
    direction = datastore_pb.Query_Order.ASCENDING

    prop_filters = [filter_ for filter_ in query.filter_list()
                    if filter_.property(0).name() != '__key__']
    ranges = [RangeIterator.from_filter(self.datastore_batch, app_id,
                                        query.name_space(), kind, filter_)
              for filter_ in prop_filters]

    # Check if the query is restricted to a single key.
    path = None
    key_filters = [filter_ for filter_ in query.filter_list()
                   if filter_.property(0).name() == '__key__']
    if len(key_filters) > 1:
      raise BadRequest('Queries can only specify one key')

    if key_filters:
      path = entity_pb.Path()
      ref_val = key_filters[0].property(0).value().referencevalue()
      for element in ref_val.pathelement_list():
        path.add_element().MergeFrom(element)

    if query.has_ancestor():
      for range_ in ranges:
        range_.restrict_to_path(query.ancestor().path())

    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
      cursor = appscale_stub_util.ListCursor(query)
      cursor_path = cursor._GetLastResult().key().path()
      for range_ in ranges:
        range_.set_cursor(cursor_path, inclusive=False)

    entities = []
    while True:
      reference_hash = yield self._common_refs_from_ranges(
        ranges, fetch_count, path)
      new_entities = yield self.__fetch_and_validate_entity_set(
        reference_hash, fetch_count, app_id, direction)
      entities.extend(new_entities)

      # If there are enough entities to satisfy the query, stop fetching.
      if len(entities) >= fetch_count:
        break

      # If there weren't enough common references to fulfill the limit, the
      # references are exhausted.
      if len(reference_hash) < fetch_count:
        break

    if check_more_results and len(entities) > request_limit:
      more_results = True

    results = entities[:request_limit]
    self.logger.debug('Returning {} results'.format(len(results)))
    raise gen.Return((results, more_results))

  def get_range_composite_query(self, query, filter_info, composite_index):
    """ Gets the start and end key of a composite query.

    Args:
      query: A datastore_pb.Query object.
      filter_info: A dictionary mapping property names to tuples of filter
        operators and values.
      composite_index: An entity_pb.CompositeIndex object.
    Returns:
      A tuple of strings, the start and end key for the composite table.
    """
    index_id = composite_index.id()
    definition = composite_index.definition()
    app_id = clean_app_id(query.app())
    name_space = ''
    if query.has_name_space():
      name_space = query.name_space()
    # Calculate the prekey for both the start and end key.
    pre_comp_index_key = "{0}{1}{2}{4}{3}{4}".format(app_id,
      self._NAMESPACE_SEPARATOR, name_space, index_id, self._SEPARATOR)

    if definition.ancestor() == 1:
      ancestor_str = encode_index_pb(query.ancestor().path())
      pre_comp_index_key += "{0}{1}".format(ancestor_str, self._SEPARATOR)

    value = ''
    index_value = ""
    equality_value = ""
    direction = datastore_pb.Query_Order.ASCENDING
    for prop in definition.property_list():
      # Choose the least restrictive operation by default.
      oper = datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL

      # The last property dictates the direction.
      if prop.has_direction():
        direction = prop.direction()
      # We loop through the definition list and remove the filters we've seen
      # before if they are equality or exists.
      all_filter_ops = [ii[0] for ii in filter_info.get(prop.name(), [])]
      if not all_filter_ops:
        continue

      if datastore_pb.Query_Filter.EQUAL in all_filter_ops:
        filters = filter_info.get(prop.name())
        index_used = 0
        for index, filt in enumerate(filters):
          if filt[0] == datastore_pb.Query_Filter.EQUAL:
            index_used = index
            break

        filter_to_use = filters.pop(index_used)

        value = str(filter_to_use[1])
        if prop.direction() == entity_pb.Index_Property.DESCENDING:
          value = helper_functions.reverse_lex(value)
        equality_value += str(value) + self._SEPARATOR
        oper = filter_to_use[0]
        index_value += str(value) + self._SEPARATOR

      elif datastore_pb.Query_Filter.EXISTS in all_filter_ops:
        # Exists filters do not add to the index value. They are just
        # placeholders.
        filters = filter_info.get(prop.name())
        index_used = 0
        for index, filt in enumerate(filters):
          if filt[0] == datastore_pb.Query_Filter.EXISTS:
            index_used = index
            break

        filters.pop(index_used)
      else:
        filters = filter_info.get(prop.name())
        if len(filters) > 1:
          return self.composite_multiple_filter_prop(
            filter_info[prop.name()], equality_value, pre_comp_index_key,
            prop.direction())
        else:
          value = str(filters[0][1])
          oper = filters[0][0]
          if prop.direction() == entity_pb.Index_Property.DESCENDING:
            value = helper_functions.reverse_lex(value)
        index_value += str(value) + self._SEPARATOR

    start_value = ''
    end_value = ''
    if oper == datastore_pb.Query_Filter.LESS_THAN:
      start_value = equality_value
      end_value = index_value
      if direction == datastore_pb.Query_Order.DESCENDING:
        start_value = index_value + self._TERM_STRING
        end_value = equality_value + self._TERM_STRING
    elif oper == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
      start_value = equality_value
      end_value = index_value + self._TERM_STRING
      if direction == datastore_pb.Query_Order.DESCENDING:
        start_value = index_value
        end_value = equality_value + self._TERM_STRING
    elif oper == datastore_pb.Query_Filter.GREATER_THAN:
      start_value = index_value + self._TERM_STRING
      end_value = equality_value + self._TERM_STRING
      if direction == datastore_pb.Query_Order.DESCENDING:
        start_value = equality_value + self.MIN_INDEX_VALUE
        end_value = index_value + self._SEPARATOR
    elif oper == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
      start_value = index_value
      end_value = equality_value + self._TERM_STRING
      if direction == datastore_pb.Query_Order.DESCENDING:
        start_value = equality_value
        end_value = index_value + self._TERM_STRING
    elif oper == datastore_pb.Query_Filter.EQUAL:
      if value == "":
        start_value = index_value
        end_value = index_value + self.MIN_INDEX_VALUE + self._TERM_STRING
      else:
        start_value = index_value
        end_value = index_value + self._TERM_STRING
    else:
      raise ValueError("Unsuported operator {0} for composite query".\
        format(oper))
    start_key = "{0}{1}".format(pre_comp_index_key, start_value)
    end_key = "{0}{1}".format(pre_comp_index_key, end_value)

    return start_key, end_key

  def composite_multiple_filter_prop(self, filter_ops, equality_value,
    pre_comp_index_key, direction):
    """Returns the start and end keys for a composite query which has multiple
       filters for a single property, and potentially multiple equality
       filters.

    Args:
      filter_ops: dictionary mapping the inequality filter to operators and
        values.
      equality_value: A string used for the start and end key which is derived
        from equality filter values.
      pre_comp_index_key: A string, contains pre-values for start and end keys.
      direction: datastore_pb.Query_Order telling the direction of the scan.
    Returns:
      The end and start key for doing a composite query.
    """
    oper1 = None
    oper2 = None
    value1 = None
    value2 = None
    start_key = ""
    end_key = ""
    if filter_ops[0][0] == datastore_pb.Query_Filter.GREATER_THAN or \
      filter_ops[0][0] == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
      oper1 = filter_ops[0][0]
      oper2 = filter_ops[1][0]
      value1 = str(filter_ops[0][1])
      value2 = str(filter_ops[1][1])
    else:
      oper1 = filter_ops[1][0]
      oper2 = filter_ops[0][0]
      value1 = str(filter_ops[1][1])
      value2 = str(filter_ops[0][1])

    if direction == datastore_pb.Query_Order.ASCENDING:
      # The first operator will always be either > or >=.
      if oper1 == datastore_pb.Query_Filter.GREATER_THAN:
        start_value = equality_value + value1 + self._SEPARATOR + \
          self._TERM_STRING
      elif oper1 == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
        start_value = equality_value + value1
      else:
        raise dbconstants.AppScaleMisconfiguredQuery("Bad filter ordering")

      # The second operator will be either < or <=.
      if oper2 == datastore_pb.Query_Filter.LESS_THAN:
        end_value = equality_value + value2
      elif oper2 == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
        end_value = equality_value + value2 + self._SEPARATOR + \
          self._TERM_STRING
      else:
        raise dbconstants.AppScaleMisconfiguredQuery("Bad filter ordering")

    if direction == datastore_pb.Query_Order.DESCENDING:
      value1 = helper_functions.reverse_lex(value1)
      value2 = helper_functions.reverse_lex(value2)
      if oper1 == datastore_pb.Query_Filter.GREATER_THAN:
        end_value = equality_value + value1
      elif oper1 == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
        end_value = equality_value + value1 + self._SEPARATOR + \
          self._TERM_STRING
      else:
        raise dbconstants.AppScaleMisconfiguredQuery("Bad filter ordering")

      if oper2 == datastore_pb.Query_Filter.LESS_THAN:
        start_value = equality_value + value2 + self._SEPARATOR + \
          self._TERM_STRING
      elif oper2 == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
        start_value = equality_value + value2
      else:
        raise dbconstants.AppScaleMisconfiguredQuery("Bad filter ordering")

    start_key = "{0}{1}".format(pre_comp_index_key, start_value)
    end_key = "{0}{1}".format(pre_comp_index_key, end_value)

    return start_key, end_key

  @gen.coroutine
  def composite_v2(self, query, filter_info, composite_index):
    """Performs composite queries using a range query against
       the composite table. Faster than in-memory filters, but requires
       indexes to be built upon each put.

    Args:
      query: The query to run.
      filter_info: dictionary mapping property names to tuples of
        filter operators and values.
      composite_index: An entity_pb.CompositeIndex object to use for the query.
    Returns:
      A tuple containing a list of entities retrieved from the given query and
      a boolean indicating if there are more results for the query.
    """
    self.logger.debug('Composite Query:\n{}'.format(query))

    if composite_index.state() != entity_pb.CompositeIndex.READ_WRITE:
      raise dbconstants.NeedsIndex(
        'The relevant composite index has not finished building')

    start_inclusive = True
    startrow, endrow = self.get_range_composite_query(query, filter_info,
                                                      composite_index)
    # Override the start_key with a cursor if given.
    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
      cursor = appscale_stub_util.ListCursor(query)
      last_result = cursor._GetLastResult()

      startrow = self.get_composite_index_key(composite_index, last_result,
        position_list=query.compiled_cursor().position_list(),
        filters=query.filter_list())
      start_inclusive = False
      if query.compiled_cursor().position_list()[0].start_inclusive() == 1:
        start_inclusive = True

    if query.has_end_compiled_cursor():
      end_compiled_cursor = query.end_compiled_cursor()
      list_cursor = appscale_stub_util.ListCursor(query)
      last_result, _ = list_cursor._DecodeCompiledCursor(end_compiled_cursor)
      endrow = self.get_composite_index_key(composite_index, last_result,
        position_list=end_compiled_cursor.position_list(),
        filters=query.filter_list())

    table_name = dbconstants.COMPOSITE_TABLE
    column_names = dbconstants.COMPOSITE_SCHEMA

    more_results = False
    request_limit, check_more_results = self.get_limit(query)
    fetch_count = request_limit
    if check_more_results:
      fetch_count += 1

    if startrow > endrow:
      raise gen.Return(([], more_results))

    # TODO: Check if we should do this for other comparisons.
    multiple_equality_filters = self.__get_multiple_equality_filters(
      query.filter_list())

    entities = []
    current_limit = fetch_count
    while True:
      references = yield self.datastore_batch.range_query(
        table_name, column_names, startrow, endrow, current_limit,
        offset=0, start_inclusive=start_inclusive, end_inclusive=True)

      # This is a projection query.
      if query.property_name_size() > 0:
        potential_entities = self._extract_entities_from_composite_indexes(
          query, references, composite_index)
      else:
        potential_entities = yield self.__fetch_entities(references)

      if len(multiple_equality_filters) > 0:
        self.logger.debug('Detected multiple equality filters on a repeated '
          'property. Removing results that do not match query.')
        potential_entities = self.__apply_multiple_equality_filters(
          potential_entities, multiple_equality_filters)

      entities.extend(potential_entities)

      # If we have enough valid entities to satisfy the query, we're done.
      if len(entities) >= fetch_count:
        break

      # If we received fewer references than we asked for, they are exhausted.
      if len(references) < current_limit:
        break

      # If all of the references that we fetched were valid, we're done.
      if len(potential_entities) == len(references):
        break

      invalid_refs = len(references) - len(potential_entities)

      # Pad the limit to increase the likelihood of fetching all the valid
      # references that we need.
      current_limit = invalid_refs + dbconstants.MAX_GROUPS_FOR_XG

      self.logger.debug('{} entities do not match query. '
        'Fetching {} more references.'.format(invalid_refs, current_limit))

      last_startrow = startrow
      # Start from the last reference fetched.
      startrow = references[-1].keys()[0]

      if startrow == last_startrow:
        raise dbconstants.AppScaleDBError(
          'An infinite loop was detected while fetching references.')

    if check_more_results and len(entities) > request_limit:
      more_results = True

    results = entities[:request_limit]
    self.logger.debug('Returning {} results'.format(len(results)))
    raise gen.Return((results, more_results))

  def __get_multiple_equality_filters(self, filter_list):
    """ Returns filters from the query that contain multiple equality
      comparisons on repeated properties.

    Args:
      filter_list: A list of filters from the query.
    Returns:
      A dictionary that contains properties with multiple equality filters.
    """
    equality_filters = {}
    for query_filter in filter_list:
      if query_filter.op() != datastore_pb.Query_Filter.EQUAL:
        continue

      for prop in query_filter.property_list():
        if prop.name() not in equality_filters:
          equality_filters[prop.name()] = []

        equality_filters[prop.name()].append(prop)

    single_eq_filters = []
    for prop in equality_filters:
      if len(equality_filters[prop]) < 2:
        single_eq_filters.append(prop)
    for prop in single_eq_filters:
      del equality_filters[prop]

    return equality_filters

  def __apply_multiple_equality_filters(self, entities, filter_dict):
    """ Removes entities that do not meet the criteria defined by multiple
      equality filters.

    Args:
      entities: A list of entities that need filtering.
      filter_dict: A dictionary containing the relevant filters.
    Returns:
      A list of filtered entities.
    """
    filtered_entities = []
    for entity in entities:
      entity_proto = entity_pb.EntityProto(entity)

      relevant_props_in_entity = {}
      for entity_prop in entity_proto.property_list():
        if entity_prop.name() not in filter_dict:
          continue

        if entity_prop.name() not in relevant_props_in_entity:
          relevant_props_in_entity[entity_prop.name()] = []

        relevant_props_in_entity[entity_prop.name()].append(entity_prop)

      passes_all_filters = True
      for filter_prop_name in filter_dict:
        if filter_prop_name not in relevant_props_in_entity:
          raise dbconstants.AppScaleDBError(
            'Property name not found in entity.')

        filter_props = filter_dict[filter_prop_name]
        entity_props = relevant_props_in_entity[filter_prop_name]

        for filter_prop in filter_props:
          # Check if filter value is in repeated property.
          passes_filter = False
          for entity_prop in entity_props:
            if entity_prop.value().Equals(filter_prop.value()):
              passes_filter = True
              break

          if not passes_filter:
            passes_all_filters = False
            break

        if not passes_all_filters:
          break

      if passes_all_filters:
        filtered_entities.append(entity)

    return filtered_entities

  def __extract_value_from_index(self, index_entry, direction):
    """ Takes an index entry and returns the value of the property.

    This function is for single property indexes only.

    Args:
      index_entry: A dictionary containing an index entry.
      direction: The direction of the index.
    Returns:
      A property value.
    """
    reference_key = index_entry.keys()[0]
    tokens = reference_key.split(self._SEPARATOR)

    # Sometimes the value can contain the separator.
    value = self._SEPARATOR.join(tokens[4:-1])

    if direction == datastore_pb.Query_Order.DESCENDING:
      value = helper_functions.reverse_lex(value)

    entity = entity_pb.EntityProto()
    prop = entity.add_property()
    prop_value = prop.mutable_value()
    self.__decode_index_str(value, prop_value)

    return prop_value

  def __valid_index_entry(self, entry, entities, direction, prop_name):
    """ Checks if an index entry is valid.

    Args:
      entry: A dictionary containing an index entry.
      entities: A dictionary of available valid entities.
      direction: The direction of the index.
      prop_name: A string containing the property name.
    Returns:
      A boolean indicating whether or not the entry is valid.
    Raises:
      AppScaleDBError: The given property name is not in the matching entity.
    """
    # Skip validating reserved properties.
    if dbconstants.RESERVED_PROPERTY_NAME.match(prop_name):
      return True

    reference = entry[entry.keys()[0]]['reference']

    # Reference may be absent from entities if the entity was deleted or part
    # of an invalid transaction.
    if reference not in entities:
      return False

    index_value = self.__extract_value_from_index(entry, direction)

    entity = entities[reference]
    entity_proto = entity_pb.EntityProto(entity)

    # TODO: Return faster if not a repeated property.
    prop_found = False
    for prop in entity_proto.property_list():
      if prop.name() != prop_name:
        continue
      prop_found = True

      if index_value.has_uservalue() and prop.value().has_uservalue():
        if index_value.uservalue().email() == prop.value().uservalue().email():
          return True

      if index_value.Equals(prop.value()):
        return True

    if not prop_found:
      # Most likely, a repeated property was populated and then emptied.
      self.logger.debug('Property name {} not found in entity.'.
        format(prop_name))

    return False

  def remove_extra_props(self, query, results):
    """ Decodes entities, strips extra properties, and re-encodes them.

    Args:
      query: A datastore_pb.Query object.
      results: A list of encoded entities.
    Returns:
      A list of encoded entities.
    """
    projected_props = query.property_name_list()

    cleaned_results = []
    for result in results:
      entity = entity_pb.EntityProto(result)
      props_to_keep = [prop for prop in entity.property_list()
                       if prop.name() in projected_props]

      # If the entity does not have the property, do not include it in the
      # results. Raw (unindexed) properties should not be projected.
      if not props_to_keep:
        continue

      entity.clear_property()
      for prop in props_to_keep:
        # Projected properties should have a meaning set to INDEX_VALUE.
        prop.set_meaning(entity_pb.Property.INDEX_VALUE)
        new_prop = entity.add_property()
        new_prop.MergeFrom(prop)

      cleaned_results.append(entity.Encode())

    return cleaned_results

  def _extract_entities_from_composite_indexes(self, query, index_result,
                                               composite_index):
    """ Takes index values and creates partial entities out of them.

    This is required for projection queries where the query specifies certain
    properties which should be returned. Distinct queries are also handled here.
    A distinct query removes entities with duplicate index values. This will
    only return the first result for entities which have the same values for
    the properties that are being projected.

    Args:
      query: A datastore_pb.Query object.
      index_result: A list of index strings.
      composite_index: An entity_pb.CompositeIndex object.
    Returns:
      A list of EntityProtos.
    """
    definition = composite_index.definition()
    prop_name_list = query.property_name_list()

    distinct_checker = []
    entities = []
    for index in index_result:
      entity = entity_pb.EntityProto()
      tokens = index.keys()[0].split(self._SEPARATOR)
      app_id = tokens.pop(0)
      namespace = tokens.pop(0)
      comp_definition_id = tokens.pop(0)
      if definition.ancestor() == 1:
        ancestor = tokens.pop(0)[:-1]
      distinct_str = ""
      value_index = 0
      for def_prop in definition.property_list():
        # If the value contained the separator, try to recover the value.
        if len(tokens[:-1]) > len(definition.property_list()):
          end_slice = value_index + 1
          while end_slice <= len(tokens[:-1]):
            value = self._SEPARATOR.join(tokens[value_index:end_slice])
            if def_prop.direction() == entity_pb.Index_Property.DESCENDING:
              value = helper_functions.reverse_lex(value)
            prop_value = entity_pb.PropertyValue()
            try:
              self.__decode_index_str(value, prop_value)
              value_index = end_slice
              break
            except ProtocolBufferDecodeError:
              end_slice += 1
        else:
          value = tokens[value_index]
          if def_prop.direction() == entity_pb.Index_Property.DESCENDING:
            value = helper_functions.reverse_lex(value)
          value_index += 1

        if def_prop.name() not in prop_name_list:
          self.logger.debug('Skipping prop {} in projection'.
            format(def_prop.name()))
          continue

        prop = entity.add_property()
        prop.set_name(def_prop.name())
        prop.set_meaning(entity_pb.Property.INDEX_VALUE)
        prop.set_multiple(False)

        distinct_str += value
        prop_value = prop.mutable_value()
        self.__decode_index_str(value, prop_value)

      key_string = tokens[-1]
      path = decode_path(key_string)

      # Set the entity group.
      ent_group = entity.mutable_entity_group()
      new_element = ent_group.add_element()
      new_element.MergeFrom(path.element(0))

      # Set the key path.
      key = entity.mutable_key()
      key.set_app(clean_app_id(app_id))
      if namespace:
        key.set_name_space(namespace)

      key.mutable_path().MergeFrom(path)

      # Filter entities if this is a distinct query.
      if query.group_by_property_name_size() == 0:
        entities.append(entity.Encode())
      elif distinct_str not in distinct_checker:
        entities.append(entity.Encode())

      distinct_checker.append(distinct_str)
    return entities

  # These are the three different types of queries attempted. Queries
  # can be identified by their filters and orderings.
  # TODO: Queries have hints which help in picking which strategy to do first.
  _QUERY_STRATEGIES = [
      __single_property_query,
      __kind_query,
      zigzag_merge_join,
  ]

  @gen.coroutine
  def __get_query_results(self, query):
    """Applies the strategy for the provided query.

    Args:
      query: A datastore_pb.Query protocol buffer.
    Returns:
      Result set.
    """
    if query.has_transaction() and not query.has_ancestor():
      raise apiproxy_errors.ApplicationError(
          datastore_pb.Error.BAD_REQUEST,
          'Only ancestor queries are allowed inside transactions.')

    num_components = len(query.filter_list()) + len(query.order_list())
    if query.has_ancestor():
      num_components += 1
    if num_components > self._MAX_QUERY_COMPONENTS:
      raise apiproxy_errors.ApplicationError(
          datastore_pb.Error.BAD_REQUEST,
          ('query is too large. may not have more than {0} filters'
           ' + sort orders ancestor total'.format(self._MAX_QUERY_COMPONENTS)))

    for prop_name in query.property_name_list():
      if dbconstants.RESERVED_PROPERTY_NAME.match(prop_name):
        raise dbconstants.BadRequest('projections are not supported for the '
                                     'property: {}'.format(prop_name))

    app_id = clean_app_id(query.app())

    self.validate_app_id(app_id)
    filters, orders = datastore_index.Normalize(query.filter_list(),
                                                query.order_list(), [])
    filter_info = self.generate_filter_info(filters)
    order_info = self.generate_order_info(orders)

    index_to_use = _FindIndexToUse(query, self.get_indexes(app_id))
    if index_to_use is not None:
      result, more_results = yield self.composite_v2(query, filter_info,
                                                     index_to_use)
      raise gen.Return((result, more_results))

    for strategy in DatastoreDistributed._QUERY_STRATEGIES:
      results, more_results = yield strategy(self, query, filter_info,
                                             order_info)
      if results or results == []:
        raise gen.Return((results, more_results))

    raise dbconstants.NeedsIndex(
      'An additional index is required to satisfy the query')

  @gen.coroutine
  def _dynamic_run_query(self, query, query_result):
    """Populates the query result and use that query result to
       encode a cursor.

    Args:
      query: The query to run.
      query_result: The response given to the application server.
    """
    result, more_results = yield self.__get_query_results(query)
    last_entity = None
    count = 0
    offset = query.offset()
    if result:
      query_result.set_skipped_results(len(result) - offset)
      # Last entity is used for the cursor. It needs to be set before
      # applying the offset.
      last_entity = result[-1]
      count = len(result)
      result = result[offset:]
      if query.has_limit():
        result = result[:query.limit()]

    cur = UnprocessedQueryCursor(query, result, last_entity)
    cur.PopulateQueryResult(count, query.offset(), query_result)

    query_result.set_more_results(more_results)

    # If there were no results then we copy the last cursor so future queries
    # can start off from the same place.
    if query.has_compiled_cursor() and not query_result.has_compiled_cursor():
      query_result.mutable_compiled_cursor().CopyFrom(query.compiled_cursor())
    elif query.has_compile() and not query_result.has_compiled_cursor():
      query_result.mutable_compiled_cursor().\
        CopyFrom(datastore_pb.CompiledCursor())

  @gen.coroutine
  def dynamic_add_actions(self, app_id, request, service_id, version_id):
    """ Adds tasks to enqueue upon committing the transaction.

    Args:
      app_id: A string specifying the application ID.
      request: A protocol buffer AddActions request.
      service_id: A string specifying the client's service ID.
      version_id: A string specifying the client's version ID.
    """
    txid = request.add_request(0).transaction().handle()

    # Check if the tasks will exceed the limit. Though this method shouldn't
    # be called concurrently for a given transaction under normal
    # circumstances, this CAS should eventually be done under a lock.
    existing_tasks = yield self.datastore_batch.transactional_tasks_count(
      app_id, txid)
    if existing_tasks > _MAX_ACTIONS_PER_TXN:
      message = 'Only {} tasks can be added to a transaction'.\
        format(_MAX_ACTIONS_PER_TXN)
      raise dbconstants.ExcessiveTasks(message)

    yield self.datastore_batch.add_transactional_tasks(
      app_id, txid, request.add_request_list(), service_id, version_id)

  @gen.coroutine
  def setup_transaction(self, app_id, is_xg):
    """ Gets a transaction ID for a new transaction.

    Args:
      app_id: The application for which we are getting a new transaction ID.
      is_xg: A bool that indicates if this transaction operates over multiple
        entity groups.
    Returns:
      A long representing a unique transaction ID.
    """
    txid = self.transaction_manager.create_transaction_id(app_id, xg=is_xg)
    in_progress = self.transaction_manager.get_open_transactions(app_id)
    yield self.datastore_batch.start_transaction(
      app_id, txid, is_xg, in_progress)
    raise gen.Return(txid)

  @gen.coroutine
  def enqueue_transactional_tasks(self, app, tasks):
    """ Send a BulkAdd request to the taskqueue service.

    Args:
      app: A string specifying an application ID.
      task_ops: A list of tasks.
    """
    # Assume all tasks have the same client version.
    service_id = tasks[0]['service_id']
    version_id = tasks[0]['version_id']

    add_requests = [task['task'] for task in tasks]
    self.logger.debug('Enqueuing {} tasks'.format(len(add_requests)))

    # The transaction has already been committed, but enqueuing the tasks may
    # fail. We need a way to enqueue the task with the condition that it
    # executes only upon successful commit. For now, we just log the error.
    try:
      yield self.taskqueue_client.add_tasks(app, service_id, version_id,
                                            add_requests)
    except EnqueueError as error:
      self.logger.error('Unable to enqueue tasks: {}'.format(error))

  @gen.coroutine
  def apply_txn_changes(self, app, txn):
    """ Apply all operations in transaction table in a single batch.

    Args:
      app: A string containing an application ID.
      txn: An integer specifying a transaction ID.
    """
    metadata = yield self.datastore_batch.get_transaction_metadata(app, txn)

    # If too much time has passed, the transaction cannot be committed.
    if 'start' not in metadata:
      raise dbconstants.BadRequest('Unable to find transaction')

    tx_duration = datetime.datetime.utcnow() - metadata['start']
    if (tx_duration > datetime.timedelta(seconds=MAX_TX_DURATION)):
      raise dbconstants.BadRequest('The referenced transaction has expired')

    # If there were no changes, the transaction is complete.
    if (len(metadata['puts']) + len(metadata['deletes']) +
        len(metadata['tasks']) == 0):
      return

    # Fail if there are too many groups involved in the transaction.
    groups_put = {group_for_key(key).Encode() for key in metadata['puts']}
    groups_deleted = {group_for_key(key).Encode()
                      for key in metadata['deletes']}
    groups_mutated = groups_put | groups_deleted
    tx_groups = groups_mutated | metadata['reads']
    if len(tx_groups) > dbconstants.MAX_GROUPS_FOR_XG:
      raise dbconstants.TooManyGroupsException(
        'Too many groups in transaction')

    composite_indices = self.get_indexes(app)
    decoded_groups = [entity_pb.Reference(group) for group in tx_groups]
    self.transaction_manager.set_groups(app, txn, decoded_groups)

    # Allow the lock to stick around if there is an issue applying the batch.
    lock = entity_lock.EntityLock(self.zookeeper.handle, decoded_groups, txn)
    try:
      yield lock.acquire()
    except entity_lock.LockTimeout:
      raise Timeout('Unable to acquire entity group locks')

    try:
      try:
        group_txids = yield self.datastore_batch.group_updates(
          metadata['reads'])
      except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
        lock.release()
        self.transaction_manager.delete_transaction_id(app, txn)
        raise dbconstants.AppScaleDBConnectionError(
          'Unable to fetch group updates')

      for group_txid in group_txids:
        if group_txid in metadata['in_progress'] or group_txid > txn:
          lock.release()
          self.transaction_manager.delete_transaction_id(app, txn)
          raise dbconstants.ConcurrentModificationException(
            'A group was modified after this transaction was started.')

      # Fetch current values so we can remove old indices.
      entity_table_keys = [encode_entity_table_key(key)
                           for key, _ in metadata['puts'].iteritems()]
      entity_table_keys.extend([encode_entity_table_key(key)
                                for key in metadata['deletes']])
      try:
        current_values = yield self.datastore_batch.batch_get_entity(
          dbconstants.APP_ENTITY_TABLE, entity_table_keys, APP_ENTITY_SCHEMA)
      except dbconstants.AppScaleDBConnectionError:
        lock.release()
        self.transaction_manager.delete_transaction_id(app, txn)
        raise

      batch = []
      entity_changes = []
      for encoded_key, encoded_entity in metadata['puts'].iteritems():
        key = entity_pb.Reference(encoded_key)
        entity_table_key = encode_entity_table_key(key)
        current_value = None
        if current_values[entity_table_key]:
          current_value = entity_pb.EntityProto(
            current_values[entity_table_key][APP_ENTITY_SCHEMA[0]])

        entity = entity_pb.EntityProto(encoded_entity)
        mutations = mutations_for_entity(entity, txn, current_value,
                                         composite_indices)
        batch.extend(mutations)

        entity_changes.append({'key': key, 'old': current_value,
                               'new': entity})

      for key in metadata['deletes']:
        entity_table_key = encode_entity_table_key(key)
        if not current_values[entity_table_key]:
          continue

        current_value = entity_pb.EntityProto(
          current_values[entity_table_key][APP_ENTITY_SCHEMA[0]])

        deletions = deletions_for_entity(current_value, composite_indices)
        batch.extend(deletions)

        entity_changes.append({'key': key, 'old': current_value, 'new': None})

      for group in groups_mutated:
        batch.append(
          {'table': 'group_updates', 'key': bytearray(group),
           'last_update': txn})

      if batch_size(batch) > LARGE_BATCH_THRESHOLD:
        try:
          yield self.datastore_batch.large_batch(app, batch, entity_changes,
                                                 txn)
        except BatchNotApplied as error:
          # If the "applied" switch has not been flipped, the lock can be
          # released. The transaction ID is kept so that the groomer can
          # clean up the batch tables.
          lock.release()
          raise dbconstants.AppScaleDBConnectionError(str(error))
      else:
        try:
          yield self.datastore_batch.normal_batch(batch, txn)
        except dbconstants.AppScaleDBConnectionError:
          # Since normal batches are guaranteed to be atomic, the lock can
          # be released.
          lock.release()
          self.transaction_manager.delete_transaction_id(app, txn)
          raise

      lock.release()

    finally:
      # In case of failure entity group lock should stay acquired
      # as transaction groomer will handle it later.
      # But tornado lock must be released.
      lock.ensure_release_tornado_lock()

    self.transaction_manager.delete_transaction_id(app, txn)

    # Process transactional tasks.
    if metadata['tasks']:
      IOLoop.current().spawn_callback(self.enqueue_transactional_tasks, app,
                                      metadata['tasks'])

  def rollback_transaction(self, app_id, txid):
    """ Handles the rollback phase of a transaction.

    Args:
      app_id: The application ID requesting the rollback.
      txid: An integer specifying a transaction ID.
    Raises:
      InternalError if unable to roll back transaction.
    """
    self.logger.info(
      'Doing a rollback on transaction {} for {}'.format(txid, app_id))
    try:
      self.zookeeper.notify_failed_transaction(app_id, txid)
    except zktransaction.ZKTransactionException as error:
      raise InternalError(str(error))

  def get_indexes(self, project_id):
    """ Retrieves list of indexes for a project.

    Args:
      project_id: A string specifying a project ID.
    Returns:
      A list of entity_pb.CompositeIndex objects.
    Raises:
      BadRequest if project_id is not found.
      InternalError if ZooKeeper is not accessible.
    """
    try:
      project_index_manager = self.index_manager.projects[project_id]
    except KeyError:
      raise BadRequest('project_id: {} not found'.format(project_id))

    try:
      indexes = project_index_manager.indexes_pb
    except IndexInaccessible:
      raise InternalError('ZooKeeper is not accessible')

    return indexes

  def _zk_state_listener(self, state):
    """ Handles changes to the ZooKeeper connection state.

    Args:
      state: A string specifying the new connection state.
    """
    # Discard any allocated blocks if disconnected from ZooKeeper.
    if state in [KazooState.LOST, KazooState.SUSPENDED]:
      self.scattered_allocators.clear()
