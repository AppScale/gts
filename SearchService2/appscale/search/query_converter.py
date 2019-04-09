"""
Code for turning a GAE Search query into a SOLR query.
"""
import logging

from appscale.search.constants import InvalidRequest
from appscale.search.models import SolrQueryOptions, SolrSchemaFieldInfo
from appscale.search.query_parser import parser

logger = logging.getLogger(__name__)


def prepare_solr_query(gae_query, fields, grouped_fields):
  """ Converts gae_query string into Solr query string.

  Args:
    gae_query: a str containing GAE Search query.
    fields: a list of SolrSchemaFieldInfo.
    grouped_fields: a dict containing mapping from GAE field name
                    to list of SolrSchemaFieldInfo.
  Returns:
    An instance of SolrQueryOptions.
  """
  converter = _QueryConverter(gae_query, fields, grouped_fields)
  return converter.solr_query()


_SOLR_TYPE = SolrSchemaFieldInfo.Type


class _QueryConverter(object):
  """
  It could be just a set of functions, but having self reference helps
  to store temporary values and simplify recursive query rendering.
  """

  NOT_MATCHABLE = u'id:""'    # A Solr query which matches nothing.
  GLOBAL_SEARCH = object()    # A constant to mark missing field in expression.

  class NotApplicableValue(Exception):
    """ Helper exception which is used to follow principle
    "Ask forgiveness not permission". It's not always easy
    to figure out in advance if it's reasonable to go deeper into
    nested syntax tree nodes to prepare query for number or date field
    as we don't know what type has a right hand values of expression.
    """
    pass

  def __init__(self, gae_query, fields, grouped_fields):
    """ Initializes instance of _QueryConverter.

    Args:
      gae_query: A str representing query sent by user.
      fields: a list of SolrSchemaFieldInfo.
      grouped_fields: a dict containing mapping from GAE field name
                      to list of SolrSchemaFieldInfo.
    """
    self.gae_query = gae_query
    self.schema_fields = fields
    self.grouped_schema_fields = grouped_fields
    self.has_string_values = False
    self.has_date_values = False
    self.has_number_values = False
    self.has_geo_values = False

  def solr_query(self):
    """ Generates SolrQueryOptions containing solr query string,
    query fields and def_type (type of Solr query parser to use).

    Returns:
      An instance of SolrQueryOptions to use in Solr request.
    """
    if not self.gae_query:
      return SolrQueryOptions(
        query_string='*:*',
        query_fields=[],
        def_type='edismax'
      )
    # Build syntax tree
    expr_or_exprs_group = parser.parse_query(self.gae_query)

    # Render Solr query string according to the syntax tree
    try:
      solr_query = self._render_exprs(expr_or_exprs_group)
    except self.NotApplicableValue:
      solr_query = self.NOT_MATCHABLE

    # Find all fields which need to be queried for global search
    query_fields = []
    if self.has_string_values:
      query_fields += [
        schema_field.solr_name for schema_field in self.schema_fields
        if (
            schema_field.type == _SOLR_TYPE.ATOM_FIELD
            or schema_field.type == _SOLR_TYPE.TEXT_FIELD
        )
      ]
    if self.has_date_values:
      query_fields += [
        schema_field.solr_name for schema_field in self.schema_fields
        if schema_field.type == _SOLR_TYPE.DATE_FIELD
      ]
    if self.has_number_values:
      query_fields += [
        schema_field.solr_name for schema_field in self.schema_fields
        if schema_field.type == _SOLR_TYPE.NUMBER_FIELD
      ]

    return SolrQueryOptions(
      query_string=solr_query,
      query_fields=query_fields,
      def_type='edismax'
    )

  def _render_exprs(self, expr_or_exprs_group):
    """ Renders an Expression or ExpressionsGroup.

    Args:
      expr_or_exprs_group: an Expression or ExpressionsGroup to render.
    Return:
      a str representing Solr query corresponding to expr_or_exprs_group.
    """
    if isinstance(expr_or_exprs_group, parser.Expression):
      expr = expr_or_exprs_group
      return self._render_single_expr(expr)
    exprs_group = expr_or_exprs_group
    rendered_elements = []
    for element in exprs_group.elements:
      try:
        rendered = self._render_exprs(element)
        rendered_elements.append(rendered)
      except self.NotApplicableValue:
        # Element can't be matched: field is missing or value is not applicable
        if exprs_group.operator == parser.AND:
          # Expressions group doesn't match as one AND elements doesn't match.
          raise
        continue

    if not rendered_elements:
      raise self.NotApplicableValue()

    if len(rendered_elements) == 1:
      return rendered_elements[0]

    operator = u' AND ' if exprs_group.operator == parser.AND else u' OR '
    return u'({})'.format(operator.join(rendered_elements))

  def _render_single_expr(self, expr):
    """ Renders a single Expression which corresponds to either
    field-specific or global search expression.
    A single expression can be extracted to group of expressions
    connected by OR, where each nested expression corresponds to
    one of field types. It's done because GAE allows to define fields
    with different type but the same name, so one GAE field name
    maps to number of different Solr fields.

    Args:
      expr: an Expression.
    Return:
      a str representing Solr query corresponding to expr_or_exprs_group.
    """
    # Corresponds to converting field-search expression or unary expression:
    # `hello`
    # `~hello`
    # `NOT hello`
    # `fieldX:2018-3-15`
    # `fieldY:(some OR (more AND complex) ~expression NOT here)`
    if not expr.field_name:
      return self._render_unary_exprs(
        self.GLOBAL_SEARCH, parser.EQUALS, expr.value
      )
    try:
      # Expr should match any of available field types for GAE field name.
      schema_fields = self.grouped_schema_fields[expr.field_name]
    except KeyError:
      logger.warning('Unknown field "{}" in query string'
                     .format(expr.field_name))
      raise self.NotApplicableValue()

    return self._render_unary_exprs(schema_fields, expr.operator, expr.value)

  def _render_unary_exprs(self, schema_fields, operator, value_or_values_group):
    """ Renders an Expression limited to particular SOLR field
    (so it has one known type) or GLOBAL_SEARCH.
    If value_or_values_group is ValuesGroup, it extracts values in brackets
    and prepends solr field with operator to every nested value.

    Args:
      schema_fields: a list of SolrSchemaFieldInfo or GLOBAL_SEARCH.
      operator: EQUALS, LESS, LESS_EQ, GREATER or GREATER_EQ.
      value_or_values_group: a Value or ValuesGroup.
    Return:
      a str representing Solr query corresponding to expression
      limited to particular SOLR field (with known type) or GLOBAL_SEARCH.
    """
    if isinstance(value_or_values_group, parser.Value):
      value = value_or_values_group
      return self._render_single_unary_expr(schema_fields, operator, value)

    # Process nested tree.
    values_group = value_or_values_group
    nested_unary_exprs = []
    for element in values_group.elements:
      try:
        rendered = self._render_unary_exprs(schema_fields, operator, element)
        nested_unary_exprs.append(rendered)
      except self.NotApplicableValue:
        # e.g.: searching "word" against filed with date type.
        if operator == parser.AND:
          # There's no sense to continue.
          raise
        continue

    if not nested_unary_exprs:
      # e.g.: searching ONLY text against filed with date type.
      raise self.NotApplicableValue()

    if len(nested_unary_exprs) == 1:
      return nested_unary_exprs[0]

    operator = u' AND ' if values_group.operator == parser.AND else u' OR '
    return u'({})'.format(operator.join(nested_unary_exprs))

  def _render_single_unary_expr(self, schema_fields, operator, value):
    """ Renders a leaf of Solr query string which is limited
    to particular SOLR field (or GLOBAL_SEARCH) and a single value.

    Args:
      schema_fields: a list of SolrSchemaFieldInfo or GLOBAL_SEARCH.
      operator: EQUALS, LESS, LESS_EQ, GREATER or GREATER_EQ.
      value: a Value.
    Return:
      a str representing Solr query leaf corresponding to expression
      limited to particular SOLR field (or GLOBAL_SEARCH) and a single value.
    """
    right_hand = value.str_value
    if right_hand[0] != u'"':
      right_hand = u'"{}"'.format(right_hand)
    if value.stem:
      right_hand = right_hand + u'~'

    if schema_fields == self.GLOBAL_SEARCH:
      # We need to add all text, atom and html fields to query_fields list
      self.has_string_values = True
      if value.has_number_value:
        # We need to add all number fields to query_fields list
        self.has_number_values = True
      if value.has_date_value:
        # We need to add all date fields to query_fields list
        self.has_date_values = True
      return u'NOT {}'.format(right_hand) if value.not_ else right_hand

    # Connect by OR rendered statement for each field type
    statements = []
    for schema_field in schema_fields:
      # Skip if value is not applicable for field type.
      if schema_field.type == _SOLR_TYPE.TEXT_FIELD:
        if operator != parser.EQUALS:
          # Can't compare using > < >= <=
          continue
      elif schema_field.type == _SOLR_TYPE.ATOM_FIELD:
        if operator != parser.EQUALS or value.stem:
          # Can't stem atom field or compare using > < >= <=
          continue
      elif schema_field.type == _SOLR_TYPE.NUMBER_FIELD:
        if not value.has_number_value or value.stem:
          # Can't search text against number field
          continue
      elif schema_field.type == _SOLR_TYPE.DATE_FIELD:
        if not value.has_date_value or value.stem:
          # Can't search text against date field
          continue
      elif schema_field.type == _SOLR_TYPE.GEO_FIELD:
        logger.warning('Geo location queries are not supported yet.')
        continue
      else:  # schema_field.type is not queryable
        continue
      rendered = self._render_field_operator_value(
        schema_field, operator, right_hand
      )
      statements.append(u'NOT {}'.format(rendered) if value.not_ else rendered)

    if not statements:
      # e.g.: searching "word" against filed with ONLY date type.
      raise self.NotApplicableValue()

    if len(statements) == 1:
      return statements[0]

    # e.g.: searching "1999-10-20" against field with type date and text.
    # Any match should be enough.
    return u'({})'.format(u' OR '.join(statements))

  @staticmethod
  def _render_field_operator_value(schema_field, operator, right_hand):
    """ Renders equality or range query according to Solr query syntax.

    Args:
      schema_field: a SolrSchemaFieldInfo or GLOBAL_SEARCH.
      operator: EQUALS, LESS, LESS_EQ, GREATER or GREATER_EQ.
      right_hand: a str representing value.
    Returns:
      A string representing equality or range query.
    """
    if operator == parser.EQUALS:
      return u'{}:{}'.format(schema_field.solr_name, right_hand)
    if operator == parser.LESS:
      return u'{}:[* TO {}}}'.format(schema_field.solr_name, right_hand)
    if operator == parser.LESS_EQ:
      return u'{}:[* TO {}]'.format(schema_field.solr_name, right_hand)
    if operator == parser.GREATER:
      return u'{}:{{{} TO *]'.format(schema_field.solr_name, right_hand)
    if operator == parser.GREATER_EQ:
      return u'{}:[{} TO *]'.format(schema_field.solr_name, right_hand)
