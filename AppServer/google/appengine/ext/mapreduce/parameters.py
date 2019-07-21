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
"""Parameters to control Mapreduce."""

__all__ = ["CONFIG_NAMESPACE",
           "config"]

import pickle

import google







try:
  from appengine_pipeline.src.pipeline import util as pipeline_util
except ImportError:
  pipeline_util = None

from google.appengine.api import lib_config

CONFIG_NAMESPACE = "mapreduce"






class _JobConfigMeta(type):
  """Metaclass that controls class creation."""

  _OPTIONS = "_options"
  _REQUIRED = "_required"

  def __new__(mcs, classname, bases, class_dict):
    """Creates a _Config class and modifies its class dict.

    Args:
      classname: name of the class.
      bases: a list of base classes.
      class_dict: original class dict.

    Returns:
      A new _Config class. The modified class will have two fields.
      _options field is a dict from option name to _Option objects.
      _required field is a set of required option names.
    """
    options = {}
    required = set()
    for name, option in class_dict.iteritems():
      if isinstance(option, _Option):
        options[name] = option
        if option.required:
          required.add(name)

    for name in options:
      class_dict.pop(name)
    class_dict[mcs._OPTIONS] = options
    class_dict[mcs._REQUIRED] = required
    cls = type.__new__(mcs, classname, bases, class_dict)


    if object not in bases:
      parent_options = {}

      for c in reversed(cls.__mro__):
        if mcs._OPTIONS in c.__dict__:

          parent_options.update(c.__dict__[mcs._OPTIONS])
        if mcs._REQUIRED in c.__dict__:
          required.update(c.__dict__[mcs._REQUIRED])
      for k, v in parent_options.iteritems():
        if k not in options:
          options[k] = v
    return cls


class _Option(object):
  """An option for _Config."""

  def __init__(self, kind, required=False, default_factory=None,
               can_be_none=False):
    """Init.

    Args:
      kind: type of the option.
      required: whether user is required to supply a value.
      default_factory: a factory, when called, returns the default value.
      can_be_none: whether value can be None.

    Raises:
      ValueError: if arguments aren't compatible.
    """
    if required and default_factory is not None:
      raise ValueError("No default_factory value when option is required.")
    self.kind = kind
    self.required = required
    self.default_factory = default_factory
    self.can_be_none = can_be_none


class _Config(object):
  """Root class for all per job configuration."""

  __metaclass__ = _JobConfigMeta

  def __init__(self, _lenient=False, **kwds):
    """Init.

    Args:
      _lenient: When true, no option is required.
      **kwds: keyword arguments for options and their values.
    """
    self._verify_keys(kwds, _lenient)
    self._set_values(kwds, _lenient)

  def _verify_keys(self, kwds, _lenient):
    keys = set()
    for k in kwds:
      if k not in self._options:
        raise ValueError("Option %s is not supported." % (k))
      keys.add(k)
    if not _lenient:
      missing = self._required - keys
      if missing:
        raise ValueError("Options %s are required." % tuple(missing))

  def _set_values(self, kwds, _lenient):
    for k, option in self._options.iteritems():
      v = kwds.get(k)
      if v is None and option.default_factory:
        v = option.default_factory()
      setattr(self, k, v)
      if _lenient:
        continue
      if v is None and option.can_be_none:
        continue
      if isinstance(v, type) and not issubclass(v, option.kind):
        raise TypeError(
            "Expect subclass of %r for option %s. Got %r" % (
                option.kind, k, v))
      if not isinstance(v, type) and not isinstance(v, option.kind):
        raise TypeError("Expect type %r for option %s. Got %r" % (
            option.kind, k, v))

  def __eq__(self, other):
    if not isinstance(other, self.__class__):
      return False
    return other.__dict__ == self.__dict__

  def __repr__(self):
    return str(self.__dict__)

  def to_json(self):
    return {"config": pickle.dumps(self)}

  @classmethod
  def from_json(cls, json):
    return pickle.loads(json["config"])



class _ConfigDefaults(object):
  """Default configs.

  Do not change parameters whose names begin with _.

  SHARD_MAX_ATTEMPTS: Max attempts to execute a shard before giving up.

  TASK_MAX_ATTEMPTS: Max attempts to execute a task before dropping it. Task
    is any taskqueue task created by MR framework. A task is dropped
    when its X-AppEngine-TaskExecutionCount is bigger than this number.
    Dropping a task will cause abort on the entire MR job.

  TASK_MAX_DATA_PROCESSING_ATTEMPTS:
    Max times to execute a task when previous task attempts failed during
    data processing stage. An MR work task has three major stages:
    initial setup, data processing, and final checkpoint.
    Setup stage should be allowed to be retried more times than data processing
    stage: setup failures are caused by unavailable GAE services while
    data processing failures are mostly due to user function error out on
    certain input data. Thus, set TASK_MAX_ATTEMPTS higher than this parameter.

  QUEUE_NAME: Default queue for MR.

  SHARD_COUNT: Default shard count.

  PROCESSING_RATE_PER_SEC: Default rate of processed entities per second.

  BASE_PATH : Base path of mapreduce and pipeline handlers.
  """

  SHARD_MAX_ATTEMPTS = 4


  TASK_MAX_ATTEMPTS = 31

  TASK_MAX_DATA_PROCESSING_ATTEMPTS = 11

  QUEUE_NAME = "default"

  SHARD_COUNT = 8





  PROCESSING_RATE_PER_SEC = 1000000


  BASE_PATH = "/_ah/mapreduce"




  _SLICE_DURATION_SEC = 15


  _CONTROLLER_PERIOD_SEC = 2



config = lib_config.register(CONFIG_NAMESPACE, _ConfigDefaults.__dict__)





_DEFAULT_PIPELINE_BASE_PATH = config.BASE_PATH + "/pipeline"

_GCS_URLFETCH_TIMEOUT_SEC = 30


_LEASE_DURATION_SEC = config._SLICE_DURATION_SEC * 1.1




_MAX_LEASE_DURATION_SEC = max(10 * 60 + 30, config._SLICE_DURATION_SEC * 1.5)
