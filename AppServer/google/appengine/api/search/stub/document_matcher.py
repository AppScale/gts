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




"""Document matcher for Full Text Search API stub.

DocumentMatcher provides an approximation of the Full Text Search API's query
matching.
"""



from google.appengine.datastore import document_pb

from google.appengine._internal.antlr3 import tree
from google.appengine.api.search import query_parser
from google.appengine.api.search import QueryParser
from google.appengine.api.search import search_util
from google.appengine.api.search.stub import simple_tokenizer
from google.appengine.api.search.stub import tokens


class DocumentMatcher(object):
  """A class to match documents with a query."""

  def __init__(self, query, inverted_index):
    self._query = query
    self._inverted_index = inverted_index
    self._parser = simple_tokenizer.SimpleTokenizer()

  def _PostingsForToken(self, token):
    """Returns the postings for the token."""
    return self._inverted_index.GetPostingsForToken(token)

  def _PostingsForFieldToken(self, field, value):
    """Returns postings for the value occurring in the given field."""
    value = simple_tokenizer.NormalizeString(value)
    return self._PostingsForToken(
        tokens.Token(chars=value, field_name=field))

  def _MatchPhrase(self, field, match, document):
    """Match a textual field with a phrase query node."""
    field_text = field.value().string_value()
    phrase_text = query_parser.GetPhraseQueryNodeText(match)


    if field.value().type() == document_pb.FieldValue.ATOM:
      return (field_text == phrase_text)

    phrase = self._parser.TokenizeText(phrase_text)
    field_text = self._parser.TokenizeText(field_text)
    if not phrase:
      return True
    posting = None
    for post in self._PostingsForFieldToken(field.name(), phrase[0].chars):
      if post.doc_id == document.id():
        posting = post
        break
    if not posting:
      return False

    def ExtractWords(token_list):
      return (token.chars for token in token_list)

    for position in posting.positions:




      match_words = zip(ExtractWords(field_text[position:]),
                        ExtractWords(phrase))
      if len(match_words) != len(phrase):
        continue


      match = True
      for doc_word, match_word in match_words:
        if doc_word != match_word:
          match = False

      if match:
        return True
    return False

  def _MatchTextField(self, field, match, document):
    """Check if a textual field matches a query tree node."""

    if (match.getType() in (QueryParser.TEXT, QueryParser.NAME) or
        match.getType() in search_util.NUMBER_QUERY_TYPES):

      if field.value().type() == document_pb.FieldValue.ATOM:
        return (field.value().string_value() ==
                query_parser.GetQueryNodeText(match))

      query_tokens = self._parser.TokenizeText(
          query_parser.GetQueryNodeText(match))


      if not query_tokens:
        return True




      if len(query_tokens) > 1:
        def QueryNode(token):
          return query_parser.CreateQueryNode(token.chars, QueryParser.TEXT)
        return all(self._MatchTextField(field, QueryNode(token), document)
                   for token in query_tokens)

      token_text = query_tokens[0].chars
      matching_docids = [
          post.doc_id for post in self._PostingsForFieldToken(
              field.name(), token_text)]
      return document.id() in matching_docids

    if match.getType() is QueryParser.PHRASE:
      return self._MatchPhrase(field, match, document)

    if match.getType() is QueryParser.CONJUNCTION:
      return all(self._MatchTextField(field, child, document)
                 for child in match.children)

    if match.getType() is QueryParser.DISJUNCTION:
      return any(self._MatchTextField(field, child, document)
                 for child in match.children)

    if match.getType() is QueryParser.NEGATION:
      return not self._MatchTextField(field, match.children[0], document)


    return False

  def _MatchDateField(self, field, match, document):
    """Check if a date field matches a query tree node."""


    return self._MatchComparableField(
        field, match, search_util.DeserializeDate,
        search_util.TEXT_QUERY_TYPES, document)


  def _MatchNumericField(self, field, match, document):
    """Check if a numeric field matches a query tree node."""
    return self._MatchComparableField(
        field, match, float, search_util.NUMBER_QUERY_TYPES, document)


  def _MatchComparableField(
      self, field, match, cast_to_type, query_node_types,
      document):
    """A generic method to test matching for comparable types.

    Comparable types are defined to be anything that supports <, >, <=, >=, ==
    and !=. For our purposes, this is numbers and dates.

    Args:
      field: The document_pb.Field to test
      match: The query node to match against
      cast_to_type: The type to cast the node string values to
      query_node_types: The query node types that would be valid matches
      document: The document that the field is in

    Returns:
      True iff the field matches the query.

    Raises:
      UnsupportedOnDevError: Raised when an unsupported operator is used, or
      when the query node is of the wrong type.
    """

    field_val = cast_to_type(field.value().string_value())

    op = QueryParser.EQ

    if match.getType() in query_node_types:
      try:
        match_val = cast_to_type(query_parser.GetQueryNodeText(match))
      except ValueError:
        return False
    elif match.children:
      op = match.getType()
      try:
        match_val = cast_to_type(
            query_parser.GetQueryNodeText(match.children[0]))
      except ValueError:
        return False
    else:
      return False

    if op is QueryParser.EQ:
      return field_val == match_val
    if op is QueryParser.NE:
      return field_val != match_val
    if op is QueryParser.GT:
      return field_val > match_val
    if op is QueryParser.GE:
      return field_val >= match_val
    if op is QueryParser.LT:
      return field_val < match_val
    if op is QueryParser.LE:
      return field_val <= match_val
    raise search_util.UnsupportedOnDevError(
        'Operator %s not supported for numerical fields on development server.'
        % match.getText())

  def _MatchField(self, field, match, document):
    """Check if a field matches a query tree.

    Args:
      field_query_node: Either a string containing the name of a field, a query
      node whose text is the name of the field, or a document_pb.Field.
      match: A query node to match the field with.
      document: The document to match.
    """

    if isinstance(field, (basestring, tree.CommonTree)):
      if isinstance(field, tree.CommonTree):
        field = field.getText()
      fields = search_util.GetAllFieldInDocument(document, field)
      return any(self._MatchField(f, match, document) for f in fields)

    if field.value().type() in search_util.TEXT_DOCUMENT_FIELD_TYPES:
      return self._MatchTextField(field, match, document)

    if field.value().type() in search_util.NUMBER_DOCUMENT_FIELD_TYPES:
      return self._MatchNumericField(field, match, document)

    if field.value().type() == document_pb.FieldValue.DATE:
      return self._MatchDateField(field, match, document)

    raise search_util.UnsupportedOnDevError(
        'Matching to field type of field "%s" (type=%d) is unsupported on '
        'dev server' % (field.name(), field.value().type()))

  def _MatchGlobal(self, match, document):
    for field in document.field_list():
      if self._MatchField(field.name(), match, document):
        return True
    return False

  def _CheckMatch(self, node, document):
    """Check if a document matches a query tree."""

    if node.getType() is QueryParser.CONJUNCTION:
      return all(self._CheckMatch(child, document) for child in node.children)

    if node.getType() is QueryParser.DISJUNCTION:
      return any(self._CheckMatch(child, document) for child in node.children)

    if node.getType() is QueryParser.NEGATION:
      return not self._CheckMatch(node.children[0], document)

    if node.getType() is QueryParser.RESTRICTION:
      field, match = node.children
      return self._MatchField(field, match, document)

    return self._MatchGlobal(node, document)

  def Matches(self, document):
    return self._CheckMatch(self._query, document)

  def FilterDocuments(self, documents):
    return (doc for doc in documents if self.Matches(doc))
