"""
Declares models to use in SearchService2. Instances of these classes
are just frozen containers of information.

It helps to remove protobuf-specific code from solr_adapter
and solr-specific code from api_methods. So both modules can talk on
unified language which corresponds to Google Search API documentation.
It doesn't cover all Google Search API objects, models are not defined
for objects like SearchParams and SortExpression, its properties are
either not supported or are passed as a keyword arguments of
SolrAdapter methods.

There are two types of models:
  - Models corresponding to Google Search API objects;
  - Helper models for solr_adapter.

Google documentations can be helpful
if you have any questions regarding Search API objects:
  https://cloud.google.com/appengine/docs/standard/python/search/documentclass
"""
import attr


# ==================================================
#     MODELS CORRESPONDING TO Search API OBJECTS
# --------------------------------------------------

@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class Document(object):
  doc_id = attr.ib()
  fields = attr.ib()
  facets = attr.ib()
  language = attr.ib()
  rank = attr.ib()


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class Field(object):
  class Type(object):
    TEXT = "text"
    HTML = "html"
    ATOM = "atom"
    NUMBER = "number"
    DATE = "date"      # value is a datetime
    GEO = "geo"        # value is a tuple(lat, lng)

  type = attr.ib()
  name = attr.ib()
  value = attr.ib()
  language = attr.ib()


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class Facet(object):
  class Type(object):
    ATOM = "atom_facet"
    NUMBER = "number_facet"

  type = attr.ib()
  name = attr.ib()
  value = attr.ib()


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ScoredDocument(object):
  doc_id = attr.ib()
  fields = attr.ib()
  facets = attr.ib()
  language = attr.ib()
  sort_scores = attr.ib()
  expressions = attr.ib()
  cursor = attr.ib()
  rank = attr.ib()


@attr.s(hash=False, slots=True, frozen=True)
class FacetRequest(object):
  name = attr.ib()
  value_limit = attr.ib()
  values = attr.ib()    # A list of values
  ranges = attr.ib()    # A list of tuples (<INCLUSIVE_START>, <EXCLUSIVE_END>)


@attr.s(hash=False, slots=True, frozen=True)
class FacetRefinement(object):
  name = attr.ib()
  value = attr.ib()
  range = attr.ib()    # A tuple (<INCLUSIVE_START>, <EXCLUSIVE_END>)


@attr.s(hash=False, slots=True, frozen=True)
class FacetResult(object):
  name = attr.ib()
  values = attr.ib()    # List of tuples (<VALUE>, <COUNT>)
  ranges = attr.ib()    # A tuple (<INCLUSIVE_START>, <EXCLUSIVE_END>, <COUNT>)


@attr.s(hash=False, slots=True, frozen=True)
class SearchResult(object):
  num_found = attr.ib()
  scored_documents = attr.ib()
  cursor = attr.ib()
  facet_results = attr.ib()


@attr.s(hash=False, slots=True, frozen=True)
class IndexMetadata(object):
  app_id = attr.ib()
  namespace = attr.ib()
  index_name = attr.ib()
  # TODO we may need to add more metadata fields.


# ======================================
#     HELPER MODELS FOR SOLR ADAPTER
# --------------------------------------

@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class SolrIndexSchemaInfo(object):
  app_id = attr.ib()
  namespace = attr.ib()
  gae_index_name = attr.ib()
  collection = attr.ib()
  docs_number = attr.ib()
  heap_usage = attr.ib()
  size_in_bytes = attr.ib()
  fields = attr.ib()
  facets = attr.ib()
  grouped_fields = attr.ib()
  grouped_facet_indexes = attr.ib()


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class SolrSchemaFieldInfo(object):
  class Type(object):
    # GAE Field types:
    TEXT_FIELD = "txt"
    # HTML_FIELD =  TODO: define HTML field type in Solr
    ATOM_FIELD = "atom"
    NUMBER_FIELD = "number"
    DATE_FIELD = "date"          # Date range for search queries
    DATE_MS_FIELD = "date_ms"    # Corresponding timestamp for sorting
    GEO_FIELD = "geo"

    # GAE Facet types:
    ATOM_FACET_INDEX = "atom_facet"    # Lowercased facet value in Solr
    ATOM_FACET = "atom_facet_value"    # Original facet value in Solr
    NUMBER_FACET = "number_facet"

    @classmethod
    def is_facet(cls, type_):
      return type_ in [cls.ATOM_FACET_INDEX, cls.ATOM_FACET, cls.NUMBER_FACET]

    @classmethod
    def is_facet_index(cls, type_):
      return type_ in [cls.ATOM_FACET_INDEX, cls.NUMBER_FACET]

    @classmethod
    def is_facet_value(cls, type_):
      return type_ in [cls.ATOM_FACET, cls.NUMBER_FACET]

  solr_name = attr.ib()
  gae_name = attr.ib()
  type = attr.ib()
  language = attr.ib()
  docs_number = attr.ib()


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class SolrQueryOptions(object):
  query_string = attr.ib()
  query_fields = attr.ib()
  def_type = attr.ib()


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class SolrSearchResult(object):
  num_found = attr.ib()
  documents = attr.ib()
  cursor = attr.ib()
  facet_results = attr.ib()
  stats_results = attr.ib()
