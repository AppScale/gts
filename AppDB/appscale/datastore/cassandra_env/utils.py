""" Helper functions for the Cassandra datastore implementation. """
from .. import dbconstants
from .. import helper_functions
from ..dbconstants import Operations
from ..utils import (
  clean_app_id,
  encode_index_pb,
  get_composite_index_keys,
  get_composite_indexes_rows,
  get_entity_key,
  get_entity_kind,
  get_index_kv_from_tuple,
  get_kind_key
)


def deletions_for_entity(entity, composite_indices=()):
  """ Get a list of deletions needed across tables for deleting an entity.

  Args:
    entity: An entity object.
    composite_indices: A list or tuple of composite indices.
  Returns:
    A list of dictionaries representing mutation operations.
  """
  deletions = []
  app_id = clean_app_id(entity.key().app())
  namespace = entity.key().name_space()
  prefix = dbconstants.KEY_DELIMITER.join([app_id, namespace])

  asc_rows = get_index_kv_from_tuple([(prefix, entity)])
  for entry in asc_rows:
    deletions.append({'table': dbconstants.ASC_PROPERTY_TABLE,
                      'key': entry[0],
                      'operation': Operations.DELETE})

  dsc_rows = get_index_kv_from_tuple(
    [(prefix, entity)], reverse=True)
  for entry in dsc_rows:
    deletions.append({'table': dbconstants.DSC_PROPERTY_TABLE,
                      'key': entry[0],
                      'operation': Operations.DELETE})

  for key in get_composite_indexes_rows([entity], composite_indices):
    deletions.append({'table': dbconstants.COMPOSITE_TABLE,
                      'key': key,
                      'operation': Operations.DELETE})

  entity_key = get_entity_key(prefix, entity.key().path())
  deletions.append({'table': dbconstants.APP_ENTITY_TABLE,
                    'key': entity_key,
                    'operation': Operations.DELETE})

  kind_key = get_kind_key(prefix, entity.key().path())
  deletions.append({'table': dbconstants.APP_KIND_TABLE,
                    'key': kind_key,
                    'operation': Operations.DELETE})

  return deletions


def index_deletions(old_entity, new_entity, composite_indices=()):
  """ Get a list of index deletions needed for updating an entity. For changing
  an existing entity, this involves examining the property list of both
  entities to see which index entries need to be removed.

  Args:
    old_entity: An entity object.
    new_entity: An entity object.
    composite_indices: A list or tuple of composite indices.
  Returns:
    A list of dictionaries representing mutation operations.
  """
  deletions = []
  app_id = clean_app_id(old_entity.key().app())
  namespace = old_entity.key().name_space()
  kind = get_entity_kind(old_entity.key())
  entity_key = str(encode_index_pb(old_entity.key().path()))

  new_props = {}
  for prop in new_entity.property_list():
    if prop.name() not in new_props:
      new_props[prop.name()] = []
    new_props[prop.name()].append(prop)

  changed_props = {}
  for prop in old_entity.property_list():
    if prop.name() in new_props and prop in new_props[prop.name()]:
      continue

    if prop.name() not in changed_props:
      changed_props[prop.name()] = []
    changed_props[prop.name()].append(prop)

    value = str(encode_index_pb(prop.value()))

    key = dbconstants.KEY_DELIMITER.join(
      [app_id, namespace, kind, prop.name(), value, entity_key])
    deletions.append({'table': dbconstants.ASC_PROPERTY_TABLE,
                      'key': key,
                      'operation': Operations.DELETE})

    reverse_key = dbconstants.KEY_DELIMITER.join(
      [app_id, namespace, kind, prop.name(),
       helper_functions.reverse_lex(value), entity_key])
    deletions.append({'table': dbconstants.DSC_PROPERTY_TABLE,
                      'key': reverse_key,
                      'operation': Operations.DELETE})

  changed_prop_names = set(changed_props.keys())
  for index in composite_indices:
    if index.definition().entity_type() != kind:
      continue

    index_props = set(prop.name() for prop
                      in index.definition().property_list())
    if index_props.isdisjoint(changed_prop_names):
      continue

    old_entries = set(get_composite_index_keys(index, old_entity))
    new_entries = set(get_composite_index_keys(index, new_entity))
    for entry in (old_entries - new_entries):
      deletions.append({'table': dbconstants.COMPOSITE_TABLE,
                        'key': entry,
                        'operation': Operations.DELETE})

  return deletions


def mutations_for_entity(entity, txn, current_value=None,
                         composite_indices=()):
  """ Get a list of mutations needed across tables for an entity change.

  Args:
    entity: An entity object.
    txn: A transaction ID handler.
    current_value: The entity object currently stored.
    composite_indices: A list of composite indices for the entity kind.
  Returns:
    A list of dictionaries representing mutations.
  """
  mutations = []
  if current_value is not None:
    mutations.extend(
      index_deletions(current_value, entity, composite_indices))

  app_id = clean_app_id(entity.key().app())
  namespace = entity.key().name_space()
  encoded_path = str(encode_index_pb(entity.key().path()))
  prefix = dbconstants.KEY_DELIMITER.join([app_id, namespace])
  entity_key = dbconstants.KEY_DELIMITER.join([prefix, encoded_path])
  entity_value = {dbconstants.APP_ENTITY_SCHEMA[0]: entity.Encode(),
                  dbconstants.APP_ENTITY_SCHEMA[1]: str(txn)}
  mutations.append({'table': dbconstants.APP_ENTITY_TABLE,
                    'key': entity_key,
                    'operation': Operations.PUT,
                    'values': entity_value})

  reference_value = {'reference': entity_key}

  kind_key = get_kind_key(prefix, entity.key().path())
  mutations.append({'table': dbconstants.APP_KIND_TABLE,
                    'key': kind_key,
                    'operation': Operations.PUT,
                    'values': reference_value})

  asc_rows = get_index_kv_from_tuple([(prefix, entity)])
  for entry in asc_rows:
    mutations.append({'table': dbconstants.ASC_PROPERTY_TABLE,
                      'key': entry[0],
                      'operation': Operations.PUT,
                      'values': reference_value})

  dsc_rows = get_index_kv_from_tuple([(prefix, entity)], reverse=True)
  for entry in dsc_rows:
    mutations.append({'table': dbconstants.DSC_PROPERTY_TABLE,
                      'key': entry[0],
                      'operation': Operations.PUT,
                      'values': reference_value})

  for key in get_composite_indexes_rows([entity], composite_indices):
    mutations.append({'table': dbconstants.COMPOSITE_TABLE,
                      'key': key,
                      'operation': Operations.PUT,
                      'values': reference_value})

  return mutations
