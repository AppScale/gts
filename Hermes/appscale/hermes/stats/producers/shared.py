from appscale.hermes.constants import MISSED


class WrongIncludeLists(ValueError):
  pass


def stats_entity_to_dict(stats_entity, include_list):
  rendered_dict = {}
  for field in include_list:
    value = getattr(stats_entity, field)
    if value is MISSED:
      continue
    rendered_dict[field] = value
  return rendered_dict