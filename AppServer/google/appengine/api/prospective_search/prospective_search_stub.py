#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#




"""In-memory persistent prospective_search API stub for dev_appserver."""







import base64
import bisect
import itertools
import operator
import os
import re
import sys
import time
import urllib


import cPickle as pickle

from collections import deque
from google.appengine.api import apiproxy_stub
from google.appengine.api.prospective_search import error_pb
from google.appengine.api.prospective_search import prospective_search_pb
from google.appengine.api.taskqueue import taskqueue_service_pb
from google.appengine.runtime import apiproxy_errors

def ValidateSubscriptionId(sub_id):
  if sub_id == '':
    RaiseBadRequest('Invalid subscription id.')

def ValidateTopic(topic):
  if topic == '':
    RaiseBadRequest('Invalid topic.')

def ValidateQuery(query):
  if query == '':
    RaiseBadRequest('Invalid query.')

def RaiseBadRequest(message):
  raise apiproxy_errors.ApplicationError(error_pb.Error.BAD_REQUEST, message)


class _TrueExpr(object):
  """Trivially true callable. Should generally use _EMPTY singleton."""

  def __call__(self, doc):
    return True

  def __str__(self):
    return '(t)'


_EMPTY = _TrueExpr()


class _Not(object):
  """NOT callable."""

  def __init__(self, expr):
    self.expr = expr

  def __call__(self, doc):
    return not self.expr(doc)

  def __str__(self):
    return '(n %s)' % str(self.expr)


def _MakeNot(expr):
  if expr is _EMPTY:
    return _EMPTY
  return _Not(expr)


class _AndOr(object):
  """AND/OR callable."""

  def __init__(self, left, right, is_and=True):
    self.left = left
    self.right = right
    self.is_and = is_and

  def __call__(self, doc):
    if self.is_and:
      return self.left(doc) and self.right(doc)
    else:
      return self.left(doc) or self.right(doc)

  def __str__(self):
    if self.is_and:
      name = 'a'
    else:
      name = 'o'
    return '(%s %s %s)' % (name, str(self.left), str(self.right))


def _MakeAndOr(left, right, is_and=True):
  if right is _EMPTY:
    return left
  return _AndOr(left, right, is_and=is_and)


class _NumberOp(object):
  """Basic numeric callable."""

  SYMBOL_TO_OPERATOR = {
      '<': operator.lt,
      '<=': operator.le,
      '=<': operator.le,
      ':': operator.eq,
      '=': operator.eq,
      '==': operator.eq,
      '>=': operator.ge,
      '=>': operator.ge,
      '>': operator.gt,
      }

  def __init__(self, field, sym, target):
    self.field = field
    self.sym = sym
    self.target = target

  def __call__(self, doc):
    value = doc.get(self.field, [])
    for item in value:
      if self.SYMBOL_TO_OPERATOR[self.sym](item, self.target):
        return True
    return False

  def __str__(self):
    return '(%s:%s %f)' % (self.sym, self.field, self.target)

  @classmethod
  def IsSymbol(cls, sym):
    return sym in cls.SYMBOL_TO_OPERATOR

  @staticmethod
  def IsNumber(num):
    try:
      float(num)
    except ValueError:
      return False
    return True


class _RangeOp(object):
  """Number in range callable."""

  def __init__(self, field, left, right):
    self.field = field
    self.left = left
    self.right = right

  def __call__(self, doc):
    value = doc.get(self.field, [])
    for item in value:
      if self.left <= item and item <= self.right:
        return True
    return False

  def __str__(self):
    return '(=:%s %f..%f)' % (self.field, self.left, self.right)


class _InField(object):
  """Text in field callable.

  Functions by swapping the field passed to __init__ into the special '' field.
  """

  def __init__(self, field, expr):
    self.field = field
    self.expr = expr

  def __call__(self, doc):

    old_field = doc['']
    doc[''] = doc.get(self.field, [])
    ret = self.expr(doc)
    doc[''] = old_field
    return ret

  def __str__(self):
    return '(infield:%s %s)' % (self.field, str(self.expr))


class _TextHas(object):
  """Text in default field callable.

  Usually used in conjunction with _InField.
  """

  def __init__(self, text):
    self.text = text
    self.regex = re.compile(ur'\b%s\b' % re.escape(unicode(text, 'utf-8')),
                            re.UNICODE)

  def __call__(self, doc):
    for item in doc['']:
      try:
        if self.regex.search(item):
          return True
      except TypeError:
        pass
    return False

  def __str__(self):
    if ' ' in self.text:
      return '"%s"' % self.text
    return self.text


class _BoolIs(object):
  """Boolean field has specified value. """

  def __init__(self, field, value):
    self.field = field
    if (value == 'true'):
      self.value = True
    else:

      self.value = False

  def __call__(self, doc):
    if self.value in doc.get(self.field, []):
      return True
    return False

  def __str__(self):
    return '(BoolIs:%s %s)' % (self.field, self.value)


class _Parser(object):
  """Parse vanillia query to expression callable."""




  LEX_RE = re.compile(r"""
      \s*  # whitespace
      (-?\d*\.?\d+  # number
      |[^\s(){}:|=<>"\.-][^\s(){}:|=<>"]*  # term
      |"(?:\\.|[^"])*"?  # phrase
      |[(){}:|-]|[=<>]+|\.\.\.?)  # symbol
      """, re.VERBOSE)

  FIELD_RE = re.compile(r'[a-zA-Z_]')

  def __init__(self, vanilla_query, schema):
    """Init.

    Args:
      vanilla_query: string vanilla query
    """
    self.src = deque(self.LEX_RE.findall(vanilla_query))
    self.src.append(None)
    self.token = self.src.popleft()
    self.schema = schema

  def ParseQuery(self):
    """Parse the entire vanilla_query."""
    return self._ParseCompound('')

  def _ParseExpr(self):
    """Parse an expression."""
    while (self.token == ')' or self.token == '}' or
           self.token == 'AND' or self.token == 'OR' or self.token == '|'):
      self.token = self.src.popleft()
    if len(self.src) >= 2 and self.FIELD_RE.match(self.token):
      field = self.token
      if (len(self.src) >= 4 and self.src[0] in [':', '=', '=='] and
          _NumberOp.IsNumber(self.src[1]) and self.src[2] in ['..', '...'] and
          _NumberOp.IsNumber(self.src[3])):
        self.src.popleft()
        left = float(self.src.popleft())
        self.src.popleft()
        right = float(self.src.popleft())
        self.token = self.src.popleft()
        return _RangeOp(field, left, right)
      elif _NumberOp.IsSymbol(self.src[0]) and _NumberOp.IsNumber(self.src[1]):
        sym = self.src.popleft()
        number = float(self.src.popleft())
        self.token = self.src.popleft()
        return _NumberOp(field, sym, number)
      elif (self.src[0] in [':', '='] and
            prospective_search_pb.SchemaEntry.BOOLEAN
             == self.schema.get(field, None)):
        self.src.popleft()
        bool_value = self.src.popleft()
        self.token = self.src.popleft()
        return _BoolIs(field, bool_value)
      elif self.src[0] in [':', '=']:
        self.token = self.src.popleft()
        self.token = self.src.popleft()
        return _InField(field, self._ParseCompoundOrLiteral())
    return self._ParseCompoundOrLiteral()

  def _ParseCompoundOrLiteral(self):
    """Parse a compound or a text literal."""
    if self.token is None:
      return _EMPTY
    last_token = self.token
    self.token = self.src.popleft()
    if last_token == '(':
      return self._ParseCompound(')')
    elif last_token == '{':
      return self._ParseCompound('}')
    elif last_token == '-' or last_token == 'NOT':
      return _MakeNot(self._ParseExpr())
    else:
      if last_token[0] == '"':
        last_token = last_token[1:]
        if len(last_token) >= 1 and last_token[-1] == '"':
          last_token = last_token[:-1]
      return _TextHas(last_token)

  def _ParseCompound(self, end_token):
    """Parse a compound (AND/OR).

    Args:
      end_token: the token that ends this compound, usually ')' or '}'
    """
    if self.token is None:
      return _EMPTY
    elif (self.token == end_token or self.token == 'AND' or
          self.token == 'OR' or self.token == '|'):
      self.token = self.src.popleft()
      return _EMPTY
    else:
      left = self._ParseExpr()
      is_and = end_token != '}'
      if self.token == 'AND':
        self.token = self.src.popleft()
      elif self.token == 'OR' or self.token == '|':
        is_and = False
        self.token = self.src.popleft()
      return _MakeAndOr(left,
                        self._ParseCompound(end_token),
                        is_and=is_and)


class ProspectiveSearchStub(apiproxy_stub.APIProxyStub):
  """Python only Prospective Search service stub."""

  def __init__(self, prospective_search_path, taskqueue_stub,
               service_name='matcher', openfile=open):
    """Initializer.

    Args:
      prospective_search_path: path for file that persists subscriptions.
      taskqueue_stub: taskqueue service stub for returning results.
      service_name: Service name expected for all calls.
    """
    super(ProspectiveSearchStub, self).__init__(service_name)
    self.prospective_search_path = prospective_search_path
    self.taskqueue_stub = taskqueue_stub
    self.topics = {}
    self.topics_parsed = {}
    self.topics_schema = {}
    if os.path.isfile(self.prospective_search_path):
      stream = openfile(self.prospective_search_path, 'rb')

      stream.seek(0, os.SEEK_END)
      if stream.tell() != 0:
        stream.seek(0)
        self.topics, self.topics_schema = pickle.load(stream)
        for topic, topic_subs in self.topics.iteritems():
          for sub_id, entry in topic_subs.items():
            vanilla_query, _ = entry
            schema = self.topics_schema.setdefault(topic, {})
            parsed = _Parser(vanilla_query, schema).ParseQuery()
            topic_parsed_subs = self.topics_parsed.setdefault(topic, {})
            topic_parsed_subs[sub_id] = parsed

  def _Write(self, openfile=open):
    """Persist subscriptions."""
    persisted = openfile(self.prospective_search_path, 'wb')
    pickle.dump((self.topics, self.topics_schema), persisted)
    persisted.close()

  def _Get_Schema(self, schema_entries):
    """Returns dictionary mapping field names to SchemaEntry types.

    Args:
      schema_entries: list of SchemaEntry entries.
    """
    schema = {}
    for entry in schema_entries:
      schema[entry.name()] = entry.type()
    return schema

  def _Dynamic_Subscribe(self, request, response):
    """Subscribe a query.

    Args:
      request: SubscribeRequest
      response: SubscribeResponse
    """
    ValidateSubscriptionId(request.sub_id())
    ValidateTopic(request.topic())
    ValidateQuery(request.vanilla_query())
    schema = self._Get_Schema(request.schema_entry_list())
    self.topics_schema[request.topic()] = schema
    parsed = _Parser(request.vanilla_query(), schema).ParseQuery()
    if (request.lease_duration_sec() == 0):
      expires = time.time() + 0xffffffff
    else:
      expires = time.time() + request.lease_duration_sec()
    topic_subs = self.topics.setdefault(request.topic(), {})
    topic_subs[request.sub_id()] = (request.vanilla_query(), expires)
    topic_parsed_subs = self.topics_parsed.setdefault(request.topic(), {})
    topic_parsed_subs[request.sub_id()] = parsed
    self._Write()


  def _Dynamic_Unsubscribe(self, request, response):
    """Unsubscribe a query.

    Args:
      request: UnsubscribeRequest
      response: UnsubscribeResponse
    """
    ValidateSubscriptionId(request.sub_id())
    ValidateTopic(request.topic())
    try:
      del self.topics[request.topic()][request.sub_id()]
      del self.topics_parsed[request.topic()][request.sub_id()]
    except KeyError:
      pass
    self._Write()

  def _ExpireSubscriptions(self):
    """Remove expired subscriptions.
    """
    now = time.time()
    empty_topics = []
    for topic, topic_subs in self.topics.iteritems():
      expired_sub_ids = []
      for sub_id, entry in topic_subs.iteritems():
        _, expires = entry
        if expires < now:
          expired_sub_ids.append(sub_id)
      for sub_id in expired_sub_ids:
        del topic_subs[sub_id]
        del self.topics_parsed[topic][sub_id]
      if len(topic_subs) == 0:
        empty_topics.append(topic)
    for topic in empty_topics:
      del self.topics[topic]
      del self.topics_parsed[topic]

  def _Dynamic_ListSubscriptions(self, request, response):
    """List subscriptions.

    Args:
      request: ListSubscriptionsRequest
      response: ListSubscriptionsResponse
    """
    ValidateTopic(request.topic())
    self._ExpireSubscriptions()
    topic_subs = self.topics.get(request.topic(), {})
    sub_ids = topic_subs.keys()
    sub_ids.sort()
    start = bisect.bisect_left(sub_ids, request.subscription_id_start())
    sub_ids = sub_ids[start:start + request.max_results()]
    for sub_id in sub_ids:
      vanilla_query, expires = topic_subs[sub_id]
      if request.has_expires_before() and expires > request.expires_before():
        continue
      record = response.add_subscription()
      record.set_id(sub_id)
      record.set_vanilla_query(vanilla_query)
      record.set_expiration_time_sec(expires)
      record.set_state(prospective_search_pb.SubscriptionRecord.OK)

  def _Dynamic_ListTopics(self, request, response):
    """List topics.

    Args:
      request: ListTopicsRequest
      response: ListTopicsResponse
    """
    topics = self.topics.keys()
    topics.sort()
    if request.has_topic_start():
      start = bisect.bisect_left(topics, request.topic_start())
    else:
      start = 0

    iter_topics = topics[start:start + request.max_results()]
    for topic in iter_topics:
      response.topic_list().append(topic)

  def _DeliverMatches(self, subscriptions, match_request):
    """Deliver list of subscriptions as batches using taskqueue.

    Args:
      subcriptions: list of subscription ids
      match_request: MatchRequest
    """
    parameters = {'topic': match_request.topic()}
    if match_request.has_result_python_document_class():
      python_document_class = match_request.result_python_document_class()
      parameters['python_document_class'] = python_document_class
      parameters['document'] = base64.urlsafe_b64encode(
          match_request.document().Encode())
    if match_request.has_result_key():
      parameters['key'] = match_request.result_key()
    taskqueue_request = taskqueue_service_pb.TaskQueueBulkAddRequest()
    batch_size = match_request.result_batch_size()
    for i in xrange(0, len(subscriptions), batch_size):
      add_request = taskqueue_request.add_add_request()
      add_request.set_queue_name(match_request.result_task_queue())
      add_request.set_task_name('')
      add_request.set_eta_usec(0)
      add_request.set_url(match_request.result_relative_url())
      add_request.set_description('prospective_search::matches')
      header = add_request.add_header()
      header.set_key('content-type')
      header.set_value('application/x-www-form-urlencoded; charset=utf-8')
      parameters['results_count'] = len(subscriptions)
      parameters['results_offset'] = i
      parameters['id'] = subscriptions[i:i+batch_size]
      add_request.set_body(urllib.urlencode(parameters, doseq=True))
    taskqueue_response = taskqueue_service_pb.TaskQueueBulkAddResponse()
    self.taskqueue_stub._Dynamic_BulkAdd(taskqueue_request, taskqueue_response)

  def _Dynamic_Match(self, request, response):
    """Match a document.

    Args:
      request: MatchRequest
      response: MatchResponse
    """
    self._ExpireSubscriptions()
    doc = {'': []}
    properties = itertools.chain(request.document().property_list(),
                                 request.document().raw_property_list())
    for prop in properties:

      doc.setdefault(prop.name(), [])
      if prop.value().has_int64value():
        value = prop.value().int64value()

        if (value < 2**32) and (value >= -2**32):
          doc[prop.name()].append(prop.value().int64value())
      elif prop.value().has_stringvalue():

        unicode_value = unicode(prop.value().stringvalue(), 'utf-8')
        doc[prop.name()].append(unicode_value)

        doc[''].append(unicode_value)
      elif prop.value().has_doublevalue():
        doc[prop.name()].append(prop.value().doublevalue())
      elif prop.value().has_booleanvalue():
        doc[prop.name()].append(prop.value().booleanvalue())

    matches = []
    topic_subs = self.topics_parsed.get(request.topic(), {})
    for sub_id, parsed in topic_subs.iteritems():
      if parsed(doc):
        matches.append(sub_id)
    if matches:
      self._DeliverMatches(matches, request)
