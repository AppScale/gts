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
"""Input Reader interface for map job."""

from . import shard_life_cycle
from google.appengine.ext.mapreduce import errors
from google.appengine.ext.mapreduce import json_util





class InputReader(shard_life_cycle._ShardLifeCycle, json_util.JsonMixin):
  """Abstract base class for input readers.

  InputReader's lifecycle:
  1. validate() is called to validate JobConfig.
  2. split_input is called to split inputs based on map_job.JobConfig.
     The class method creates a set of InputReader instances.
  3. beging_shard/end_shard/begin_slice/end_slice are called at the time
     implied by the names.
  4. next() is called by each shard on each instance. The output of next()
     is fed into JobConfig.mapper instance.
  5. to_json()/from_json() are used to persist reader's state across multiple
     slices.
  """

  def __iter__(self):
    return self

  def next(self):
    """Returns the next input from this input reader.

    Returns:
      The next input read by this input reader. The return value is
      fed into mapper.

    Raises:
      StopIteration when no more item is left.
    """
    raise NotImplementedError("next() not implemented in %s" % self.__class__)

  @classmethod
  def from_json(cls, input_shard_state):
    """Creates an instance of the InputReader for the given input shard state.

    Args:
      input_shard_state: The InputReader state as returned by to_json.

    Returns:
      An instance of the InputReader that can resume iteration.
    """
    raise NotImplementedError("from_json() not implemented in %s" % cls)

  def to_json(self):
    """Returns input reader state for the remaining inputs.

    Returns:
      A json-serializable state for the InputReader.
    """
    raise NotImplementedError("to_json() not implemented in %s" %
                              self.__class__)

  @classmethod
  def split_input(cls, job_config):
    """Returns an iterator of input readers.

    This method returns a container of input readers,
    one for each shard. The container must have __iter__ defined.
    http://docs.python.org/2/reference/datamodel.html#object.__iter__

    This method should try to split inputs among readers evenly.

    Args:
      job_config: an instance of map_job.JobConfig.

    Returns:
      An iterator of input readers.
    """
    raise NotImplementedError("split_input() not implemented in %s" % cls)

  @classmethod
  def validate(cls, job_config):
    """Validates relevant parameters.

    This method can validate fields which it deems relevant.

    Args:
      job_config: an instance of map_job.JobConfig.

    Raises:
      errors.BadReaderParamsError: required parameters are missing or invalid.
    """
    if job_config.input_reader_cls != cls:
      raise errors.BadReaderParamsError(
          "Expect input reader class %r, got %r." %
          (cls, job_config.input_reader_cls))

