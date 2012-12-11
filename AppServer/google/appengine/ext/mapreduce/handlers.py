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

















"""Defines executor tasks handlers for MapReduce implementation."""





import datetime
import gc
import logging
import math
import os
import time

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import db
from google.appengine.ext.mapreduce import base_handler
from google.appengine.ext.mapreduce import context
from google.appengine.ext.mapreduce import errors
from google.appengine.ext.mapreduce import input_readers
from google.appengine.ext.mapreduce import model
from google.appengine.ext.mapreduce import operation
from google.appengine.ext.mapreduce import quota
from google.appengine.ext.mapreduce import util

try:
  from google.appengine.ext import ndb
except ImportError:
  ndb = None



_QUOTA_BATCH_SIZE = 20



_SLICE_DURATION_SEC = 15


_CONTROLLER_PERIOD_SEC = 2



_RETRY_SLICE_ERROR_MAX_RETRIES = 10


_TEST_INJECTED_FAULTS = set()


def _run_task_hook(hooks, method, task, queue_name):
  """Invokes hooks.method(task, queue_name).

  Args:
    hooks: A hooks.Hooks instance or None.
    method: The name of the method to invoke on the hooks class e.g.
        "enqueue_kickoff_task".
    task: The taskqueue.Task to pass to the hook method.
    queue_name: The name of the queue to pass to the hook method.

  Returns:
    True if the hooks.Hooks instance handled the method, False otherwise.
  """
  if hooks is not None:
    try:
      getattr(hooks, method)(task, queue_name)
    except NotImplementedError:

      return False

    return True
  return False


class MapperWorkerCallbackHandler(util.HugeTaskHandler):
  """Callback handler for mapreduce worker task.

  Request Parameters:
    mapreduce_spec: MapreduceSpec of the mapreduce serialized to json.
    shard_id: id of the shard.
    slice_id: id of the slice.
  """

  def __init__(self, *args):
    """Constructor."""
    util.HugeTaskHandler.__init__(self, *args)
    self._time = time.time

  def handle(self):
    """Handle request."""
    tstate = model.TransientShardState.from_request(self.request)
    spec = tstate.mapreduce_spec
    self._start_time = self._time()
    shard_id = tstate.shard_id

    shard_state, control = db.get([
        model.ShardState.get_key_by_shard_id(shard_id),
        model.MapreduceControl.get_key_by_job_id(spec.mapreduce_id),
    ])
    if not shard_state:


      logging.error("State not found for shard ID %r; shutting down",
                    shard_id)
      return

    if not shard_state.active:
      logging.error("Shard is not active. Looks like spurious task execution.")
      return

    ctx = context.Context(spec, shard_state,
                          task_retry_count=self.task_retry_count())

    if control and control.command == model.MapreduceControl.ABORT:
      logging.info("Abort command received by shard %d of job '%s'",
                   shard_state.shard_number, shard_state.mapreduce_id)


      shard_state.active = False
      shard_state.result_status = model.ShardState.RESULT_ABORTED
      shard_state.put(config=util.create_datastore_write_config(spec))
      model.MapreduceControl.abort(spec.mapreduce_id)
      return

    input_reader = tstate.input_reader

    if spec.mapper.params.get("enable_quota", True):
      quota_consumer = quota.QuotaConsumer(
          quota.QuotaManager(memcache.Client()),
          shard_id,
          _QUOTA_BATCH_SIZE)
    else:
      quota_consumer = None






    if ndb is not None:
      ndb_ctx = ndb.get_context()
      ndb_ctx.set_cache_policy(lambda key: False)
      ndb_ctx.set_memcache_policy(lambda key: False)

    context.Context._set(ctx)
    try:


      if not quota_consumer or quota_consumer.check():
        scan_aborted = False
        entity = None

        try:


          if not quota_consumer or quota_consumer.consume():
            for entity in input_reader:
              if isinstance(entity, db.Model):
                shard_state.last_work_item = repr(entity.key())
              else:
                shard_state.last_work_item = repr(entity)[:100]

              scan_aborted = not self.process_data(
                  entity, input_reader, ctx, tstate)


              if (quota_consumer and not scan_aborted and
                  not quota_consumer.consume()):
                scan_aborted = True
              if scan_aborted:
                break
          else:
            scan_aborted = True

          if not scan_aborted:
            logging.info("Processing done for shard %d of job '%s'",
                         shard_state.shard_number, shard_state.mapreduce_id)


            if quota_consumer:
              quota_consumer.put(1)
            shard_state.active = False
            shard_state.result_status = model.ShardState.RESULT_SUCCESS

          operation.counters.Increment(
              context.COUNTER_MAPPER_WALLTIME_MS,
              int((time.time() - self._start_time)*1000))(ctx)



          ctx.flush()
        except errors.RetrySliceError, e:
          logging.error("Slice error: %s", e)
          retry_count = int(
              os.environ.get("HTTP_X_APPENGINE_TASKRETRYCOUNT") or 0)
          if retry_count <= _RETRY_SLICE_ERROR_MAX_RETRIES:
            raise
          logging.error("Too many retries: %d, failing the job", retry_count)
          scan_aborted = True
          shard_state.active = False
          shard_state.result_status = model.ShardState.RESULT_FAILED
        except errors.FailJobError, e:
          logging.error("Job failed: %s", e)
          scan_aborted = True
          shard_state.active = False
          shard_state.result_status = model.ShardState.RESULT_FAILED

      if not shard_state.active:



        if (shard_state.result_status == model.ShardState.RESULT_SUCCESS and
            tstate.output_writer):
          tstate.output_writer.finalize(ctx, shard_state.shard_number)

      config = util.create_datastore_write_config(spec)







      @db.transactional(retries=5)
      def tx():
        fresh_shard_state = db.get(
            model.ShardState.get_key_by_shard_id(shard_id))
        if not fresh_shard_state:
          raise db.Rollback()
        if (not fresh_shard_state.active or
            "worker_active_state_collision" in _TEST_INJECTED_FAULTS):
          shard_state.active = False
          logging.error("Spurious task execution. Aborting the shard.")
          return
        fresh_shard_state.copy_from(shard_state)
        fresh_shard_state.put(config=config)
      tx()
    finally:
      context.Context._set(None)
      if quota_consumer:
        quota_consumer.dispose()



    if shard_state.active:
      self.reschedule(shard_state, tstate)
    gc.collect()

  def process_data(self, data, input_reader, ctx, transient_shard_state):
    """Process a single data piece.

    Call mapper handler on the data.

    Args:
      data: a datum to process.
      input_reader: input reader.
      ctx: current execution context.

    Returns:
      True if scan should be continued, False if scan should be aborted.
    """
    if data is not input_readers.ALLOW_CHECKPOINT:
      ctx.counters.increment(context.COUNTER_MAPPER_CALLS)

      handler = ctx.mapreduce_spec.mapper.handler
      if input_reader.expand_parameters:
        result = handler(*data)
      else:
        result = handler(data)

      if util.is_generator(handler):
        for output in result:
          if isinstance(output, operation.Operation):
            output(ctx)
          else:
            output_writer = transient_shard_state.output_writer
            if not output_writer:
              logging.error(
                  "Handler yielded %s, but no output writer is set.", output)
            else:
              output_writer.write(output, ctx)

    if self._time() - self._start_time > _SLICE_DURATION_SEC:
      return False
    return True

  @staticmethod
  def get_task_name(shard_id, slice_id):
    """Compute single worker task name.

    Args:
      transient_shard_state: An instance of TransientShardState.

    Returns:
      task name which should be used to process specified shard/slice.
    """


    return "appengine-mrshard-%s-%s" % (
        shard_id, slice_id)

  def reschedule(self, shard_state, transient_shard_state):
    """Reschedule worker task to continue scanning work.

    Args:
      transient_shard_state: an instance of TransientShardState.
    """
    transient_shard_state.slice_id += 1
    MapperWorkerCallbackHandler._schedule_slice(
        shard_state, transient_shard_state)

  @classmethod
  def _schedule_slice(cls,
                      shard_state,
                      transient_shard_state,
                      queue_name=None,
                      eta=None,
                      countdown=None):
    """Schedule slice scanning by adding it to the task queue.

    Args:
      shard_state: An instance of ShardState.
      transient_shard_state: An instance of TransientShardState.
      queue_name: Optional queue to run on; uses the current queue of
        execution or the default queue if unspecified.
      eta: Absolute time when the MR should execute. May not be specified
        if 'countdown' is also supplied. This may be timezone-aware or
        timezone-naive.
      countdown: Time in seconds into the future that this MR should execute.
        Defaults to zero.
    """
    base_path = transient_shard_state.base_path
    mapreduce_spec = transient_shard_state.mapreduce_spec

    task_name = MapperWorkerCallbackHandler.get_task_name(
        transient_shard_state.shard_id,
        transient_shard_state.slice_id)
    queue_name = queue_name or os.environ.get("HTTP_X_APPENGINE_QUEUENAME",
                                              "default")

    worker_task = util.HugeTask(url=base_path + "/worker_callback",
                                params=transient_shard_state.to_dict(),
                                name=task_name,
                                eta=eta,
                                countdown=countdown)

    if not _run_task_hook(mapreduce_spec.get_hooks(),
                          "enqueue_worker_task",
                          worker_task,
                          queue_name):
      try:
        worker_task.add(queue_name, parent=shard_state)
      except (taskqueue.TombstonedTaskError,
              taskqueue.TaskAlreadyExistsError), e:
        logging.warning("Task %r with params %r already exists. %s: %s",
                        task_name,
                        transient_shard_state.to_dict(),
                        e.__class__,
                        e)


class ControllerCallbackHandler(util.HugeTaskHandler):
  """Supervises mapreduce execution.

  Is also responsible for gathering execution status from shards together.

  This task is "continuously" running by adding itself again to taskqueue if
  mapreduce is still active.
  """

  def __init__(self, *args):
    """Constructor."""
    util.HugeTaskHandler.__init__(self, *args)
    self._time = time.time

  def handle(self):
    """Handle request."""
    spec = model.MapreduceSpec.from_json_str(
        self.request.get("mapreduce_spec"))

    state, control = db.get([
        model.MapreduceState.get_key_by_job_id(spec.mapreduce_id),
        model.MapreduceControl.get_key_by_job_id(spec.mapreduce_id),
    ])
    if not state:
      logging.error("State not found for mapreduce_id '%s'; skipping",
                    spec.mapreduce_id)
      return

    shard_states = model.ShardState.find_by_mapreduce_state(state)
    if state.active and len(shard_states) != spec.mapper.shard_count:

      logging.error("Incorrect number of shard states: %d vs %d; "
                    "aborting job '%s'",
                    len(shard_states), spec.mapper.shard_count,
                    spec.mapreduce_id)
      state.active = False
      state.result_status = model.MapreduceState.RESULT_FAILED
      model.MapreduceControl.abort(spec.mapreduce_id)

    active_shards = [s for s in shard_states if s.active]
    failed_shards = [s for s in shard_states
                     if s.result_status == model.ShardState.RESULT_FAILED]
    aborted_shards = [s for s in shard_states
                     if s.result_status == model.ShardState.RESULT_ABORTED]
    if state.active:
      state.active = bool(active_shards)
      state.active_shards = len(active_shards)
      state.failed_shards = len(failed_shards)
      state.aborted_shards = len(aborted_shards)
      if not control and failed_shards:
        model.MapreduceControl.abort(spec.mapreduce_id)

    if (not state.active and control and
        control.command == model.MapreduceControl.ABORT):

      logging.info("Abort signal received for job '%s'", spec.mapreduce_id)
      state.result_status = model.MapreduceState.RESULT_ABORTED

    if not state.active:
      state.active_shards = 0
      if not state.result_status:

        if [s for s in shard_states
            if s.result_status != model.ShardState.RESULT_SUCCESS]:
          state.result_status = model.MapreduceState.RESULT_FAILED
        else:
          state.result_status = model.MapreduceState.RESULT_SUCCESS
        logging.info("Final result for job '%s' is '%s'",
                     spec.mapreduce_id, state.result_status)



    self.aggregate_state(state, shard_states)
    poll_time = state.last_poll_time
    state.last_poll_time = datetime.datetime.utcfromtimestamp(self._time())

    if not state.active:
      ControllerCallbackHandler._finalize_job(
          spec, state, self.base_path())
      return
    else:
      config = util.create_datastore_write_config(spec)
      state.put(config=config)

    processing_rate = int(spec.mapper.params.get(
        "processing_rate") or model._DEFAULT_PROCESSING_RATE_PER_SEC)
    self.refill_quotas(poll_time, processing_rate, active_shards)
    ControllerCallbackHandler.reschedule(
        state, self.base_path(), spec, self.serial_id() + 1)

  def aggregate_state(self, mapreduce_state, shard_states):
    """Update current mapreduce state by aggregating shard states.

    Args:
      mapreduce_state: current mapreduce state as MapreduceState.
      shard_states: all shard states (active and inactive). list of ShardState.
    """
    processed_counts = []
    mapreduce_state.counters_map.clear()

    for shard_state in shard_states:
      mapreduce_state.counters_map.add_map(shard_state.counters_map)
      processed_counts.append(shard_state.counters_map.get(
          context.COUNTER_MAPPER_CALLS))

    mapreduce_state.set_processed_counts(processed_counts)

  def refill_quotas(self,
                    last_poll_time,
                    processing_rate,
                    active_shard_states):
    """Refill quotas for all active shards.

    Args:
      last_poll_time: Datetime with the last time the job state was updated.
      processing_rate: How many items to process per second overall.
      active_shard_states: All active shard states, list of ShardState.
    """
    if not active_shard_states:
      return
    quota_manager = quota.QuotaManager(memcache.Client())

    current_time = int(self._time())
    last_poll_time = time.mktime(last_poll_time.timetuple())
    total_quota_refill = processing_rate * max(0, current_time - last_poll_time)
    quota_refill = int(math.ceil(
        1.0 * total_quota_refill / len(active_shard_states)))

    if not quota_refill:
      return


    for shard_state in active_shard_states:
      quota_manager.put(shard_state.shard_id, quota_refill)

  def serial_id(self):
    """Get serial unique identifier of this task from request.

    Returns:
      serial identifier as int.
    """
    return int(self.request.get("serial_id"))

  @staticmethod
  def _finalize_job(mapreduce_spec, mapreduce_state, base_path):
    """Finalize job execution.

    Finalizes output writer, invokes done callback an schedules
    finalize job execution.

    Args:
      mapreduce_spec: an instance of MapreduceSpec
      mapreduce_state: an instance of MapreduceState
      base_path: handler base path.
    """
    config = util.create_datastore_write_config(mapreduce_spec)


    if (mapreduce_spec.mapper.output_writer_class() and
        mapreduce_state.result_status == model.MapreduceState.RESULT_SUCCESS):
      mapreduce_spec.mapper.output_writer_class().finalize_job(mapreduce_state)


    def put_state(state):
      state.put(config=config)
      done_callback = mapreduce_spec.params.get(
          model.MapreduceSpec.PARAM_DONE_CALLBACK)
      if done_callback:
        done_task = taskqueue.Task(
            url=done_callback,
            headers={"Mapreduce-Id": mapreduce_spec.mapreduce_id},
            method=mapreduce_spec.params.get("done_callback_method", "POST"))
        queue_name = mapreduce_spec.params.get(
            model.MapreduceSpec.PARAM_DONE_CALLBACK_QUEUE,
            "default")

        if not _run_task_hook(mapreduce_spec.get_hooks(),
                              "enqueue_done_task",
                              done_task,
                              queue_name):
          done_task.add(queue_name, transactional=True)
      FinalizeJobHandler.schedule(base_path, mapreduce_spec)

    db.run_in_transaction(put_state, mapreduce_state)

  @staticmethod
  def get_task_name(mapreduce_spec, serial_id):
    """Compute single controller task name.

    Args:
      transient_shard_state: an instance of TransientShardState.

    Returns:
      task name which should be used to process specified shard/slice.
    """


    return "appengine-mrcontrol-%s-%s" % (
        mapreduce_spec.mapreduce_id, serial_id)

  @staticmethod
  def controller_parameters(mapreduce_spec, serial_id):
    """Fill in  controller task parameters.

    Returned parameters map is to be used as task payload, and it contains
    all the data, required by controller to perform its function.

    Args:
      mapreduce_spec: specification of the mapreduce.
      serial_id: id of the invocation as int.

    Returns:
      string->string map of parameters to be used as task payload.
    """
    return {"mapreduce_spec": mapreduce_spec.to_json_str(),
            "serial_id": str(serial_id)}

  @classmethod
  def reschedule(cls,
                 mapreduce_state,
                 base_path,
                 mapreduce_spec,
                 serial_id,
                 queue_name=None):
    """Schedule new update status callback task.

    Args:
      mapreduce_state: mapreduce state as model.MapreduceState
      base_path: mapreduce handlers url base path as string.
      mapreduce_spec: mapreduce specification as MapreduceSpec.
      serial_id: id of the invocation as int.
      queue_name: The queue to schedule this task on. Will use the current
        queue of execution if not supplied.
    """
    task_name = ControllerCallbackHandler.get_task_name(
        mapreduce_spec, serial_id)
    task_params = ControllerCallbackHandler.controller_parameters(
        mapreduce_spec, serial_id)
    if not queue_name:
      queue_name = os.environ.get("HTTP_X_APPENGINE_QUEUENAME", "default")

    controller_callback_task = util.HugeTask(
        url=base_path + "/controller_callback",
        name=task_name, params=task_params,
        countdown=_CONTROLLER_PERIOD_SEC)

    if not _run_task_hook(mapreduce_spec.get_hooks(),
                          "enqueue_controller_task",
                          controller_callback_task,
                          queue_name):
      try:
        controller_callback_task.add(queue_name, parent=mapreduce_state)
      except (taskqueue.TombstonedTaskError,
              taskqueue.TaskAlreadyExistsError), e:
        logging.warning("Task %r with params %r already exists. %s: %s",
                        task_name, task_params, e.__class__, e)


class KickOffJobHandler(util.HugeTaskHandler):
  """Taskqueue handler which kicks off a mapreduce processing.

  Request Parameters:
    mapreduce_spec: MapreduceSpec of the mapreduce serialized to json.
    input_readers: List of InputReaders objects separated by semi-colons.
  """

  def handle(self):
    """Handles kick off request."""
    spec = model.MapreduceSpec.from_json_str(
        self._get_required_param("mapreduce_spec"))

    app_id = self.request.get("app", None)
    queue_name = os.environ.get("HTTP_X_APPENGINE_QUEUENAME", "default")
    mapper_input_reader_class = spec.mapper.input_reader_class()



    state = model.MapreduceState.create_new(spec.mapreduce_id)
    state.mapreduce_spec = spec
    state.active = True
    if app_id:
      state.app_id = app_id

    input_readers = mapper_input_reader_class.split_input(spec.mapper)
    if not input_readers:

      logging.warning("Found no mapper input data to process.")
      state.active = False
      state.active_shards = 0
      ControllerCallbackHandler._finalize_job(spec, state, self.base_path())
      return


    spec.mapper.shard_count = len(input_readers)
    state.active_shards = len(input_readers)
    state.mapreduce_spec = spec

    output_writer_class = spec.mapper.output_writer_class()
    if output_writer_class:
      output_writer_class.init_job(state)

    output_writers = []
    if output_writer_class:
      for shard_number in range(len(input_readers)):
        writer = output_writer_class.create(state, shard_number)
        assert isinstance(writer, output_writer_class)
        output_writers.append(writer)
    else:
      output_writers = [None for ir in input_readers]

    state.put(config=util.create_datastore_write_config(spec))

    KickOffJobHandler._schedule_shards(
        spec, input_readers, output_writers, queue_name, self.base_path())

    ControllerCallbackHandler.reschedule(
        state, self.base_path(), spec, queue_name=queue_name, serial_id=0)

  def _get_required_param(self, param_name):
    """Get a required request parameter.

    Args:
      param_name: name of request parameter to fetch.

    Returns:
      parameter value

    Raises:
      errors.NotEnoughArgumentsError: if parameter is not specified.
    """
    value = self.request.get(param_name)
    if not value:
      raise errors.NotEnoughArgumentsError(param_name + " not specified")
    return value

  @classmethod
  def _schedule_shards(cls,
                       spec,
                       input_readers,
                       output_writers,
                       queue_name,
                       base_path):
    """Prepares shard states and schedules their execution.

    Args:
      spec: mapreduce specification as MapreduceSpec.
      input_readers: list of InputReaders describing shard splits.
      queue_name: The queue to run this job on.
      base_path: The base url path of mapreduce callbacks.
    """
    assert len(input_readers) == len(output_writers)



    shard_states = []
    for shard_number, input_reader in enumerate(input_readers):
      shard_state = model.ShardState.create_new(spec.mapreduce_id, shard_number)
      shard_state.shard_description = str(input_reader)
      shard_states.append(shard_state)


    existing_shard_states = db.get(shard.key() for shard in shard_states)
    existing_shard_keys = set(shard.key() for shard in existing_shard_states
                              if shard is not None)


    db.put((shard for shard in shard_states
            if shard.key() not in existing_shard_keys),
           config=util.create_datastore_write_config(spec))


    processing_rate = int(spec.mapper.params.get(
        "processing_rate") or model._DEFAULT_PROCESSING_RATE_PER_SEC)
    quota_refill = processing_rate / len(shard_states)
    quota_manager = quota.QuotaManager(memcache.Client())
    for shard_state in shard_states:
      quota_manager.put(shard_state.shard_id, quota_refill)


    for shard_number, (input_reader, output_writer) in enumerate(
        zip(input_readers, output_writers)):
      shard_id = model.ShardState.shard_id_from_number(
          spec.mapreduce_id, shard_number)
      MapperWorkerCallbackHandler._schedule_slice(
          shard_states[shard_number],
          model.TransientShardState(
              base_path, spec, shard_id, 0, input_reader,
              output_writer=output_writer),
          queue_name=queue_name)


class StartJobHandler(base_handler.PostJsonHandler):
  """Command handler starts a mapreduce job."""

  def handle(self):
    """Handles start request."""

    mapreduce_name = self._get_required_param("name")
    mapper_input_reader_spec = self._get_required_param("mapper_input_reader")
    mapper_handler_spec = self._get_required_param("mapper_handler")
    mapper_output_writer_spec = self.request.get("mapper_output_writer")
    mapper_params = self._get_params(
        "mapper_params_validator", "mapper_params.")
    params = self._get_params(
        "params_validator", "params.")


    mapper_params["processing_rate"] = int(mapper_params.get(
          "processing_rate") or model._DEFAULT_PROCESSING_RATE_PER_SEC)
    queue_name = mapper_params["queue_name"] = mapper_params.get(
        "queue_name", "default")


    mapper_spec = model.MapperSpec(
        mapper_handler_spec,
        mapper_input_reader_spec,
        mapper_params,
        int(mapper_params.get("shard_count", model._DEFAULT_SHARD_COUNT)),
        output_writer_spec=mapper_output_writer_spec)

    mapreduce_id = type(self)._start_map(
        mapreduce_name,
        mapper_spec,
        params,
        base_path=self.base_path(),
        queue_name=queue_name,
        _app=mapper_params.get("_app"))
    self.json_response["mapreduce_id"] = mapreduce_id

  def _get_params(self, validator_parameter, name_prefix):
    """Retrieves additional user-supplied params for the job and validates them.

    Args:
      validator_parameter: name of the request parameter which supplies
        validator for this parameter set.
      name_prefix: common prefix for all parameter names in the request.

    Raises:
      Any exception raised by the 'params_validator' request parameter if
      the params fail to validate.
    """
    params_validator = self.request.get(validator_parameter)

    user_params = {}
    for key in self.request.arguments():
      if key.startswith(name_prefix):
        values = self.request.get_all(key)
        adjusted_key = key[len(name_prefix):]
        if len(values) == 1:
          user_params[adjusted_key] = values[0]
        else:
          user_params[adjusted_key] = values

    if params_validator:
      resolved_validator = util.for_name(params_validator)
      resolved_validator(user_params)

    return user_params

  def _get_required_param(self, param_name):
    """Get a required request parameter.

    Args:
      param_name: name of request parameter to fetch.

    Returns:
      parameter value

    Raises:
      errors.NotEnoughArgumentsError: if parameter is not specified.
    """
    value = self.request.get(param_name)
    if not value:
      raise errors.NotEnoughArgumentsError(param_name + " not specified")
    return value

  @classmethod
  def _start_map(cls,
                 name,
                 mapper_spec,
                 mapreduce_params,
                 base_path=None,
                 queue_name=None,
                 eta=None,
                 countdown=None,
                 hooks_class_name=None,
                 _app=None,
                 transactional=False,
                 parent_entity=None):
    queue_name = queue_name or os.environ.get("HTTP_X_APPENGINE_QUEUENAME",
                                              "default")
    if queue_name[0] == "_":

      queue_name = "default"

    if not transactional and parent_entity:
      raise Exception("Parent shouldn't be specfied "
                      "for non-transactional starts.")


    mapper_input_reader_class = mapper_spec.input_reader_class()
    mapper_input_reader_class.validate(mapper_spec)

    mapper_output_writer_class = mapper_spec.output_writer_class()
    if mapper_output_writer_class:
      mapper_output_writer_class.validate(mapper_spec)

    mapreduce_id = model.MapreduceState.new_mapreduce_id()
    mapreduce_spec = model.MapreduceSpec(
        name,
        mapreduce_id,
        mapper_spec.to_json(),
        mapreduce_params,
        hooks_class_name)


    ctx = context.Context(mapreduce_spec, None)
    context.Context._set(ctx)
    try:
      mapper_spec.get_handler()
    finally:
      context.Context._set(None)

    kickoff_params = {"mapreduce_spec": mapreduce_spec.to_json_str()}
    if _app:
      kickoff_params["app"] = _app
    kickoff_worker_task = util.HugeTask(
        url=base_path + "/kickoffjob_callback",
        params=kickoff_params,
        eta=eta,
        countdown=countdown)

    hooks = mapreduce_spec.get_hooks()
    config = util.create_datastore_write_config(mapreduce_spec)

    def start_mapreduce():
      parent = parent_entity
      if not transactional:



        state = model.MapreduceState.create_new(mapreduce_spec.mapreduce_id)
        state.mapreduce_spec = mapreduce_spec
        state.active = True
        state.active_shards = mapper_spec.shard_count
        if _app:
          state.app_id = _app
        state.put(config=config)
        parent = state

      if hooks is not None:
        try:
          hooks.enqueue_kickoff_task(kickoff_worker_task, queue_name)
        except NotImplementedError:

          pass
        else:
          return
      kickoff_worker_task.add(queue_name, transactional=True, parent=parent)

    if transactional:
      start_mapreduce()
    else:
      db.run_in_transaction(start_mapreduce)

    return mapreduce_id


class FinalizeJobHandler(base_handler.TaskQueueHandler):
  """Finalize map job by deleting all temporary entities."""

  def handle(self):
    mapreduce_id = self.request.get("mapreduce_id")
    mapreduce_state = model.MapreduceState.get_by_job_id(mapreduce_id)
    if mapreduce_state:
      config=util.create_datastore_write_config(mapreduce_state.mapreduce_spec)
      db.delete(model.MapreduceControl.get_key_by_job_id(mapreduce_id),
              config=config)
      shard_states = model.ShardState.find_by_mapreduce_state(mapreduce_state)
      for shard_state in shard_states:
        db.delete(util._HugeTaskPayload.all().ancestor(shard_state),
                  config=config)
      db.delete(shard_states, config=config)
      db.delete(util._HugeTaskPayload.all().ancestor(mapreduce_state),
                config=config)

  @classmethod
  def schedule(cls, base_path, mapreduce_spec):
    """Schedule finalize task.

    Args:
      mapreduce_spec: mapreduce specification as MapreduceSpec.
    """
    task_name = mapreduce_spec.mapreduce_id + "-finalize"
    finalize_task = taskqueue.Task(
        name=task_name,
        url=base_path + "/finalizejob_callback",
        params={"mapreduce_id": mapreduce_spec.mapreduce_id})
    queue_name = os.environ.get("HTTP_X_APPENGINE_QUEUENAME", "default")
    if not _run_task_hook(mapreduce_spec.get_hooks(),
                          "enqueue_controller_task",
                          finalize_task,
                          queue_name):
      try:
        finalize_task.add(queue_name)
      except (taskqueue.TombstonedTaskError,
              taskqueue.TaskAlreadyExistsError), e:
        logging.warning("Task %r already exists. %s: %s",
                        task_name, e.__class__, e)


class CleanUpJobHandler(base_handler.PostJsonHandler):
  """Command to kick off tasks to clean up a job's data."""

  def handle(self):
    mapreduce_id = self.request.get("mapreduce_id")
    db.delete(model.MapreduceState.get_key_by_job_id(mapreduce_id))
    self.json_response["status"] = ("Job %s successfully cleaned up." %
                                    mapreduce_id)


class AbortJobHandler(base_handler.PostJsonHandler):
  """Command to abort a running job."""

  def handle(self):
    model.MapreduceControl.abort(self.request.get("mapreduce_id"))
    self.json_response["status"] = "Abort signal sent."
