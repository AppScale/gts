"""Prospective Search for NDB.

This reimplements all of the standard APIs with the following changes:

- A document_class argument must be an NDB Model class.
- A document must be an NDB Model instance.
- get_document() always returns an NDB Model instance.

The exceptions and public constants exported by the standard module
are re-exported here.
"""

# TODO: Ideally prospective search would support NDB natively, or
# support protobufs natively (in addition to ENTITY and MODEL).
# TODO: Should we try to support async calls as well?  That can't be
# done without rewriting the standard prospective_search API module.

import base64

from .google_imports import datastore
from .google_imports import datastore_types
from .google_imports import prospective_search
from .google_imports import prospective_search_pb
from .google_imports import entity_pb

from . import model
from . import tasklets

# Re-export constants and exceptions from prospective_search.
DEFAULT_RESULT_BATCH_SIZE = prospective_search.DEFAULT_RESULT_BATCH_SIZE
DEFAULT_LEASE_DURATION_SEC = prospective_search.DEFAULT_LEASE_DURATION_SEC
DEFAULT_LIST_SUBSCRIPTIONS_MAX_RESULTS = \
    prospective_search.DEFAULT_LIST_SUBSCRIPTIONS_MAX_RESULTS
DEFAULT_LIST_TOPICS_MAX_RESULTS = \
    prospective_search.DEFAULT_LIST_TOPICS_MAX_RESULTS
Error = prospective_search.Error
DocumentTypeError = prospective_search.DocumentTypeError
QuerySyntaxError = prospective_search.QuerySyntaxError
SchemaError = prospective_search.SchemaError
SubscriptionDoesNotExist = prospective_search.SubscriptionDoesNotExist
TopicNotSpecified = prospective_search.TopicNotSpecified
SubscriptionState = prospective_search.SubscriptionState
subscription_state_name = prospective_search.subscription_state_name

__all__ = ['get_document',
           'get_subscription',
           'list_subscriptions',
           'list_topics',
           'match',
           'unsubscribe',
           'subscribe',
           'subscription_state_name',
           'DEFAULT_RESULT_BATCH_SIZE',
           'DEFAULT_LEASE_DURATION_SEC',
           'DEFAULT_LIST_SUBSCRIPTIONS_MAX_RESULTS',
           'DEFAULT_LIST_TOPICS_MAX_RESULTS',
           'DocumentTypeError',
           'Error',
           'QuerySyntaxError',
           'SchemaError',
           'SubscriptionDoesNotExist',
           'SubscriptionState',
           'TopicNotSpecified']

_doc_class = prospective_search_pb.MatchRequest  # For testing get_document().

_MODEL_TYPE_TO_PYTHON_TYPE = {
  model.StringProperty: str,
  model.IntegerProperty: int,
  model.BooleanProperty: bool,
  model.FloatProperty: float,
  model.TextProperty: str,
  }


def _add_schema_entry(prop_class, name, schema):
  """Add single entry to SchemaEntries by invoking add_entry."""
  python_type = _MODEL_TYPE_TO_PYTHON_TYPE.get(prop_class, None)
  if not python_type:
    return
  if python_type not in schema:
    schema[python_type] = [name]
  else:
    schema[python_type].append(name)


def _model_to_entity_schema(document_class):
  """Produce schema from NDB Model class."""
  schema = {}
  for name, prop in document_class._properties.iteritems():
    _add_schema_entry(prop.__class__, name, schema)
  return schema


def _get_document_topic(document_class, topic):
  assert issubclass(document_class, model.Model)
  if topic:
    return topic
  return document_class._get_kind()


def subscribe(document_class,
              query,
              sub_id,
              schema=None,
              topic=None,
              lease_duration_sec=DEFAULT_LEASE_DURATION_SEC):
  """Subscribe a query."""
  assert schema is None
  topic = _get_document_topic(document_class, topic)
  schema = _model_to_entity_schema(document_class)
  return prospective_search.subscribe(
    datastore.Entity,
    query,
    sub_id,
    schema=schema,
    topic=topic,
    lease_duration_sec=lease_duration_sec)


def unsubscribe(document_class, sub_id, topic=None):
  topic = _get_document_topic(document_class, topic)
  prospective_search.unsubscribe(datastore.Entity, sub_id, topic=topic)


def get_subscription(document_class, sub_id, topic=None):
  """Get subscription information."""
  topic = _get_document_topic(document_class, topic)
  return prospective_search.get_subscription(datastore.Entity, sub_id,
                                             topic=topic)


def list_subscriptions(document_class,
                       sub_id_start='',
                       topic=None,
                       max_results=DEFAULT_LIST_SUBSCRIPTIONS_MAX_RESULTS,
                       expires_before=None):
  """List subscriptions on a topic."""
  topic = _get_document_topic(document_class, topic)
  return prospective_search.list_subscriptions(
    datastore.Entity,
    sub_id_start=sub_id_start,
    topic=topic,
    max_results=max_results,
    expires_before=expires_before)


list_topics = prospective_search.list_topics


def match(document,
          topic=None,
          result_key=None,
          result_relative_url='/_ah/prospective_search',
          result_task_queue='default',
          result_batch_size=DEFAULT_RESULT_BATCH_SIZE,
          result_return_document=True):
  """Match document with all subscribed queries on specified topic."""
  # Convert document to datastore.Entity.
  topic = _get_document_topic(document.__class__, topic)
  pb = document._to_pb()
  entity = datastore.Entity('temp-kind').FromPb(pb)
  return prospective_search.match(
    entity,
    topic=topic,
    result_key=result_key,
    result_relative_url=result_relative_url,
    result_task_queue=result_task_queue,
    result_batch_size=result_batch_size,
    result_return_document=result_return_document)


def get_document(request):
  """Decodes document from prospective_search result POST request.

  Args:
    request: received POST request

  Returns:
    document: original NDB Model document from match call.

  Raises:
    DocumentTypeError: if document class is not recognized.
  """
  doc_class = request.get('python_document_class')
  if not doc_class:
    return None
  entity = entity_pb.EntityProto()
  entity.ParseFromString(base64.urlsafe_b64decode(
      request.get('document').encode('utf-8')))
  doc_class = int(doc_class)
  ctx = tasklets.get_context()
  adapter = ctx._conn.adapter
  return adapter.pb_to_entity(entity)
