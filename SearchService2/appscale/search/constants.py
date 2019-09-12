# Max amount of time to wait for response from Solr (in seconds).
from appscale.search.protocols import search_pb2

SOLR_TIMEOUT = 60

# Max amount of time to wait before commit updates (in milliseconds).
SOLR_COMMIT_WITHIN = 0

# Name of Solr configs set for appscale collections.
APPSCALE_CONFIG_SET_NAME = 'appscale_search_api_config'

# Prefix for all Solr-related nodes in Zookeeper.
SOLR_ZK_ROOT = '/solr'

# The ZooKeeper path where a list of active search servers is stored.
SEARCH_SERVERS_NODE = '/appscale/search/live_nodes'

# The ZooKeeper path where a replication configuration is stored.
SERVICE_SETTINGS_NODE = '/appscale/search/service_settings'

SUPPORTED_LANGUAGES = [
  'en',
  'ar',
  'bg',
  'ca',
  'cjk',
  'cz',
  'da',
  'de',
  'el',
  'es',
  'eu',
  'fa',
  'fi',
  'fr',
  'ga',
  'gl',
  'hi',
  'hu',
  'hy',
  'id',
  'it',
  'ja',
  'ko',
  'lv',
  'nl',
  'no',
  'pt',
  'ro',
  'ru',
  'sv',
  'th',
  'tr'
]


class SearchServiceError(Exception):
  def __init__(self, error_code, error_detail, search_api_response=None):
    self.error_code = error_code
    self.error_name = search_pb2.SearchServiceError.ErrorCode.keys()[error_code]
    self.error_detail = error_detail
    self.search_api_response = search_api_response
    msg = '{}: {}'.format(self.error_name, error_detail)
    super(SearchServiceError, self).__init__(msg)


class InternalError(SearchServiceError):
  def __init__(self, message):
    super(InternalError, self).__init__(
      error_code=search_pb2.SearchServiceError.INTERNAL_ERROR,
      error_detail=message
    )


class InvalidRequest(SearchServiceError):
  def __init__(self, message):
    super(InvalidRequest, self).__init__(
      error_code=search_pb2.SearchServiceError.INVALID_REQUEST,
      error_detail=message
    )


class SolrError(InternalError):
  """ Should be raised if any Solr-related error occurred"""


class SolrIsNotReachable(SolrError):
  """ Should be raised when there are no Solr live nodes. """


class SolrClientError(SolrError):
  """ Should be raised when Solr responds with client error. """


class SolrServerError(SolrError):
  """ Should be raised when Solr responds with server error. """


class NotConfiguredError(InternalError):
  """ Search is not configured. """


class UnknownFieldTypeException(InternalError):
  """ Unknown Field type """


class UnknownFacetTypeException(InternalError):
  """ Unknown Facet type """


class ParsingError(ValueError):
  """ Search query parsing failed """
