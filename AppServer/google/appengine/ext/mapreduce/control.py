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
















"""API for controlling MapReduce execution outside of MapReduce framework."""


__all__ = ["start_map"]



import logging
import google

from google.appengine.ext.mapreduce import base_handler
from google.appengine.ext.mapreduce import handlers
from google.appengine.ext.mapreduce import model


_DEFAULT_SHARD_COUNT = 8


def start_map(name,
              handler_spec,
              reader_spec,
              mapper_parameters,
              shard_count=_DEFAULT_SHARD_COUNT,
              output_writer_spec=None,
              mapreduce_parameters=None,
              base_path=None,
              queue_name=None,
              eta=None,
              countdown=None,
              hooks_class_name=None,
              _app=None,
              transactional=False,
              transactional_parent=None):
  """Start a new, mapper-only mapreduce.

  Args:
    name: mapreduce name. Used only for display purposes.
    handler_spec: fully qualified name of mapper handler function/class to call.
    reader_spec: fully qualified name of mapper reader to use
    mapper_parameters: dictionary of parameters to pass to mapper. These are
      mapper-specific and also used for reader initialization.
    shard_count: number of shards to create.
    mapreduce_parameters: dictionary of mapreduce parameters relevant to the
      whole job.
    base_path: base path of mapreduce library handler specified in app.yaml.
      "/mapreduce" by default.
    queue_name: executor queue name to be used for mapreduce tasks. If
      unspecified it will be the "default" queue or inherit the queue of
      the currently running request.
    eta: absolute time when the MR should execute. May not be specified
      if 'countdown' is also supplied. This may be timezone-aware or
      timezone-naive.
    countdown: time in seconds into the future that this MR should execute.
      Defaults to zero.
    hooks_class_name: fully qualified name of a hooks.Hooks subclass.
    transactional: specifies if job should be started as a part of already
      opened transaction.
    transactional_parent: specifies the entity which is already a part of
      transaction. Child entity will be used to store task payload if mapreduce
      specification is too big.

  Returns:
    mapreduce id as string.
  """
  if not shard_count:
    shard_count = _DEFAULT_SHARD_COUNT
  if base_path is None:
    base_path = base_handler._DEFAULT_BASE_PATH

  if mapper_parameters:
    mapper_parameters = dict(mapper_parameters)
  if mapreduce_parameters:
    mapreduce_parameters = dict(mapreduce_parameters)

  mapper_spec = model.MapperSpec(handler_spec,
                                 reader_spec,
                                 mapper_parameters,
                                 shard_count,
                                 output_writer_spec=output_writer_spec)

  if transactional and not transactional_parent:



    logging.error(
        "transactional_parent should be specified for transactional starts."
        "Your job will fail to start if mapreduce specification is too big.")

  return handlers.StartJobHandler._start_map(
      name,
      mapper_spec,
      mapreduce_parameters or {},
      base_path=base_path,
      queue_name=queue_name,
      eta=eta,
      countdown=countdown,
      hooks_class_name=hooks_class_name,
      _app=_app,
      transactional=transactional,
      parent_entity=transactional_parent)

