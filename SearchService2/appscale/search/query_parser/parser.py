"""
parser module is responsible for parsing query string and building
structured tree containing grouped expressions.

e.g.:
"foo bar OR (price<1025 AND product:(laptop OR camera))"
is translated to:

ExpressionsGroup(
  OR
  ExpressionsGroup(
    AND
    Expression(field_name=, operator=EQUALS, value=Value(str_value="foo"))
    Expression(field_name=, operator=EQUALS, value=Value(str_value="bar")))
  ExpressionsGroup(
    AND
    Expression(field_name=price, operator=LESS, value=Value("1025"))
    Expression(field_name=product, operator=EQUALS, value=
        ValuesGroup(
          OR
          Value(str_value="laptop")
          Value(str_value="camera")  ))))
"""
import datetime
import logging

import antlr4
import attr

from appscale.search.constants import InvalidRequest
from appscale.search.query_parser.queryLexer import queryLexer
from appscale.search.query_parser.queryParser import queryParser

logger = logging.getLogger(__name__)


# =======================
#  Trivial query tokens:
# -----------------------
AND = queryParser.AND
OR = queryParser.OR

NOT = queryParser.NOT
STEM = queryParser.STEM

EQUALS = queryParser.EQUALS
LESS = queryParser.LESS
LESS_EQ = queryParser.LESS_EQ
GREATER = queryParser.GREATER
GREATER_EQ = queryParser.GREATER_EQ
# ^^^^^^^^^^^^^^^^^^^^^^^


# ===========================
#  Composite parts of query:
# ---------------------------
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ExpressionsGroup(object):
  """
  A model representing group of expressions
  and expression groups connected by AND or OR.
  It corresponds to entire query or nested queries.
  e.g.: `foo bar OR (price<1025 AND product:laptop)`
         ^^\1/^^    ^^^^^^^^^^^^^^\2/^^^^^^^^^^^^^^
         ^^^^^^^^^^^^^\3/^^^^^^^^^^^^^^^^^^^^^^^^^^
  """
  operator = attr.ib()    # OR | AND
  elements = attr.ib()    # ExpressionsGroup | Expression


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class Expression(object):
  """
  A model representing an expression. It holds information
  about field name, operator and value or values group.
  e.g.: `product  :  (one OR other AND NOT foo)`
       field^     |  ^^^^^\ values group /^^^^^
                  ^operator
  """
  field_name = attr.ib()  # string
  operator = attr.ib()    # EQUALS | LESS | LESS_EQ | GREATER | GREATER_EQ
  value = attr.ib()       # ValuesGroup | Value


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ValuesGroup(object):
  """
  A model representing group if values
  and value groups connected by AND or OR.
  Ot corresponds to right hand part of expression.
  e.g.: `(~first_value OR (second_value AND NOT third_value))`
          ^^\value/^^^ |  ^^^^^^^^^\ values group /^^^^^^^^^
                       ^operator
  """
  operator = attr.ib()    # OR | AND
  elements = attr.ib()    # ValuesGroup | Value


NOT_NUMBER = object()
NOT_DATE = object()


@attr.s(cmp=False, hash=False, slots=True)
class Value(object):
  """
  A model representing a leaf of query tree:
  a value with optional negotiation or stemming.
  e.g.: `NOT  hello_world`
         ^not ^^\value/^^
  """
  not_ = attr.ib()                       # boolean
  stem = attr.ib()                       # boolean
  str_value = attr.ib()                  # unicode string
  _number_value = attr.ib(default=None)  # float if raw_value matches number
  _date_value = attr.ib(default=None)    # date if raw_value matches date
  # TODO: _geo_value to be added, It requires grammar changes.

  @property
  def number_value(self):
    if self._number_value is None:
      try:
        self._number_value = float(self.str_value)
      except ValueError:
        self._number_value = NOT_NUMBER
    return self._number_value

  @property
  def date_value(self):
    if self._date_value is None:
      try:
        year, month, day = self.str_value.split('-', 2)
        self._date_value = datetime.date(int(year), int(month), int(day))
      except (ValueError, TypeError):
        self._date_value = NOT_DATE
    return self._date_value

  @property
  def has_number_value(self):
    return self.number_value is not NOT_NUMBER

  @property
  def has_date_value(self):
    return self.date_value is not NOT_DATE


def _group_or_single_expr(operator, elements):
  if len(elements) > 1:
    return ExpressionsGroup(operator=operator, elements=elements)
  return elements[0]


def _group_or_single_value(operator, elements):
  if len(elements) > 1:
    return ValuesGroup(operator=operator, elements=elements)
  return elements[0]
# ^^^^^^^^^^^^^^^^^^^^^^^^^^^


def parse_query(query_str):
  """ Parses GAE search query and returns easily readable
  composition of Expressions.

  Args:
    query_str: a str representing GAE search query.
  Returns:
    An Expression or ExpressionsGroup corresponding to query_str.
  """
  input_stream = antlr4.InputStream(query_str)
  lexer = queryLexer(input_stream)
  stream = antlr4.CommonTokenStream(lexer)
  parser = queryParser(stream)
  raw_query_node = parser.query()    # MATCHED: exprs_seq EOF
  if parser.getNumberOfSyntaxErrors():
    if 'distance(' in query_str:
      msg = 'Searching on GeoPoint fields is not supported yet.'
    else:
      msg = 'Failed to parse query string: "{}"'.format(query_str)
    raise InvalidRequest(msg)
  exprs_seq_node = raw_query_node.children[0]
  return _process_exprs_seq(exprs_seq_node)


def _process_exprs_seq(exprs_seq_node):
  """ Transforms antlr4 tree node to Expression or ExpressionsGroup.

  Args:
    exprs_seq_node: an ExprsSeqContext generated by antlr4.
  Returns:
    An Expression or ExpressionsGroup corresponding to query_str.
  """
  # According to GAE docs logical operators should be applied in order:
  # first NOT, then OR, last AND.
  connected_by_and = []
  connected_by_or = []
  for element in _read_exprs_seq(exprs_seq_node):
    if isinstance(element, (Expression, ExpressionsGroup)):
      connected_by_or.append(element)
    elif element == AND:
      nested = _group_or_single_expr(OR, connected_by_or)
      connected_by_and.append(nested)
      connected_by_or = []

  if connected_by_or:
    nested = _group_or_single_expr(OR, connected_by_or)
    connected_by_and.append(nested)

  return _group_or_single_expr(AND, connected_by_and)


def _read_exprs_seq(exprs_seq_node):
  """ Generates instances of Expression or ExpressionsGroup
  while iterating through children of exprs_seq_node.

  Args:
    exprs_seq_node: an ExprsSeqContext generated by antlr4.
  """
  prev_element = None
  for child in exprs_seq_node.children:
    if isinstance(child, queryParser.ExprContext):
      # MATCHED: expr
      if prev_element is not None:
        yield prev_element if prev_element in [AND, OR] else AND
      prev_element = child
      yield _process_expr(child)
    elif isinstance(child, queryParser.ExprsGroupContext):
      # MATCHED: "(" exprs_seq ")"
      if prev_element is not None:
        yield prev_element if prev_element in [AND, OR] else AND
      prev_element = child
      in_brackets = child.children[1]    # 0:"("  1:nested_seq  2:")"
      yield _process_exprs_seq(in_brackets)
    else:    # isinstance(child, Tree.TerminalNode):
      # MATCHED: AND | OR
      prev_element = child.symbol.type    # it is AND or OR


def _process_expr(expr_node):
  """ Transforms antlr4 tree node to Expression.

  Args:
    expr_node: an ExprContext generated by antlr4.
  Returns:
    An Expression corresponding to expr_node.
  """
  if len(expr_node.children) == 3:
    # MATCHED: field_name operator (value | "(" values_seq ")")
    field_name = expr_node.children[0].getText()
    operator = expr_node.children[1].symbol.type
    right_hand = expr_node.children[2]
    if isinstance(right_hand, queryParser.UnaryExprsGroupContext):
      in_brackets = right_hand.children[1]    # 0:"("  1:nested_seq  2:")"
      value = _process_unary_exprs_seq(in_brackets)
    else:
      value = _process_unary_expr(right_hand)
  else:
    # MATCHED: value
    field_name = None
    operator = EQUALS
    value = _process_unary_expr(expr_node.children[0])

  return Expression(field_name=field_name, operator=operator, value=value)


def _process_unary_exprs_seq(unary_exprs_seq_node):
  """ Transforms antlr4 tree node to Value or ValuesGroup.

  Args:
    unary_exprs_seq_node: an UnaryExprsGroupContext generated by antlr4.
  Returns:
    A Value or ValuesGroup corresponding to unary_exprs_seq_node.
  """
  # According to GAE docs logical operators should be applied in order:
  # first NOT, then OR, last AND.
  connected_by_and = []
  connected_by_or = []
  for element in _read_unary_exprs_seq(unary_exprs_seq_node):
    if isinstance(element, (Value, ValuesGroup)):
      connected_by_or.append(element)
    elif element == AND:
      nested = _group_or_single_value(OR, connected_by_or)
      connected_by_and.append(nested)
      connected_by_or = []

  if connected_by_or:
    nested = _group_or_single_value(OR, connected_by_or)
    connected_by_and.append(nested)

  return _group_or_single_value(AND, connected_by_and)


def _read_unary_exprs_seq(unary_exprs_seq_node):
  """ Generates instances of Value or ValuesGroup
  while iterating through children of unary_exprs_seq_node.

  Args:
    unary_exprs_seq_node: an UnaryExprsGroupContext generated by antlr4.
  """
  prev_element = None
  for child in unary_exprs_seq_node.children:
    if isinstance(child, queryParser.UnaryExprContext):
      # MATCHED: unary_expr
      if prev_element is not None:
        yield prev_element if prev_element in [AND, OR] else AND
      prev_element = child
      yield _process_unary_expr(child)
    elif isinstance(child, queryParser.UnaryExprsGroupContext):
      # MATCHED: "(" unary_exprs_seq ")"
      if prev_element is not None:
        yield prev_element if prev_element in [AND, OR] else AND
      prev_element = child
      in_brackets = child.children[1]    # 0:"("  1:nested_seq  2:")"
      yield _process_unary_exprs_seq(in_brackets)
    else:    # isinstance(child, Tree.TerminalNode):
      # MATCHED: AND | OR
      prev_element = child.symbol.type    # it is AND or OR


def _process_unary_expr(unary_expr_node):
  """ Transforms antlr4 tree node to Value.

  Args:
    unary_expr_node: an UnaryExprContext generated by antlr4.
  Returns:
    A Value corresponding to unary_expr_node.
  """
  if len(unary_expr_node.children) == 2:
    # MATCHED: (NOT | ~) (WORD | QUOTED)
    not_or_stem = unary_expr_node.children[0].symbol.type
    not_ = not_or_stem == NOT
    stem = not_or_stem == STEM
    value = unary_expr_node.children[1].getText()
  else:
    # MATCHED: WORD | QUOTED
    not_ = False
    stem = False
    value = unary_expr_node.children[0].getText()

  return Value(not_=not_, stem=stem, str_value=value)


def print_exprs_group(exprs_group, prefix=u''):
  """ Debugging function for printing expressions group.

  Args:
    exprs_group: an ExpressionsGroup.
    prefix: a str to prepend to output string.
  """
  print(prefix + (u'AND' if exprs_group.operator == AND else u'OR'))
  for element in exprs_group.elements:
    if isinstance(element, Expression):
      logger.info(prefix + u' ' + repr(element))
    else:
      print_exprs_group(element, prefix+u'    ')
