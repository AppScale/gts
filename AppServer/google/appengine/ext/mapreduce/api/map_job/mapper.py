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





class Mapper(object):
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

  def begin_shard(self, ctx):
    """Called at the beginning of a shard.

    This method may be called more than once due to slice retry.
    Make it idempotent.

    Args:
      ctx: map_job.ShardContext object.
    """
    pass

  def end_shard(self, ctx):
    """Called at the end of a shard.

    This method may be called more than once due to slice retry.
    Make it idempotent.

    If shard execution error out before reaching the end, this method
    won't be called.

    Args:
      ctx: map_job.ShardContext object.
    """
    pass

  def begin_slice(self, ctx):
    """Called at the beginning of a slice.

    This method may be called more than once due to slice retry.
    Make it idempotent.

    Args:
      ctx: map_job.SliceContext object.
    """
    pass

  def end_slice(self, ctx):
    """Called at the end of a slice.

    This method may be called more than once due to slice retry.
    Make it idempotent.

    If slice execution error out before reaching the end, this method
    won't be called.

    Args:
      ctx: map_job.SliceContext object.
    """
    pass


  def __call__(self, ctx, val):
    """Invoked once on every value yielded by input reader.

    Under normal cases, this is invoked exactly once on each input value.
    But upon slice retry, some input value may have been processed by
    the previous attempt. If your logic is idempotent (e.g write to
    datastore by key), this is OK. If your logic is not (e.g. append to
    a cloud storage file), slice retry can create duplicated entries.
    Work is in progress to remove these duplicates.

    Args:
      ctx: context.Context object.
      val: a single yielded value from your input reader. The exact type
        depends on the input reader. For example, some may yield a single
        datastore entity, others may yield a (int, str) tuple.

    Yields:
      Each value yielded is fed into output writer.
      Thus each value must have the type expected by your output writer.

    Returns:
      If there is nothing to yield, return None.
    """
    return
