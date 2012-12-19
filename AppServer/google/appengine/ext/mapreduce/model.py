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
















"""Model classes which are used to communicate between parts of implementation.

These model classes are describing mapreduce, its current state and
communication messages. They are either stored in the datastore or
serialized to/from json and passed around with other means.
"""





__all__ = ["JsonMixin", "JsonProperty", "MapreduceState", "MapperSpec",
           "MapreduceControl", "MapreduceSpec", "ShardState", "CountersMap",
           "TransientShardState"]

import copy
import datetime
import logging
import math
import os
import random
import simplejson
import time

from google.appengine.api import datastore_errors
from google.appengine.api import datastore_types
from google.appengine.ext import db
from google.appengine.ext.mapreduce import context
from google.appengine.ext.mapreduce import hooks
from google.appengine.ext.mapreduce import util
from google.appengine._internal.graphy.backends import google_chart_api




_DEFAULT_PROCESSING_RATE_PER_SEC = 1000000


_DEFAULT_SHARD_COUNT = 8


class JsonMixin(object):
  """Simple, stateless json utilities mixin.

  Requires class to implement two methods:
    to_json(self): convert data to json-compatible datastructure (dict,
      list, strings, numbers)
    @classmethod from_json(cls, json): load data from json-compatible structure.
  """

  def to_json_str(self):
    """Convert data to json string representation.

    Returns:
      json representation as string.
    """
    json = self.to_json()
    try:
      return simplejson.dumps(json, sort_keys=True)
    except:
      logging.exception("Could not serialize JSON: %r", json)
      raise

  @classmethod
  def from_json_str(cls, json_str):
    """Convert json string representation into class instance.

    Args:
      json_str: json representation as string.

    Returns:
      New instance of the class with data loaded from json string.
    """
    return cls.from_json(simplejson.loads(json_str))


class JsonProperty(db.UnindexedProperty):
  """Property type for storing json representation of data.

  Requires data types to implement two methods:
    to_json(self): convert data to json-compatible datastructure (dict,
      list, strings, numbers)
    @classmethod from_json(cls, json): load data from json-compatible structure.
  """

  def __init__(self, data_type, default=None, **kwargs):
    """Constructor.

    Args:
      data_type: underlying data type as class.
      default: default value for the property. The value is deep copied
        fore each model instance.
      kwargs: remaining arguments.
    """
    kwargs["default"] = default
    super(JsonProperty, self).__init__(**kwargs)
    self.data_type = data_type

  def get_value_for_datastore(self, model_instance):
    """Gets value for datastore.

    Args:
      model_instance: instance of the model class.

    Returns:
      datastore-compatible value.
    """
    value = super(JsonProperty, self).get_value_for_datastore(model_instance)
    if not value:
      return None
    json_value = value
    if not isinstance(value, dict):
      json_value = value.to_json()
    if not json_value:
      return None
    return datastore_types.Text(simplejson.dumps(
        json_value, sort_keys=True))

  def make_value_from_datastore(self, value):
    """Convert value from datastore representation.

    Args:
      value: datastore value.

    Returns:
      value to store in the model.
    """

    if value is None:
      return None
    json = simplejson.loads(value)
    if self.data_type == dict:
      return json
    return self.data_type.from_json(json)

  def validate(self, value):
    """Validate value.

    Args:
      value: model value.

    Returns:
      Whether the specified value is valid data type value.

    Raises:
      BadValueError: when value is not of self.data_type type.
    """
    if value is not None and not isinstance(value, self.data_type):
      raise datastore_errors.BadValueError(
          "Property %s must be convertible to a %s instance (%s)" %
          (self.name, self.data_type, value))
    return super(JsonProperty, self).validate(value)

  def empty(self, value):
    """Checks if value is empty.

    Args:
      value: model value.

    Returns:
      True passed value is empty.
    """
    return not value

  def default_value(self):
    """Create default model value.

    If default option was specified, then it will be deeply copied.
    None otherwise.

    Returns:
      default model value.
    """
    if self.default:
      return copy.deepcopy(self.default)
    else:
      return None




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
  request_id_hash = os.environ.get("REQUEST_ID_HASH")
  if not request_id_hash:
    request_id_hash = str(random.getrandbits(32))
  return "%d%s" % (now_descending, request_id_hash)


class CountersMap(JsonMixin):
  """Maintains map from counter name to counter value.

  The class is used to provide basic arithmetics of counter values (buil
  add/remove), increment individual values and store/load data from json.
  """

  def __init__(self, initial_map=None):
    """Constructor.

    Args:
      initial_map: initial counter values map from counter name (string) to
        counter value (int).
    """
    if initial_map:
      self.counters = initial_map
    else:
      self.counters = {}

  def __repr__(self):
    """Compute string representation."""
    return "mapreduce.model.CountersMap(%r)" % self.counters

  def get(self, counter_name):
    """Get current counter value.

    Args:
      counter_name: counter name as string.

    Returns:
      current counter value as int. 0 if counter was not set.
    """
    return self.counters.get(counter_name, 0)

  def increment(self, counter_name, delta):
    """Increment counter value.

    Args:
      counter_name: counter name as String.
      delta: increment delta as Integer.

    Returns:
      new counter value.
    """
    current_value = self.counters.get(counter_name, 0)
    new_value = current_value + delta
    self.counters[counter_name] = new_value
    return new_value

  def add_map(self, counters_map):
    """Add all counters from the map.

    For each counter in the passed map, adds its value to the counter in this
    map.

    Args:
      counters_map: CounterMap instance to add.
    """
    for counter_name in counters_map.counters:
      self.increment(counter_name, counters_map.counters[counter_name])

  def sub_map(self, counters_map):
    """Subtracts all counters from the map.

    For each counter in the passed map, subtracts its value to the counter in
    this map.

    Args:
      counters_map: CounterMap instance to subtract.
    """
    for counter_name in counters_map.counters:
      self.increment(counter_name, -counters_map.counters[counter_name])

  def clear(self):
    """Clear all values."""
    self.counters = {}

  def to_json(self):
    """Serializes all the data in this map into json form.

    Returns:
      json-compatible data representation.
    """
    return {"counters": self.counters}

  @classmethod
  def from_json(cls, json):
    """Create new CountersMap from the json data structure, encoded by to_json.

    Args:
      json: json representation of CountersMap .

    Returns:
      an instance of CountersMap with all data deserialized from json.
    """
    counters_map = cls()
    counters_map.counters = json["counters"]
    return counters_map

  def to_dict(self):
    """Convert to dictionary.

    Returns:
      a dictionary with counter name as key and counter values as value.
    """
    return self.counters


class MapperSpec(JsonMixin):
  """Contains a specification for the mapper phase of the mapreduce.

  MapperSpec instance can be changed only during mapreduce starting process,
  and it remains immutable for the rest of mapreduce execution. MapperSpec is
  passed as a payload to all mapreduce tasks in JSON encoding as part of
  MapreduceSpec.

  Specifying mapper handlers:
    * '<module_name>.<class_name>' - __call__ method of class instance will be
      called
    * '<module_name>.<function_name>' - function will be called.
    * '<module_name>.<class_name>.<method_name>' - class will be instantiated
      and method called.
  """

  def __init__(self,
               handler_spec,
               input_reader_spec,
               params,
               shard_count,
               output_writer_spec=None):
    """Creates a new MapperSpec.

    Args:
      handler_spec: handler specification as string (see class doc for
        details).
      input_reader_spec: The class name of the input reader to use.
      params: Dictionary of additional parameters for the mapper.
      shard_count: number of shards to process in parallel.

    Properties:
      handler_spec: name of handler class/function to use.
      shard_count: number of shards to process in parallel.
      handler: cached instance of mapper handler as callable.
      input_reader_spec: The class name of the input reader to use.
      output_writer_spec: The class name of the output writer to use.
      params: Dictionary of additional parameters for the mapper.
    """
    self.handler_spec = handler_spec
    self.__handler = None
    self.input_reader_spec = input_reader_spec
    self.output_writer_spec = output_writer_spec
    self.shard_count = shard_count
    self.params = params

  def get_handler(self):
    """Get mapper handler instance.

    Returns:
      cached handler instance as callable.
    """
    if self.__handler is None:
      self.__handler = util.handler_for_name(self.handler_spec)
    return self.__handler

  handler = property(get_handler)

  def input_reader_class(self):
    """Get input reader class.

    Returns:
      input reader class object.
    """
    return util.for_name(self.input_reader_spec)

  def output_writer_class(self):
    """Get output writer class.

    Returns:
      output writer class object.
    """
    return self.output_writer_spec and util.for_name(self.output_writer_spec)

  def to_json(self):
    """Serializes this MapperSpec into a json-izable object."""
    result = {
        "mapper_handler_spec": self.handler_spec,
        "mapper_input_reader": self.input_reader_spec,
        "mapper_params": self.params,
        "mapper_shard_count": self.shard_count,
    }
    if self.output_writer_spec:
      result["mapper_output_writer"] = self.output_writer_spec
    return result

  def __str__(self):
    return "MapperSpec(%s, %s, %s, %s)" % (
        self.handler_spec, self.input_reader_spec, self.params,
        self.shard_count)

  @classmethod
  def from_json(cls, json):
    """Creates MapperSpec from a dict-like object."""
    return cls(json["mapper_handler_spec"],
               json["mapper_input_reader"],
               json["mapper_params"],
               json["mapper_shard_count"],
               json.get("mapper_output_writer")
               )


class MapreduceSpec(JsonMixin):
  """Contains a specification for the whole mapreduce.

  MapreduceSpec instance can be changed only during mapreduce starting process,
  and it remains immutable for the rest of mapreduce execution. MapreduceSpec is
  passed as a payload to all mapreduce tasks in json encoding.
  """


  PARAM_DONE_CALLBACK = "done_callback"

  PARAM_DONE_CALLBACK_QUEUE = "done_callback_queue"

  def __init__(self,
               name,
               mapreduce_id,
               mapper_spec,
               params={},
               hooks_class_name=None):
    """Create new MapreduceSpec.

    Args:
      name: The name of this mapreduce job type.
      mapreduce_id: ID of the mapreduce.
      mapper_spec: JSON-encoded string containing a MapperSpec.
      params: dictionary of additional mapreduce parameters.
      hooks_class_name: The fully qualified name of the hooks class to use.

    Properties:
      name: The name of this mapreduce job type.
      mapreduce_id: unique id of this mapreduce as string.
      mapper: This MapreduceSpec's instance of MapperSpec.
      params: dictionary of additional mapreduce parameters.
      hooks_class_name: The fully qualified name of the hooks class to use.
    """
    self.name = name
    self.mapreduce_id = mapreduce_id
    self.mapper = MapperSpec.from_json(mapper_spec)
    self.params = params
    self.hooks_class_name = hooks_class_name
    self.__hooks = None
    self.get_hooks()

  def get_hooks(self):
    """Returns a hooks.Hooks class or None if no hooks class has been set."""
    if self.__hooks is None and self.hooks_class_name is not None:
      hooks_class = util.for_name(self.hooks_class_name)
      if not isinstance(hooks_class, type):
        raise ValueError("hooks_class_name must refer to a class, got %s" %
                         type(hooks_class).__name__)
      if not issubclass(hooks_class, hooks.Hooks):
        raise ValueError(
            "hooks_class_name must refer to a hooks.Hooks subclass")
      self.__hooks = hooks_class(self)

    return self.__hooks

  def to_json(self):
    """Serializes all data in this mapreduce spec into json form.

    Returns:
      data in json format.
    """
    mapper_spec = self.mapper.to_json()
    return {
        "name": self.name,
        "mapreduce_id": self.mapreduce_id,
        "mapper_spec": mapper_spec,
        "params": self.params,
        "hooks_class_name": self.hooks_class_name,
    }

  @classmethod
  def from_json(cls, json):
    """Create new MapreduceSpec from the json, encoded by to_json.

    Args:
      json: json representation of MapreduceSpec.

    Returns:
      an instance of MapreduceSpec with all data deserialized from json.
    """
    mapreduce_spec = cls(json["name"],
                         json["mapreduce_id"],
                         json["mapper_spec"],
                         json.get("params"),
                         json.get("hooks_class_name"))
    return mapreduce_spec


class MapreduceState(db.Model):
  """Holds accumulated state of mapreduce execution.

  MapreduceState is stored in datastore with a key name equal to the
  mapreduce ID. Only controller tasks can write to MapreduceState.

  Properties:
    mapreduce_spec: cached deserialized MapreduceSpec instance. read-only
    active: if we have this mapreduce running right now
    last_poll_time: last time controller job has polled this mapreduce.
    counters_map: shard's counters map as CountersMap. Mirrors
      counters_map_json.
    chart_url: last computed mapreduce status chart url. This chart displays the
      progress of all the shards the best way it can.
    sparkline_url: last computed mapreduce status chart url in small format.
    result_status: If not None, the final status of the job.
    active_shards: How many shards are still processing.
    start_time: When the job started.
    writer_state: Json property to be used by writer to store its state.
  """

  RESULT_SUCCESS = "success"
  RESULT_FAILED = "failed"
  RESULT_ABORTED = "aborted"

  _RESULTS = frozenset([RESULT_SUCCESS, RESULT_FAILED, RESULT_ABORTED])


  mapreduce_spec = JsonProperty(MapreduceSpec, indexed=False)
  active = db.BooleanProperty(default=True, indexed=False)
  last_poll_time = db.DateTimeProperty(required=True)
  counters_map = JsonProperty(CountersMap, default=CountersMap(), indexed=False)
  app_id = db.StringProperty(required=False, indexed=True)
  writer_state = JsonProperty(dict, indexed=False)


  chart_url = db.TextProperty(default="")
  chart_width = db.IntegerProperty(default=300, indexed=False)
  sparkline_url = db.TextProperty(default="")
  result_status = db.StringProperty(required=False, choices=_RESULTS)
  active_shards = db.IntegerProperty(default=0, indexed=False)
  failed_shards = db.IntegerProperty(default=0, indexed=False)
  aborted_shards = db.IntegerProperty(default=0, indexed=False)
  start_time = db.DateTimeProperty(auto_now_add=True)

  @classmethod
  def kind(cls):
    """Returns entity kind."""
    return "_GAE_MR_MapreduceState"

  @classmethod
  def get_key_by_job_id(cls, mapreduce_id):
    """Retrieves the Key for a Job.

    Args:
      mapreduce_id: The job to retrieve.

    Returns:
      Datastore Key that can be used to fetch the MapreduceState.
    """
    return db.Key.from_path(cls.kind(), str(mapreduce_id))

  @classmethod
  def get_by_job_id(cls, mapreduce_id):
    """Retrieves the instance of state for a Job.

    Args:
      mapreduce_id: The mapreduce job to retrieve.

    Returns:
      instance of MapreduceState for passed id.
    """
    return db.get(cls.get_key_by_job_id(mapreduce_id))

  def set_processed_counts(self, shards_processed):
    """Updates a chart url to display processed count for each shard.

    Args:
      shards_processed: list of integers with number of processed entities in
        each shard
    """
    chart = google_chart_api.BarChart(shards_processed)
    shard_count = len(shards_processed)

    if shards_processed:

      stride_length = max(1, shard_count / 16)
      chart.bottom.labels = []
      for x in xrange(shard_count):
        if (x % stride_length == 0 or
            x == shard_count - 1):
          chart.bottom.labels.append(x)
        else:
          chart.bottom.labels.append("")
      chart.left.labels = ['0', str(max(shards_processed))]
      chart.left.min = 0

    self.chart_width = min(700, max(300, shard_count * 20))
    self.chart_url = chart.display.Url(self.chart_width, 200)

  def get_processed(self):
    """Number of processed entities.

    Returns:
      The total number of processed entities as int.
    """
    return self.counters_map.get(context.COUNTER_MAPPER_CALLS)

  processed = property(get_processed)

  @staticmethod
  def create_new(mapreduce_id=None,
                 gettime=datetime.datetime.now):
    """Create a new MapreduceState.

    Args:
      mapreduce_id: Mapreduce id as string.
      gettime: Used for testing.
    """
    if not mapreduce_id:
      mapreduce_id = MapreduceState.new_mapreduce_id()
    state = MapreduceState(key_name=mapreduce_id,
                           last_poll_time=gettime())
    state.set_processed_counts([])
    return state

  @staticmethod
  def new_mapreduce_id():
    """Generate new mapreduce id."""
    return _get_descending_key()


class TransientShardState(object):
  """Shard's state kept in task payload.

  TransientShardState holds a port of all shard processing state, which is not
  saved in datastore, but rather is passed in task payload.
  """

  def __init__(self,
               base_path,
               mapreduce_spec,
               shard_id,
               slice_id,
               input_reader,
               output_writer=None):
    self.base_path = base_path
    self.mapreduce_spec = mapreduce_spec
    self.shard_id = shard_id
    self.slice_id = slice_id
    self.input_reader = input_reader
    self.output_writer = output_writer

  def to_dict(self):
    """Convert state to dictionary to save in task payload."""
    result = {"mapreduce_spec": self.mapreduce_spec.to_json_str(),
              "shard_id": self.shard_id,
              "slice_id": str(self.slice_id),
              "input_reader_state": self.input_reader.to_json_str()}
    if self.output_writer:
      result["output_writer_state"] = self.output_writer.to_json_str()
    return result

  @classmethod
  def from_request(cls, request):
    """Create new TransientShardState from webapp request."""
    mapreduce_spec = MapreduceSpec.from_json_str(request.get("mapreduce_spec"))
    mapper_spec = mapreduce_spec.mapper
    input_reader_spec_dict = simplejson.loads(request.get("input_reader_state"))
    input_reader = mapper_spec.input_reader_class().from_json(
        input_reader_spec_dict)

    output_writer = None
    if mapper_spec.output_writer_class():
      output_writer = mapper_spec.output_writer_class().from_json(
          simplejson.loads(request.get("output_writer_state", "{}")))
      assert isinstance(output_writer, mapper_spec.output_writer_class()), (
          "%s.from_json returned an instance of wrong class: %s" % (
              mapper_spec.output_writer_class(),
              output_writer.__class__))

    request_path = request.path
    base_path = request_path[:request_path.rfind("/")]

    return cls(base_path,
               mapreduce_spec,
               str(request.get("shard_id")),
               int(request.get("slice_id")),
               input_reader,
               output_writer=output_writer)


class ShardState(db.Model):
  """Single shard execution state.

  The shard state is stored in the datastore and is later aggregated by
  controller task. Shard key_name is equal to shard_id.

  Properties:
    active: if we have this shard still running as boolean.
    counters_map: shard's counters map as CountersMap. Mirrors
      counters_map_json.
    mapreduce_id: unique id of the mapreduce.
    shard_id: unique id of this shard as string.
    shard_number: ordered number for this shard.
    result_status: If not None, the final status of this shard.
    update_time: The last time this shard state was updated.
    shard_description: A string description of the work this shard will do.
    last_work_item: A string description of the last work item processed.
  """

  RESULT_SUCCESS = "success"
  RESULT_FAILED = "failed"
  RESULT_ABORTED = "aborted"

  _RESULTS = frozenset([RESULT_SUCCESS, RESULT_FAILED, RESULT_ABORTED])


  active = db.BooleanProperty(default=True, indexed=False)
  counters_map = JsonProperty(CountersMap, default=CountersMap(), indexed=False)
  result_status = db.StringProperty(choices=_RESULTS, indexed=False)


  mapreduce_id = db.StringProperty(required=True)
  update_time = db.DateTimeProperty(auto_now=True, indexed=False)
  shard_description = db.TextProperty(default="")
  last_work_item = db.TextProperty(default="")

  def copy_from(self, other_state):
    """Copy data from another shard state entity to self."""
    for prop in self.properties().values():
      setattr(self, prop.name, getattr(other_state, prop.name))

  def get_shard_number(self):
    """Gets the shard number from the key name."""
    return int(self.key().name().split("-")[-1])

  shard_number = property(get_shard_number)

  def get_shard_id(self):
    """Returns the shard ID."""
    return self.key().name()

  shard_id = property(get_shard_id)

  @classmethod
  def kind(cls):
    """Returns entity kind."""
    return "_GAE_MR_ShardState"

  @classmethod
  def shard_id_from_number(cls, mapreduce_id, shard_number):
    """Get shard id by mapreduce id and shard number.

    Args:
      mapreduce_id: mapreduce id as string.
      shard_number: shard number to compute id for as int.

    Returns:
      shard id as string.
    """
    return "%s-%d" % (mapreduce_id, shard_number)

  @classmethod
  def get_key_by_shard_id(cls, shard_id):
    """Retrieves the Key for this ShardState.

    Args:
      shard_id: The shard ID to fetch.

    Returns:
      The Datatore key to use to retrieve this ShardState.
    """
    return db.Key.from_path(cls.kind(), shard_id)

  @classmethod
  def get_by_shard_id(cls, shard_id):
    """Get shard state from datastore by shard_id.

    Args:
      shard_id: shard id as string.

    Returns:
      ShardState for given shard id or None if it's not found.
    """
    return cls.get_by_key_name(shard_id)

  @classmethod
  def find_by_mapreduce_state(cls, mapreduce_state):
    """Find all shard states for given mapreduce.

    Args:
      mapreduce_state: MapreduceState instance

    Returns:
      iterable of all ShardState for given mapreduce.
    """
    keys = []
    for i in range(mapreduce_state.mapreduce_spec.mapper.shard_count):
      shard_id = cls.shard_id_from_number(mapreduce_state.key().name(), i)
      keys.append(cls.get_key_by_shard_id(shard_id))
    return [state for state in db.get(keys) if state]

  @classmethod
  def find_by_mapreduce_id(cls, mapreduce_id):
    logging.error(
        "ShardState.find_by_mapreduce_id method may be inconsistent. " +
        "ShardState.find_by_mapreduce_state should be used instead.")
    return cls.all().filter(
        "mapreduce_id =", mapreduce_id).fetch(99999)

  @classmethod
  def create_new(cls, mapreduce_id, shard_number):
    """Create new shard state.

    Args:
      mapreduce_id: unique mapreduce id as string.
      shard_number: shard number for which to create shard state.

    Returns:
      new instance of ShardState ready to put into datastore.
    """
    shard_id = cls.shard_id_from_number(mapreduce_id, shard_number)
    state = cls(key_name=shard_id,
                mapreduce_id=mapreduce_id)
    return state


class MapreduceControl(db.Model):
  """Datastore entity used to control mapreduce job execution.

  Only one command may be sent to jobs at a time.

  Properties:
    command: The command to send to the job.
  """

  ABORT = "abort"

  _COMMANDS = frozenset([ABORT])
  _KEY_NAME = "command"

  command = db.TextProperty(choices=_COMMANDS, required=True)

  @classmethod
  def kind(cls):
    """Returns entity kind."""
    return "_GAE_MR_MapreduceControl"

  @classmethod
  def get_key_by_job_id(cls, mapreduce_id):
    """Retrieves the Key for a mapreduce ID.

    Args:
      mapreduce_id: The job to fetch.

    Returns:
      Datastore Key for the command for the given job ID.
    """
    return db.Key.from_path(cls.kind(), "%s:%s" % (mapreduce_id, cls._KEY_NAME))

  @classmethod
  def abort(cls, mapreduce_id, **kwargs):
    """Causes a job to abort.

    Args:
      mapreduce_id: The job to abort. Not verified as a valid job.
    """
    cls(key_name="%s:%s" % (mapreduce_id, cls._KEY_NAME),
        command=cls.ABORT).put(**kwargs)
