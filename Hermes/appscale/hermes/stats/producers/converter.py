import attr

from appscale.hermes.stats.constants import MISSED


class WrongIncludeLists(ValueError):
  pass


class ConflictingIncludeListName(ValueError):
  pass


def include_list_name(name):
  """ # TODO """
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
  ENTITY = 'entity'
  ENTITY_DICT = 'dict'
  ENTITY_LIST = 'list'


class IncludeLists(object):
  """ # TODO """

  # Dictionary with known include lists
  # Key is name specified in decorator @include_list_name(name)
  # Value is a set of attr.Attribute of decorated class
  all_attributes = {}

  @classmethod
  def register(cls, list_name, entity_class):
    cls.all_attributes[list_name] = set(attr.fields(entity_class))

  def __init__(self, include_lists):
    """ Validates include lists and copies it to own data structures
    
    Args:
      include_lists: a dict where key is a name of include list,
                     value is a list of fields to include
    """
    self._lists = {}

    for list_name, fields_to_include in include_lists.iteritems():
      try:
        known_attributes = self.all_attributes[list_name]
      except KeyError:
        raise WrongIncludeLists(
          'Include list "{name}" is unknown, available are: {known}'
          .format(name=list_name, known=self.all_attributes.keys())
        )

      # List of field names will be transformed to set of attr.Attribute
      self._lists[list_name] = include = set()

      for field in fields_to_include:
        try:
          attribute = next(att for att in known_attributes if att.name == field)
          include.add(attribute)
        except StopIteration:
          known_field_names = [att.name for att in known_attributes.all_attributes]
          raise WrongIncludeLists(
            'Unknown field "{field}" for "{list}", available are: {known}'
            .format(field=field, list=list_name, known=known_field_names)
          )

  def get_included_attrs(self, stats_entity):
    try:
      return self._lists[stats_entity._include_list_name]
    except KeyError:
      # No constraints specified for this entity - return all attributes
      return self.all_attributes[stats_entity._include_list_name]
    except AttributeError:
      # This stats entity wasn't decorated with @include_list_name
      return set(attr.fields(stats_entity.__class__))



def stats_to_dict(stats, include_lists=None):
  """ Renders stats entity to dictionary. If include_lists is specified
  it will skip not included fields.
  
  Args:
     stats: an instance of stats entity
     include_lists: an instance of IncludeLists
     
  Returns:
    a dictionary representation of stats
  """
  if not include_lists:
    return attr.asdict(stats)
  included = include_lists.get_included_attrs(stats)
  result = {}
  for att in included:
    if att not in included:
      continue
    value = getattr(stats, att.name)
    if value is MISSED:
      continue
    if isinstance(value, dict):
      value = {k: stats_to_dict(v, include_lists) for k, v in value.iteritems()}
    elif isinstance(value, list):
      value = [stats_to_dict(v, include_lists) for v in value]
    elif attr.has(value):
      value = stats_to_dict(value, include_lists)
    result[att.name] = value
  return result


def stats_from_dict(stats_class, dictionary, strict=False):
  """ Parses source dictionary and builds an entity of stats_class
  
  Args:
    stats_class: @attr.s decorated class representing stats entity
    dictionary: a dict - source dictionary with stats fields
    strict: a boolean determines whether missed fields should be replaced with
            MISSED constant
     
  Returns:
    An instance of stats_class
    
  Raises:
    TypeError if strict is True and any field is missed in dictionary
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
          for key, value in dictionary[att.name].iteritems()
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

