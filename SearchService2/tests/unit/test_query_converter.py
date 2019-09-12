import collections

import pytest

from appscale.search import solr_adapter
from appscale.search.models import SolrSchemaFieldInfo
from appscale.search.query_converter import prepare_solr_query


def generate_fields(solr_field_names):
  """ Helper function for generating comprehensive
  fields information from a list of Solr field names.
  It's then should be passed to prepare_solr_query

  Args:
    solr_field_names:  a list of Solr field names (e.g.: "description_en_text").
  Returns:
    A tuple (<fields list>, <fields grouped by GAE name>).
  """
  fields = []
  grouped_fields = collections.defaultdict(list)
  for solr_name in solr_field_names:
    gae_name, type_, language = solr_adapter.parse_solr_field_name(solr_name)
    schema_field = SolrSchemaFieldInfo(
      solr_name=solr_name,
      gae_name=gae_name,
      type=type_,
      language=language,
      docs_number=None
    )
    fields.append(schema_field)
    grouped_fields[gae_name].append(schema_field)
  return fields, grouped_fields


FIELDS, GROUPED_FIELDS = generate_fields([
  'tag_atom',
  'name_atom',
  'description_txt_en',
  'description_txt_fr',
  'description_number',
  'description_date',
  'created_at_date',
  'modified_at_date',
  'price_number',
  'location_geo',
])


def test_single_word():
  solr_query_options = prepare_solr_query('foo', FIELDS, GROUPED_FIELDS)
  assert solr_query_options.query_string == '"foo"'
  assert set(solr_query_options.query_fields) == {
    'tag_atom',
    'name_atom',
    'description_txt_en',
    'description_txt_fr',
  }
  assert solr_query_options.def_type == 'edismax'


def test_single_number():
  solr_query_options = prepare_solr_query('-123.4', FIELDS, GROUPED_FIELDS)
  assert solr_query_options.query_string == '"-123.4"'
  assert set(solr_query_options.query_fields) == {
    'tag_atom',
    'name_atom',
    'description_txt_en',
    'description_txt_fr',
    'description_number',
    'price_number',
  }


def test_single_date():
  solr_query_options = prepare_solr_query('2019-01-23', FIELDS, GROUPED_FIELDS)
  assert solr_query_options.query_string == '"2019-01-23"'
  assert set(solr_query_options.query_fields) == {
    'tag_atom',
    'name_atom',
    'description_txt_en',
    'description_txt_fr',
    'description_date',
    'created_at_date',
    'modified_at_date',
  }


def test_stem_text():
  solr_query_options = prepare_solr_query('~hello', FIELDS, GROUPED_FIELDS)
  assert solr_query_options.query_string == '"hello"~'


@pytest.mark.xfail
def test_geo():
  # Geo location search is not supported yet.
  # Links:
  #  - https://cloud.google.com/appengine/docs/standard/python/search/query_strings#Python_Queries_on_geopoint_fields (GAE)
  #  - https://lucene.apache.org/solr/guide/7_6/spatial-search.html (Solr).
  prepare_solr_query(
    'distance(location, geopoint(35.2, 40.5)) < 100', FIELDS, GROUPED_FIELDS
  )


@pytest.mark.xfail
def test_two_words():
  solr_query_options = prepare_solr_query('hello world', FIELDS, GROUPED_FIELDS)
  # It's currently expected to fail as we convert it to '"hello" AND "world"'
  # Links:
  #  - https://cloud.google.com/appengine/docs/standard/python/search/query_strings#Python_Multi-value_queries
  assert solr_query_options.query_string == '"hello world"'
  assert set(solr_query_options.query_fields) == {
    'tag_atom',
    'name_atom',
    'description_txt_en',
    'description_txt_fr',
  }


def test_word_and_word():
  solr_query_options = prepare_solr_query(
    'hello AND world', FIELDS, GROUPED_FIELDS
  )
  assert solr_query_options.query_string == '("hello" AND "world")'
  assert set(solr_query_options.query_fields) == {
    'tag_atom',
    'name_atom',
    'description_txt_en',
    'description_txt_fr',
  }


def test_word_and_word_or_number():
  solr_query_options = prepare_solr_query(
    'hello AND world OR 321.6', FIELDS, GROUPED_FIELDS
  )
  assert solr_query_options.query_string == '("hello" AND ("world" OR "321.6"))'
  assert set(solr_query_options.query_fields) == {
    'tag_atom',
    'name_atom',
    'description_txt_en',
    'description_txt_fr',
    'description_number',
    'price_number',
  }


def test_date_and_word_or_number():
  solr_query_options = prepare_solr_query(
    '2019-02-02 AND world OR 321.6', FIELDS, GROUPED_FIELDS
  )
  assert solr_query_options.query_string == \
    '("2019-02-02" AND ("world" OR "321.6"))'
  assert set(solr_query_options.query_fields) == {
    'tag_atom',
    'name_atom',
    'description_txt_en',
    'description_txt_fr',
    'description_number',
    'description_date',
    'created_at_date',
    'modified_at_date',
    'price_number',
  }


def test_bool_operator_priorities():
  solr_query_options = prepare_solr_query(
    'NOT cat AND dogs OR horses', FIELDS, GROUPED_FIELDS
  )
  assert solr_query_options.query_string == \
         '(NOT "cat" AND ("dogs" OR "horses"))'

  solr_query_options = prepare_solr_query(
    'NOT cat OR dogs AND horses', FIELDS, GROUPED_FIELDS
  )
  assert solr_query_options.query_string == \
         '((NOT "cat" OR "dogs") AND "horses")'


def test_field_value():
  solr_query_options = prepare_solr_query('tag:hello', FIELDS, GROUPED_FIELDS)
  assert solr_query_options.query_string == 'tag_atom:"hello"'
  assert solr_query_options.query_fields == []


def test_field_quoted_value():
  solr_query_options = prepare_solr_query('tag:"hello"', FIELDS, GROUPED_FIELDS)
  assert solr_query_options.query_string == 'tag_atom:"hello"'
  assert solr_query_options.query_fields == []


def test_quoted():
  solr_query_options = prepare_solr_query(
    '"tag:hello AND whateve OR (it does NOT matter)"', FIELDS, GROUPED_FIELDS
  )
  assert solr_query_options.query_string == \
    '"tag:hello AND whateve OR (it does NOT matter)"'
  assert set(solr_query_options.query_fields) == {
    'tag_atom',
    'name_atom',
    'description_txt_en',
    'description_txt_fr',
  }


def test_field_with_many_types():
  # Value like number
  solr_query_options = prepare_solr_query(
    'description:-123.6', FIELDS, GROUPED_FIELDS
  )
  assert solr_query_options.query_string == (
    '(description_txt_en:"-123.6" OR description_txt_fr:"-123.6" OR'
    ' description_number:"-123.6")'
    # Searching number on description_date would lead to error,
    # so it should be skipped.
  )
  assert solr_query_options.query_fields == []

  # Value like date
  solr_query_options = prepare_solr_query(
    'description:1999-08-15', FIELDS, GROUPED_FIELDS
  )
  assert solr_query_options.query_string == (
    '(description_txt_en:"1999-08-15" OR description_txt_fr:"1999-08-15" OR'
    ' description_date:"1999-08-15")'
    # Searching date on description_number would lead to error,
    # so it should be skipped.
  )
  assert solr_query_options.query_fields == []


def test_field_match_both_values():
  # Value like number AND value like date
  solr_query_options = prepare_solr_query(
    'description:(-123.6 AND 1999-08-15)', FIELDS, GROUPED_FIELDS
  )
  assert solr_query_options.query_string == (
    '((description_txt_en:"-123.6" OR description_txt_fr:"-123.6" OR'
    ' description_number:"-123.6") AND '
    '(description_txt_en:"1999-08-15" OR description_txt_fr:"1999-08-15" OR'
    ' description_date:"1999-08-15"))'
  )
  assert solr_query_options.query_fields == []


def test_field_match_any_value():
  # Value like number OR value like date
  solr_query_options = prepare_solr_query(
    'description:(-123.6 OR 1999-08-15)', FIELDS, GROUPED_FIELDS
  )
  assert solr_query_options.query_string == (
    '((description_txt_en:"-123.6" OR description_txt_fr:"-123.6" OR'
    ' description_number:"-123.6") OR '
    '(description_txt_en:"1999-08-15" OR description_txt_fr:"1999-08-15" OR'
    ' description_date:"1999-08-15"))'
  )
  assert solr_query_options.query_fields == []


def test_field_compare():
  solr_query_options = prepare_solr_query(
    'description>100.2 description<=200 price<999.9 price>=100 '
    'created_at>=1990-06-13',
    FIELDS, GROUPED_FIELDS
  )
  assert solr_query_options.query_string == (
    '(description_number:{"100.2" TO *] AND description_number:[* TO "200"]'
    ' AND price_number:[* TO "999.9"} AND price_number:["100" TO *]'
    ' AND created_at_date:["1990-06-13" TO *])'
    # Searching date on description_number would lead to error,
    # so it should be skipped.
  )
  assert solr_query_options.query_fields == []


def test_complex_composition():
  solr_query_options = prepare_solr_query(
    'name:(-123.6 OR 1999-08-15 AND (foo AND NOT bar dogs (hello))) '
    'AND tag:phone "some () quoted text NOT 123" '
    'OR (one two OR three) OR price>321.6',
    FIELDS, GROUPED_FIELDS
  )
  assert solr_query_options.query_string == (
    '(((name_atom:"-123.6" OR name_atom:"1999-08-15") AND '
    '(name_atom:"foo" AND NOT name_atom:"bar" AND name_atom:"dogs" AND '
    'name_atom:"hello")) AND '
    'tag_atom:"phone" AND ("some () quoted text NOT 123" OR '
    '("one" AND ("two" OR "three")) OR '
    'price_number:{"321.6" TO *]))'
  )
  assert set(solr_query_options.query_fields) == {
    'tag_atom',
    'name_atom',
    'description_txt_en',
    'description_txt_fr',
  }
