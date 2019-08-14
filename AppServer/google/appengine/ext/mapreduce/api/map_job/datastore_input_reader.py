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
"""Datastore Input Reader implementation for the map_job API."""
import logging

from google.appengine.ext.mapreduce import datastore_range_iterators as db_iters
from google.appengine.ext.mapreduce import errors
from google.appengine.ext.mapreduce.api.map_job import abstract_datastore_input_reader




class DatastoreInputReader(abstract_datastore_input_reader
                           .AbstractDatastoreInputReader):
  """Iterates over an entity kind and yields datastore.Entity."""

  _KEY_RANGE_ITER_CLS = db_iters.KeyRangeEntityIterator

  @classmethod
  def validate(cls, job_config):
    """Inherit docs."""
    super(DatastoreInputReader, cls).validate(job_config)
    params = job_config.input_reader_params
    entity_kind = params[cls.ENTITY_KIND_PARAM]

    if "." in entity_kind:
      logging.warning(
          ". detected in entity kind %s specified for reader %s."
          "Assuming entity kind contains the dot.",
          entity_kind, cls.__name__)

    if cls.FILTERS_PARAM in params:
      filters = params[cls.FILTERS_PARAM]
      for f in filters:
        if f[1] != "=":
          raise errors.BadReaderParamsError(
              "Only equality filters are supported: %s", f)
