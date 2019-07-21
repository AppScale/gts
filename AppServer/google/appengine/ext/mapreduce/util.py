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














"""Utility functions for use with the mapreduce library."""





__all__ = [
    "create_datastore_write_config",
    "for_name",
    "get_queue_name",
    "get_short_name",
    "handler_for_name",
    "is_generator",
    "parse_bool",
    "total_seconds",
    "try_serialize_handler",
    "try_deserialize_handler",
    "CALLBACK_MR_ID_TASK_HEADER",
    "strip_prefix_from_items",
    "ALLOW_CHECKPOINT",
    ]

import inspect
import os
import pickle
import random
import sys
import time
import types

import google
from google.appengine.ext import ndb

from google.appengine.datastore import datastore_rpc
from google.appengine.ext.mapreduce import parameters


_MR_ID_TASK_HEADER = "AE-MR-ID"
_MR_SHARD_ID_TASK_HEADER = "AE-MR-SHARD-ID"


CALLBACK_MR_ID_TASK_HEADER = "Mapreduce-Id"






ALLOW_CHECKPOINT = object()


_FUTURE_TIME = 2**34


def _get_descending_key(gettime=time.time):
  """Returns a key name lexically ordered by time descending.

  This lets us have a key name for use with Datastore entities which returns
  rows in time descending order when it is scanned in lexically ascending order,
  allowing us to bypass index building for descending indexes.

  Args:
    gettime: Used for testing.

  Returns:
    A string with a time descending key.
  """


  now_descending = int((_FUTURE_TIME - gettime()) * 100)
  request_id_hash = os.environ.get("REQUEST_ID_HASH", "")
  random_bits = random.getrandbits(32)
  return "%d%s%s" % (now_descending, random_bits, request_id_hash)


def _get_task_host():
  """Get the Host header value for all mr tasks.

  Task Host header determines which instance this task would be routed to.

  Current version id format is: v7.368834058928280579
  Current module id is just the module's name. It could be "default"
  Default version hostname is app_id.appspot.com

  Returns:
    A complete host name is of format version.module.app_id.appspot.com
  If module is the default module, just version.app_id.appspot.com. The reason
  is if an app doesn't have modules enabled and the url is
  "version.default.app_id", "version" is ignored and "default" is used as
  version. If "default" version doesn't exist, the url is routed to the
  default version.
  """
  version = os.environ["CURRENT_VERSION_ID"].split(".")[0]
  default_host = os.environ["DEFAULT_VERSION_HOSTNAME"]
  module = os.environ["CURRENT_MODULE_ID"]
  if os.environ["CURRENT_MODULE_ID"] == "default":
    return "%s.%s" % (version, default_host)
  return "%s.%s.%s" % (version, module, default_host)


def _get_task_headers(map_job_id,
                      mr_id_header_key=_MR_ID_TASK_HEADER,
                      set_host_header=True):
  """Get headers for all mr tasks.

  Args:
    map_job_id: map job id.
    mr_id_header_key: the key to set mr id with.
    set_host_header: If True, the "Host" param will be set to point to the
                     current version + module.

  Returns:
    A dictionary of all headers.
  """
  result = {mr_id_header_key: map_job_id}
  if set_host_header:
    result["Host"] = _get_task_host()
  return result


def _enum(**enums):
  """Helper to create enum."""
  return type("Enum", (), enums)


def get_queue_name(queue_name):
  """Determine which queue MR should run on.

  How to choose the queue:
  1. If user provided one, use that.
  2. If we are starting a mr from taskqueue, inherit that queue.
     If it's a special queue, fall back to the default queue.
  3. Default queue.

  If user is using any MR pipeline interface, pipeline.start takes a
  "queue_name" argument. The pipeline will run on that queue and MR will
  simply inherit the queue_name.

  Args:
    queue_name: queue_name from user. Maybe None.

  Returns:
    The queue name to run on.
  """
  if queue_name:
    return queue_name
  queue_name = os.environ.get("HTTP_X_APPENGINE_QUEUENAME",
                              parameters.config.QUEUE_NAME)
  if len(queue_name) > 1 and queue_name[0:2] == "__":

    return parameters.config.QUEUE_NAME
  else:
    return queue_name


def total_seconds(td):
  """convert a timedelta to seconds.

  This is patterned after timedelta.total_seconds, which is only
  available in python 27.

  Args:
    td: a timedelta object.

  Returns:
    total seconds within a timedelta. Rounded up to seconds.
  """
  secs = td.seconds + td.days * 24 * 3600
  if td.microseconds:
    secs += 1
  return secs


def _maybe_localize_fq_name(module_name, fq_name):
  """Localizes fq_name to deal with path difference in python25/27 runtimes.

  Args:
    module_name: Name of our module, obtained using __name__.
    fq_name: Fully qualified name to be "localized".
  Returns:
    fq_name, potentially with prefix switched to match current module.
  """


























  PREFIX_LOCALIZATIONS = {
      "google.appengine._internal.mapreduce": "google.appengine.ext.mapreduce",
      "google.appengine.ext.mapreduce": "google.appengine._internal.mapreduce",
  }
  for local_module_prefix, fq_name_prefix in PREFIX_LOCALIZATIONS.iteritems():
    if (module_name.startswith(local_module_prefix)
        and fq_name.startswith(fq_name_prefix)):
      return fq_name.replace(fq_name_prefix, local_module_prefix, 1)
  return fq_name


def for_name(fq_name, recursive=False):
  """Find class/function/method specified by its fully qualified name.

  Fully qualified can be specified as:
    * <module_name>.<class_name>
    * <module_name>.<function_name>
    * <module_name>.<class_name>.<method_name> (an unbound method will be
      returned in this case).

  for_name works by doing __import__ for <module_name>, and looks for
  <class_name>/<function_name> in module's __dict__/attrs. If fully qualified
  name doesn't contain '.', the current module will be used.

  Args:
    fq_name: fully qualified name of something to find.
    recursive: run recursively or not.

  Returns:
    class object or None if fq_name is None.

  Raises:
    ImportError: when specified module could not be loaded or the class
    was not found in the module.
  """



  if fq_name is None:
    return

  fq_name = str(fq_name)
  module_name = __name__
  short_name = fq_name

  fq_name = _maybe_localize_fq_name(module_name, fq_name)

  if fq_name.rfind(".") >= 0:
    (module_name, short_name) = (fq_name[:fq_name.rfind(".")],
                                 fq_name[fq_name.rfind(".") + 1:])

  try:
    result = __import__(module_name, None, None, [short_name])
    return result.__dict__[short_name]
  except KeyError:





    if recursive:
      raise
    else:
      raise ImportError("Could not find '%s' on path '%s'" % (
          short_name, module_name))
  except ImportError:


    try:
      module = for_name(module_name, recursive=True)
      if hasattr(module, short_name):
        return getattr(module, short_name)
      else:

        raise KeyError()
    except KeyError:
      raise ImportError("Could not find '%s' on path '%s'" % (
          short_name, module_name))
    except ImportError:


      pass


    raise


def handler_for_name(fq_name):
  """Resolves and instantiates handler by fully qualified name.

  First resolves the name using for_name call. Then if it resolves to a class,
  instantiates a class, if it resolves to a method - instantiates the class and
  binds method to the instance.

  Args:
    fq_name: fully qualified name of something to find.

  Returns:
    handler instance which is ready to be called.
  """
  resolved_name = for_name(fq_name)
  if isinstance(resolved_name, (type, types.ClassType)):

    return resolved_name()
  elif isinstance(resolved_name, types.MethodType):

    return getattr(resolved_name.im_class(), resolved_name.__name__)
  else:
    return resolved_name


def try_serialize_handler(handler):
  """Try to serialize map/reduce handler.

  Args:
    handler: handler function/instance. Handler can be a function or an
      instance of a callable class. In the latter case, the handler will
      be serialized across slices to allow users to save states.

  Returns:
    serialized handler string or None.
  """
  if (isinstance(handler, types.InstanceType) or
      (isinstance(handler, object) and
       not inspect.isfunction(handler) and
       not inspect.ismethod(handler)) and
      hasattr(handler, "__call__")):
    return pickle.dumps(handler)
  return None


def try_deserialize_handler(serialized_handler):
  """Reverse function of try_serialize_handler.

  Args:
    serialized_handler: serialized handler str or None.

  Returns:
    handler instance or None.
  """
  if serialized_handler:
    return pickle.loads(serialized_handler)


def is_generator(obj):
  """Return true if the object is generator or generator function.

  Generator function objects provides same attributes as functions.
  See isfunction.__doc__ for attributes listing.

  Adapted from Python 2.6.

  Args:
    obj: an object to test.

  Returns:
    true if the object is generator function.
  """
  if isinstance(obj, types.GeneratorType):
    return True

  CO_GENERATOR = 0x20
  return bool(((inspect.isfunction(obj) or inspect.ismethod(obj)) and
               obj.func_code.co_flags & CO_GENERATOR))


def get_short_name(fq_name):
  """Returns the last component of the name."""
  return fq_name.split(".")[-1:][0]


def parse_bool(obj):
  """Return true if the object represents a truth value, false otherwise.

  For bool and numeric objects, uses Python's built-in bool function.  For
  str objects, checks string against a list of possible truth values.

  Args:
    obj: object to determine boolean value of; expected

  Returns:
    Boolean value according to 5.1 of Python docs if object is not a str
      object.  For str objects, return True if str is in TRUTH_VALUE_SET
      and False otherwise.
    http://docs.python.org/library/stdtypes.html
  """
  if type(obj) is str:
    TRUTH_VALUE_SET = ["true", "1", "yes", "t", "on"]
    return obj.lower() in TRUTH_VALUE_SET
  else:
    return bool(obj)


def create_datastore_write_config(mapreduce_spec):
  """Creates datastore config to use in write operations.

  Args:
    mapreduce_spec: current mapreduce specification as MapreduceSpec.

  Returns:
    an instance of datastore_rpc.Configuration to use for all write
    operations in the mapreduce.
  """
  force_writes = parse_bool(mapreduce_spec.params.get("force_writes", "false"))
  if force_writes:
    return datastore_rpc.Configuration(force_writes=force_writes)
  else:

    return datastore_rpc.Configuration()


def _set_ndb_cache_policy():
  """Tell NDB to never cache anything in memcache or in-process.

  This ensures that entities fetched from Datastore input_readers via NDB
  will not bloat up the request memory size and Datastore Puts will avoid
  doing calls to memcache. Without this you get soft memory limit exits,
  which hurts overall throughput.
  """
  ndb_ctx = ndb.get_context()
  ndb_ctx.set_cache_policy(lambda key: False)
  ndb_ctx.set_memcache_policy(lambda key: False)


def _obj_to_path(obj):
  """Returns the fully qualified path to the object.

  Args:
    obj: obj must be a new style top level class, or a top level function.
      No inner function or static method.

  Returns:
    Fully qualified path to the object.

  Raises:
    TypeError: when argument obj has unsupported type.
    ValueError: when obj can't be discovered on the top level.
  """
  if obj is None:
    return obj

  if inspect.isclass(obj) or inspect.isfunction(obj):
    fetched = getattr(sys.modules[obj.__module__], obj.__name__, None)
    if fetched is None:
      raise ValueError(
          "Object %r must be defined on the top level of a module." % obj)
    return "%s.%s" % (obj.__module__, obj.__name__)
  raise TypeError("Unexpected type %s." % type(obj))


def strip_prefix_from_items(prefix, items):
  """Strips out the prefix from each of the items if it is present.

  Args:
    prefix: the string for that you wish to strip from the beginning of each
      of the items.
    items: a list of strings that may or may not contain the prefix you want
      to strip out.

  Returns:
    items_no_prefix: a copy of the list of items (same order) without the
      prefix (if present).
  """
  items_no_prefix = []
  for item in items:
    if item.startswith(prefix):
      items_no_prefix.append(item[len(prefix):])
    else:
      items_no_prefix.append(item)
  return items_no_prefix
