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
"""Map job execution context."""

import logging




class JobContext(object):
  """Context for map job."""

  def __init__(self, job_config):
    """Init.

    Read only properties:
      job_config: map_job.JobConfig for the job.

    Args:
      job_config: map_job.JobConfig.
    """
    self.job_config = job_config


class ShardContext(object):
  """Context for a shard."""

  def __init__(self, job_context, shard_state):
    """Init.

    The signature of __init__ is subject to change.

    Read only properties:
      job_context: JobContext object.
      id: str. of format job_id-shard_number.
      number: int. shard number. 0 indexed.
      attempt: int. The current attempt at executing this shard.
        Starting at 1.

    Args:
      job_context: map_job.JobConfig.
      shard_state: model.ShardState.
    """
    self.job_context = job_context
    self.id = shard_state.shard_id
    self.number = shard_state.shard_number
    self.attempt = shard_state.retries + 1
    self._state = shard_state


  def incr(self, counter_name, delta=1):
    """Changes counter by delta.

    Args:
      counter_name: the name of the counter to change. str.
      delta: int.
    """
    self._state.counters_map.increment(counter_name, delta)


class SliceContext(object):
  """Context for map job."""

  def __init__(self, shard_context, shard_state, tstate):
    """Init.

    The signature of __init__ is subject to change.

    Read only properties:
      job_context: JobContext object.
      shard_context: ShardContext object.
      number: int. slice number. 0 indexed.
      attempt: int. The current attempt at executing this slice.
        starting at 1.

    Args:
      shard_context: map_job.JobConfig.
      shard_state: model.ShardState.
      tstate: model.TransientShardstate.
    """
    self._tstate = tstate
    self.job_context = shard_context.job_context
    self.shard_context = shard_context
    self.number = shard_state.slice_id
    self.attempt = shard_state.slice_retries + 1

  def incr(self, counter_name, delta=1):
    """See shard_context.count."""
    self.shard_context.incr(counter_name, delta)

  def emit(self, value):
    """Emits a value to output writer.

    Args:
      value: a value of type expected by the output writer.
    """
    if not self._tstate.output_writer:
      logging.error("emit is called, but no output writer is set.")
      return
    self._tstate.output_writer.write(value)
