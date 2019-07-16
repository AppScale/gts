import collections

from appscale.search import solr_adapter
from appscale.search.facet_converter import (
  discover_facets, generate_refinement_filter, convert_facet_requests,
  convert_facet_results
)
from appscale.search.models import (
  SolrSchemaFieldInfo, FacetRefinement, FacetRequest, FacetResult
)


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


FACETS, GROUPED_FACETS = generate_fields([
  'tag_atom_facet',
  'product_atom_facet',
  'category_atom_facet',
  'country_atom_facet',
  'price_number_facet',
  'year_number_facet',
])


def test_refinements_filter():
  filter_str = generate_refinement_filter(
    GROUPED_FACETS,
    [
      FacetRefinement(name='tag', value='hi-tech', range=None),
      FacetRefinement(name='tag', value='furniture', range=None),
      FacetRefinement(name='tag', value='sale', range=None),
      FacetRefinement(name='price', value=None, range=(None, 100)),
      FacetRefinement(name='price', value=None, range=(100, 500)),
      FacetRefinement(name='year', value='[12,56)', range=None),
    ]
  )
  expected = (
    '(tag_atom_facet:"hi-tech"'
    ' OR tag_atom_facet:"furniture"'
    ' OR tag_atom_facet:"sale")'
    ' AND (price_number_facet:[* TO 100} OR price_number_facet:[100 TO 500})'
    ' AND (year_number_facet:[12 TO 56})'
  )
  actual_set = set(filter_str.split(' AND '))
  expected_set = set(expected.split(' AND '))
  assert actual_set == expected_set


def test_discover_facets():
  tag_solr_field = GROUPED_FACETS['tag'][0]
  product_solr_field = GROUPED_FACETS['product'][0]
  category_solr_field = GROUPED_FACETS['category'][0]
  country_solr_field = GROUPED_FACETS['country'][0]
  price_solr_field = GROUPED_FACETS['price'][0]
  fake_stats = [
    (tag_solr_field, 203),
    (product_solr_field, 687),
    (category_solr_field, 167),
    (country_solr_field, 1023),
    (price_solr_field, 365),
  ]
  facet_items, stats_items = discover_facets(
    facets_stats=fake_stats, facets_count=4, value_limit=5
  )
  expected_facet_items = [
    ('country*', {
      'type': 'terms',
      'field': 'country_atom_facet',
      'limit': 5
    }),
    ('product*', {
      'type': 'terms',
      'field': 'product_atom_facet',
      'limit': 5
    }),
    ('tag*', {
      'type': 'terms',
      'field': 'tag_atom_facet',
      'limit': 5
    }),
  ]
  expected_stats_items = [
    (price_solr_field, '{!min=true max=true count=true}price_number_facet'),
  ]
  assert facet_items == expected_facet_items
  assert stats_items == expected_stats_items


def test_convert_facet_requests():
  facet_requests = [
    FacetRequest(
      name='tag', value_limit=None,
      values=['entertainment', 'traveling', 'food'],
      ranges=[]
    ),
    FacetRequest(
      name='country', value_limit=6, values=[], ranges=[]
    ),
    FacetRequest(
      name='price', value_limit=None,
      values=[],
      ranges=[(None, 50), (50, 150), (150, 500), (500, None)]
    ),
    FacetRequest(
      name='year', value_limit=None,
      values=[],
      ranges=[]
    ),
  ]
  facet_items, stats_items = convert_facet_requests(
    GROUPED_FACETS, facet_requests
  )
  expected_facet_items = [
    # Tag values facet
    ('tag:entertainment', {'query': 'tag_atom_facet:"entertainment"'}),
    ('tag:traveling', {'query': 'tag_atom_facet:"traveling"'}),
    ('tag:food', {'query': 'tag_atom_facet:"food"'}),
    # Country terms facet
    ('country*', {
      'type': 'terms',
      'field': 'country_atom_facet',
      'limit': 6
    }),
    # Price ranges facet
    ('price#[* TO 50}', {'query': 'price_number_facet:[* TO 50}'}),
    ('price#[50 TO 150}', {'query': 'price_number_facet:[50 TO 150}'}),
    ('price#[150 TO 500}', {'query': 'price_number_facet:[150 TO 500}'}),
    ('price#[500 TO *}', {'query': 'price_number_facet:[500 TO *}'}),
  ]
  year_solr_field = GROUPED_FACETS['year'][0]
  expected_stats_items = [
    (year_solr_field, '{!min=true max=true count=true}year_number_facet'),
  ]
  assert facet_items == expected_facet_items
  assert stats_items == expected_stats_items


def test_convert_facet_results():
  facet_results = convert_facet_results(
    solr_facet_results={
      # Tag values facet
      'tag:entertainment': {'count': 128},
      'tag:traveling': {'count': 32},
      'tag:food': {'count': 8},
      # Country terms facet
      'country*': {
        'buckets': [
          {'val': 'cn', 'count': 100},
          {'val': 'us', 'count': 20},
          {'val': 'uk', 'count': 5},
        ]
      },
      # Price ranges facet
      'price#[* TO 50}': {'count': 81},
      'price#[50 TO 150}': {'count': 243},
      'price#[150 TO 500}': {'count': 27},
      'price#[500 TO *}': {'count': 3},
    },
    stats_results=[
      ('year', {'min': 1986, 'max': 2019, 'count': 156})
    ])
  expected = [
    FacetResult(
      name='tag',
      values=[('entertainment', 128), ('traveling', 32), ('food', 8)],
      ranges=[]
    ),
    FacetResult(
      name='country',
      values=[('cn', 100), ('us', 20), ('uk', 5)],
      ranges=[]
    ),
    FacetResult(
      name='price',
      values=[],
      ranges=[(None, 50, 81), (50, 150, 243), (150, 500, 27), (500, None, 3)]
    ),
    FacetResult(
      name='year',
      values=[('[1986,2019)', 156)],
      ranges=[]
    ),
  ]
  # Order doesn't matter, so let's sort actual and expected.
  facet_results.sort(key=lambda item: item.name)
  for result in facet_results:
    result.values.sort()
    result.ranges.sort(key=lambda item: (item[0] or 0, item[1] or 1))
  expected.sort(key=lambda item: item.name)
  for result in expected:
    result.values.sort()
    result.ranges.sort(key=lambda item: (item[0] or 0, item[1] or 1))
  assert facet_results == expected
