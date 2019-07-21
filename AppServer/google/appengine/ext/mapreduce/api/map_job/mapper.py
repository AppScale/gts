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
"""Interface for user defined mapper."""

from . import shard_life_cycle





class Mapper(shard_life_cycle._ShardLifeCycle):
  """Interface user's mapper should implement.

  Each shard initiates one instance. The instance is pickled
  and unpickled if a shard can't finish within the boundary of a single
  task (a.k.a a slice of the shard).

  Upon shard retry, a new instance will be used.

  Upon slice retry, the instance is unpickled from its state
  at the end of last slice.

  Be wary of the size of your mapper instances. They have to be persisted
  across slices.
  """

  def __init__(self):
    """Init.

    Init must not take additional arguments.
    """
    pass

  def __call__(self, slice_ctx, val):
    """Called for every value yielded by input reader.

    Normal case:
    This method is invoked exactly once on each input value. If an
    output writer is provided, this method can repeated call ctx.emit to
    write to output writer.

    On retries:
    Upon slice retry, some input value may have been processed by
    the previous attempt. This should not be a problem if your logic
    is idempotent (e.g write to datastore by key) but could be a
    problem otherwise (e.g write to cloud storage) and may result
    in duplicates.

    Advanced usage:
    Implementation can mimic combiner by tallying in-memory and
    and emit when memory is filling up or when end_slice() is called.
    CAUTION! Carefully tune to not to exceed memory limit or request deadline.

    Args:
      slice_ctx: map_job.SliceContext object.
      val: a single value yielded by your input reader. The type
        depends on the input reader. For example, some may yield a single
        datastore entity, others may yield a (int, str) tuple.
    """
    pass
