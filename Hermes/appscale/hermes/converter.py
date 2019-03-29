"""
This module holds functionality related to conversion of stats entities
to dictionaries (JSON serializable) and lists (CSV rows).
It also provides function for building stats entities from dictionaries.
"""
import collections

import attr

from appscale.hermes.constants import MISSED


class WrongIncludeLists(ValueError):
  """ Is raised when unknown fields are passed to IncludeLists.__init__. """
  pass


class ConflictingIncludeListName(ValueError):
  """ Is raised when a name is used twice with @include_list_name decorator. """
  pass


def include_list_name(name):
  """ Class decorator. It is used for stats model classes.
  Decorated class will be registered to IncludeLists, so when you
  convert your stats model to dict and list you'll be able to specify
  list of fields to include."""
  def decorator(cls):
    if not attr.has(cls):
      raise attr.exceptions.NotAnAttrsClassError(
        'Include list feature works with attr.s classes only'
      )
    cls._include_list_name = name
    IncludeLists.register(name, cls)
    return cls
  return decorator


class Meta(object):
  """
  Constants used as metadata keys for attr.ib().
  E.g.: processes_stats = attr.ib(metadata={Meta.NESTED_LIST: ProcessStats})
  """
  ENTITY = 'entity'
  ENTITY_DICT = 'dict'
  ENTITY_LIST = 'list'


class IncludeLists(object):
  """
  An instance of this class can list attributes which should be included
  when rendering stats entity.
  It knows all available attributes for each class decorated by
  @include_list_name(name).
  An instance of IncludeLists can be created from dictionary like:
  {
    'process': ['monit_name', 'unified_service_name', 'application_id',
                'port', 'cpu', 'memory', 'children_stats_sum'],
    'process.cpu': ['user', 'system', 'percent'],
    'process.memory': ['resident', 'virtual', 'unique'],
    'process.children_stats_sum': ['cpu', 'memory'],
  }
  Here keys are names specified in @include_list_name(name) decorator,
  and values are lists of field names.
  """

  # Dictionary with known include lists
  # Key is name specified in decorator @include_list_name(name)
  # Value is an ordered set of attr.Attribute of decorated class (actually
  #   ordered set is simulated using OrderedDict with None values)
  all_attributes = {}

  @classmethod
  def register(cls, list_name, entity_class):
    """ Class method which is used by include_list_name decorator when
    new class is decorated with this. It saves all available attributes
    for the entity_class to all_attributes dict.

    Args:
      list_name: A string representing name of include list.
      entity_class: An @attr.s decorated class.
    """
    cls.all_attributes[list_name] = collections.OrderedDict(
      (att, None) for att in attr.fields(entity_class)
    )

  def __init__(self, include_lists):
    """ Validates include lists and copies it to own data structures.

    Args:
      include_lists: A dict where key is a name of include list,
        value is a list of fields to include.
    Raises:
      WrongIncludeLists if unknown field or unknown include list was found.
    """
    self._lists = {}
    self._original_dict = include_lists

    for list_name, fields_to_include in include_lists.items():
      try:
        known_attributes = self.all_attributes[list_name]
      except KeyError:
        raise WrongIncludeLists(
          'Include list "{name}" is unknown, available are: {known}'
          .format(name=list_name, known=list(self.all_attributes.keys()))
        )

      # List of field names will be transformed to set of attr.Attribute
      self._lists[list_name] = include = collections.OrderedDict()

      for field in fields_to_include:
        try:
          attribute = next(att for att in known_attributes if att.name == field)
          include[attribute] = None
        except StopIteration:
          known_field_names = [att.name for att in known_attributes]
          raise WrongIncludeLists(
            'Unknown field "{field}" for "{list}", available are: {known}'
            .format(field=field, list=list_name, known=known_field_names)
          )

  def get_included_attrs(self, stats_entity_class):
    """ Checks if there is any include list specified for stats_entity_class
    and if none was found - returns all available attributes for the class,
    otherwise returns only specified in include list.

    Args:
      stats_entity_class: An @attr.s decorated class, stats model.
    Returns:
      A list of attr.Attribute instances which should be included.
    """
    try:
      return self._lists[stats_entity_class._include_list_name]
    except KeyError:
      # No constraints specified for this entity - return all attributes
      return self.all_attributes[stats_entity_class._include_list_name]
    except AttributeError:
      # This stats entity class wasn't decorated with @include_list_name
      return attr.fields(stats_entity_class)

  def asdict(self):
    return self._original_dict

  def is_subset_of(self, include_lists):
    """ Determines if include_lists (argument) contains all attributes
    specified for this instance (self).

    Args:
      include_lists: An instance of IncludeLists to compare with.
    Returns:
      A boolean indicating if self if subset of include_lists.
    """
    if self is include_lists:
      return True
    for list_name, include_list in self._lists.items():
      corresponding_list = include_lists._lists.get(list_name)
      if corresponding_list is None:
        return False
      for attribute in include_list:
        if attribute not in corresponding_list:
          return False
    return True


def stats_to_dict(stats, include_lists=None):
  """ Renders stats entity to dictionary. If include_lists is specified
  it will skip not included fields.

  Args:
    stats: An instance of stats entity.
    include_lists: An instance of IncludeLists.

  Returns:
    A dictionary representation of stats.
  """
  if not include_lists:
    return attr.asdict(stats)
  included = include_lists.get_included_attrs(stats.__class__)
  result = {}
  for att in included:
    if att not in included:
      continue
    value = getattr(stats, att.name)
    if value is MISSED:
      continue
    if value and isinstance(value, dict):
      if attr.has(next(iter(value.values()))):
        # Only collections of attr types (stats models) should be converted
        value = {
          k: stats_to_dict(v, include_lists)
          for k, v in value.items()
        }
    elif value and isinstance(value, list):
      if attr.has(value[0]):
        # Only collections of attr types (stats models) should be converted
        value = [stats_to_dict(v, include_lists) for v in value]
    elif attr.has(value):
      value = stats_to_dict(value, include_lists)
    result[att.name] = value
  return result


def stats_from_dict(stats_class, dictionary, strict=False):
  """ Parses source dictionary and builds an entity of stats_class.

  Args:
    stats_class: An @attr.s decorated class representing stats entity.
    dictionary: A dict - source dictionary with stats fields.
    strict: A boolean determines whether missed fields should be replaced with
      MISSED constant.
  Returns:
    An instance of stats_class.
  Raises:
    TypeError if strict is True and any field is missed in dictionary.
  """
  changed_kwargs = {}
  for att in attr.fields(stats_class):
    if att.name not in dictionary and not strict:
      changed_kwargs[att.name] = MISSED
      continue
    if att.metadata:
      # Try to unpack nested entity
      nested_stats_class = att.metadata.get(Meta.ENTITY)
      if nested_stats_class:
        changed_kwargs[att.name] = stats_from_dict(
          nested_stats_class, dictionary[att.name], strict
        )
        continue
      # Try to unpack dict of nested entities
      nested_stats_class = att.metadata.get(Meta.ENTITY_DICT)
      if nested_stats_class:
        changed_kwargs[att.name] = {
          key: stats_from_dict(nested_stats_class, value, strict)
          for key, value in dictionary[att.name].items()
        }
        continue
      # Try to unpack list of nested entities
      nested_stats_class = att.metadata.get(Meta.ENTITY_LIST)
      if nested_stats_class:
        changed_kwargs[att.name] = [
          stats_from_dict(nested_stats_class, value, strict)
          for value in dictionary[att.name]
        ]
        continue

  if changed_kwargs:
    # Copy source dictionary if some values were unpacked/changed
    kwargs = dict(dictionary)
    kwargs.update(changed_kwargs)
  else:
    kwargs = dictionary

  return stats_class(**kwargs)


def get_stats_header(stats_class, include_lists=None, prefix=''):
  """ Renders a list containing names of fields. If include_lists is specified
  it will skip not included fields. Also it always skips any nested lists and
  dictionaries because they bring dynamically changing columns list **.
  Order of names in this header corresponds to values order in
  a list generated by stats_to_list.

  Args:
    stats_class: An @attr.s decorated class representing stats model.
    include_lists: An instance of IncludeLists.
    prefix: A string prefix to be prepended to column names.
  Returns:
    A list representing names of stats fields.
  """
  if include_lists:
    included = include_lists.get_included_attrs(stats_class)
  else:
    included = attr.fields(stats_class)
  result = []
  for att in included:
    if not att.metadata:
      result.append('{}{}'.format(prefix, att.name))
    else:
      nested_entity_class = att.metadata.get(Meta.ENTITY)
      if nested_entity_class:
        result += get_stats_header(nested_entity_class, include_lists,
                                   '{}{}.'.format(prefix, att.name))
  return result


def stats_to_list(stats, include_lists=None):
  """ Renders stats entity to a list. If include_lists is specified
  it will skip not included fields. Also it always skips any nested lists and
  dictionaries because they brings dynamically changing columns list **.

  Args:
    stats: An instance of stats entity.
    include_lists: An instance of IncludeLists.
  Returns:
    A list representing stats.
  """
  if include_lists:
    included = include_lists.get_included_attrs(stats.__class__)
  else:
    included = attr.fields(stats.__class__)
  result = []
  for att in included:
    if not att.metadata:
      value = getattr(stats, att.name)
      result.append(value)
    elif Meta.ENTITY in att.metadata:
      value = getattr(stats, att.name)
      if value is not MISSED:
        # Render nested stats entity
        result += stats_to_list(value, include_lists)
      else:
        # Render needed number of MISSED values
        stats_class = att.metadata[Meta.ENTITY]
        if include_lists:
          values_number = len(include_lists.get_included_attrs(stats_class))
        else:
          values_number = len(attr.fields(stats_class))
        result += [MISSED] * values_number
  return result
