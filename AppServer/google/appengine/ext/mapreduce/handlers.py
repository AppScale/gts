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
import random
import sys
import time
import traceback
import simplejson

from google.appengine.ext import ndb

from google.appengine import runtime
from google.appengine.api import datastore_errors
from google.appengine.api import logservice
from google.appengine.api import modules
from google.appengine.api import taskqueue
from google.appengine.ext import db
from google.appengine.ext.mapreduce import base_handler
from google.appengine.ext.mapreduce import context
from google.appengine.ext.mapreduce import errors
from google.appengine.ext.mapreduce import input_readers
from google.appengine.ext.mapreduce import model
from google.appengine.ext.mapreduce import operation
from google.appengine.ext.mapreduce import parameters
from google.appengine.ext.mapreduce import util
from google.appengine.runtime import apiproxy_errors



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


class MapperWorkerCallbackHandler(base_handler.HugeTaskHandler):
  """Callback handler for mapreduce worker task."""
  _TASK_STATE = util._enum(RETRY_TASK="retry_task",
                           DROP_TASK="drop_task")

  def __init__(self, *args):
    """Constructor."""
    super(MapperWorkerCallbackHandler, self).__init__(*args)
    self._time = time.time

  def _drop_gracefully(self):
    """Drop worker task gracefully.

    Set current shard_state to failed. Controller logic will take care of
    other shards and the entire MR.
    """
    shard_id = self.request.headers[util._MR_SHARD_ID_TASK_HEADER]
    mr_id = self.request.headers[util._MR_ID_TASK_HEADER]
    shard_state, mr_state = db.get([
        model.ShardState.get_key_by_shard_id(shard_id),
        model.MapreduceState.get_key_by_job_id(mr_id)])

    if shard_state and shard_state.active:
      shard_state.set_for_failure()
      config = util.create_datastore_write_config(mr_state.mapreduce_spec)
      shard_state.put(config=config)

  def _try_acquire_lease(self, shard_state, tstate):
    """Validate datastore and the task payload are consistent.

    If so, attempt to get a lease on this slice's execution.
    See model.ShardState doc on slice_start_time.

    Args:
      shard_state: model.ShardState from datastore.
      tstate: model.TransientShardState from taskqueue paylod.

    Returns:
      A fresh shard state entity if lease is acquired. A _TASK_STATE
    enum if this task should be retried or dropped. Only old tasks
    (comparing to datastore state) will be dropped. Future tasks are
    retried until they naturally become old so that we don't ever stuck MR.
    """

    if not shard_state:
      logging.warning("State not found for shard %s; Possible spurious task "
                      "execution. Dropping this task.",
                      tstate.shard_id)
      return self._TASK_STATE.DROP_TASK

    if not shard_state.active:
      logging.warning("Shard %s is not active. Possible spurious task "
                      "execution. Dropping this task.", tstate.shard_id)
      logging.warning(str(shard_state))
      return self._TASK_STATE.DROP_TASK


    if shard_state.retries > tstate.retries:
      logging.warning(
          "Got shard %s from previous shard retry %s. Possible spurious "
          "task execution. Dropping this task.",
          tstate.shard_id,
          tstate.retries)
      logging.warning(str(shard_state))
      return self._TASK_STATE.DROP_TASK
    elif shard_state.retries < tstate.retries:



      logging.warning(
          "ShardState for %s is behind slice. Waiting for it to catch up",
          shard_state.shard_id)
      return self._TASK_STATE.RETRY_TASK



    if shard_state.slice_id > tstate.slice_id:
      logging.warning(
          "Task %s-%s is behind ShardState %s. Dropping task.""",
          tstate.shard_id, tstate.slice_id, shard_state.slice_id)
      return self._TASK_STATE.DROP_TASK



    elif shard_state.slice_id < tstate.slice_id:
      logging.warning(
          "Task %s-%s is ahead of ShardState %s. Waiting for it to catch up.",
          tstate.shard_id, tstate.slice_id, shard_state.slice_id)
      return self._TASK_STATE.RETRY_TASK



    if shard_state.slice_start_time:
      countdown = self._wait_time(shard_state,
                                  parameters._LEASE_GRACE_PERIOD +
                                  parameters._SLICE_DURATION_SEC)
      if countdown > 0:
        logging.warning(
            "Last retry of slice %s-%s may be still running."
            "Will try again in %s seconds", tstate.shard_id, tstate.slice_id,
            countdown)



        time.sleep(countdown)
        return self._TASK_STATE.RETRY_TASK

      else:
        if self._wait_time(shard_state, parameters._REQUEST_EVENTUAL_TIMEOUT):
          if not self._old_request_ended(shard_state):
            logging.warning(
                "Last retry of slice %s-%s is still in flight with request_id "
                "%s. Will try again later.", tstate.shard_id, tstate.slice_id,
                shard_state.slice_request_id)
            return self._TASK_STATE.RETRY_TASK
        else:
          logging.warning(
              "Last retry of slice %s-%s has no log entry and has"
              "timed out after %s seconds",
              tstate.shard_id, tstate.slice_id,
              parameters._REQUEST_EVENTUAL_TIMEOUT)


    config = util.create_datastore_write_config(tstate.mapreduce_spec)
    @db.transactional(retries=5)
    def _tx():
      """Use datastore to set slice_start_time to now.

      If failed for any reason, raise error to retry the task (hence all
      the previous validation code). The task would die naturally eventually.

      Returns:
        Fresh shard state if state commit succeeded. None otherwise.
      """
      fresh_state = model.ShardState.get_by_shard_id(tstate.shard_id)
      if not fresh_state:
        logging.error("ShardState missing.")
        raise db.Rollback()
      if (fresh_state.active and
          fresh_state.slice_id == shard_state.slice_id and
          fresh_state.slice_start_time == shard_state.slice_start_time):
        fresh_state.slice_start_time = datetime.datetime.now()
        fresh_state.slice_request_id = os.environ.get("REQUEST_LOG_ID")
        fresh_state.acquired_once = True
        fresh_state.put(config=config)
        return fresh_state
      else:
        logging.warning(
            "Contention on slice %s-%s execution. Will retry again.",
            tstate.shard_id, tstate.slice_id)

        time.sleep(random.randrange(1, 5))
        return self._TASK_STATE.RETRY_TASK

    return _tx()

  def _old_request_ended(self, shard_state):
    """Whether previous slice retry has ended according to Logs API.

    Args:
      shard_state: shard state.

    Returns:
      True if the request of previous slice retry has ended. False if it has
    not or unknown.
    """
    assert shard_state.slice_start_time is not None
    assert shard_state.slice_request_id is not None
    request_ids = [shard_state.slice_request_id]
    logs = list(logservice.fetch(
        request_ids=request_ids,

        module_versions=[(os.environ["CURRENT_MODULE_ID"],
                          modules.get_current_version_name())]))

    if not logs or not logs[0].finished:
      return False
    return True

  def _wait_time(self, shard_state, secs, now=datetime.datetime.now):
    """Time to wait until slice_start_time is secs ago from now.

    Args:
      shard_state: shard state.
      secs: duration in seconds.
      now: a func that gets now.

    Returns:
      0 if no wait. A positive int in seconds otherwise. Always around up.
    """
    assert shard_state.slice_start_time is not None
    delta = now() - shard_state.slice_start_time
    duration = datetime.timedelta(seconds=secs)
    if delta < duration:
      return util.total_seconds(duration - delta)
    else:
      return 0

  def _try_free_lease(self, shard_state, slice_retry=False):
    """Try to free lease.

    A lightweight transaction to update shard_state and unset
    slice_start_time to allow the next retry to happen without blocking.
    We don't care if this fails or not because the lease will expire
    anyway.

    Under normal execution, _save_state_and_schedule_next is the exit point.
    It updates/saves shard state and schedules the next slice or returns.
    Other exit points are:
    1. _are_states_consistent: at the beginning of handle, checks
      if datastore states and the task are in sync.
      If not, raise or return.
    2. _attempt_slice_retry: may raise exception to taskqueue.
    3. _save_state_and_schedule_next: may raise exception when taskqueue/db
       unreachable.

    This handler should try to free the lease on every exceptional exit point.

    Args:
      shard_state: model.ShardState.
      slice_retry: whether to count this as a failed slice execution.
    """
    @db.transactional
    def _tx():
      fresh_state = model.ShardState.get_by_shard_id(shard_state.shard_id)
      if fresh_state and fresh_state.active:

        fresh_state.slice_start_time = None
        fresh_state.slice_request_id = None
        if slice_retry:
          fresh_state.slice_retries += 1
        fresh_state.put()
    try:
      _tx()

    except Exception, e:
      logging.warning(e)
      logging.warning(
          "Release lock for shard %s failed. Wait for lease to expire.",
          shard_state.shard_id)

  def handle(self):
    """Handle request."""
    tstate = model.TransientShardState.from_request(self.request)
    spec = tstate.mapreduce_spec
    self._start_time = self._time()

    shard_state, control = db.get([
        model.ShardState.get_key_by_shard_id(tstate.shard_id),
        model.MapreduceControl.get_key_by_job_id(spec.mapreduce_id),
    ])

    shard_state = self._try_acquire_lease(shard_state, tstate)
    if shard_state == self._TASK_STATE.RETRY_TASK:
      self.retry_task()
      return
    if shard_state == self._TASK_STATE.DROP_TASK:
      return

    ctx = context.Context(spec, shard_state,
                          task_retry_count=self.task_retry_count())

    if control and control.command == model.MapreduceControl.ABORT:
      logging.info("Abort command received by shard %d of job '%s'",
                   shard_state.shard_number, shard_state.mapreduce_id)


      shard_state.set_for_abort()
      shard_state.put(config=util.create_datastore_write_config(spec))
      return






    ndb_ctx = ndb.get_context()
    ndb_ctx.set_cache_policy(lambda key: False)
    ndb_ctx.set_memcache_policy(lambda key: False)

    context.Context._set(ctx)
    retry_directive = False

    try:
      self.process_inputs(
          tstate.input_reader, shard_state, tstate, ctx)

      if not shard_state.active:


        if (shard_state.result_status == model.ShardState.RESULT_SUCCESS and
            tstate.output_writer):




          tstate.output_writer.finalize(ctx, shard_state)

    except Exception, e:
      retry_directive = self._retry_logic(
          e, shard_state, tstate, spec.mapreduce_id)
    finally:
      context.Context._set(None)

    if retry_directive is None:
      return self.retry_task()
    self._save_state_and_schedule_next(shard_state, tstate, retry_directive)

  def process_inputs(self,
                     input_reader,
                     shard_state,
                     tstate,
                     ctx):
    """Read inputs, process them, and write out outputs.

    This is the core logic of MapReduce. It reads inputs from input reader,
    invokes user specified mapper function, and writes output with
    output writer. It also updates shard_state accordingly.
    e.g. if shard processing is done, set shard_state.active to False.

    If errors.FailJobError is caught, it will fail this MR job.
    All other exceptions will be logged and raised to taskqueue for retry
    until the number of retries exceeds a limit.

    Args:
      input_reader: input reader.
      shard_state: shard state.
      tstate: transient shard state.
      ctx: mapreduce context.
    """
    processing_limit = self._processing_limit(tstate.mapreduce_spec)
    if processing_limit == 0:
      return

    finished_shard = True

    for entity in input_reader:
      if isinstance(entity, db.Model):
        shard_state.last_work_item = repr(entity.key())
      elif isinstance(entity, ndb.Model):
        shard_state.last_work_item = repr(entity.key)
      else:
        shard_state.last_work_item = repr(entity)[:100]

      processing_limit -= 1

      if not self.process_data(
          entity, input_reader, ctx, tstate):
        finished_shard = False
        break
      elif processing_limit == 0:
        finished_shard = False
        break


    operation.counters.Increment(
        context.COUNTER_MAPPER_WALLTIME_MS,
        int((self._time() - self._start_time)*1000))(ctx)
    ctx.flush()

    if finished_shard:
      shard_state.set_for_success()

  def process_data(self, data, input_reader, ctx, transient_shard_state):
    """Process a single data piece.

    Call mapper handler on the data.

    Args:
      data: a datum to process.
      input_reader: input reader.
      ctx: mapreduce context
      transient_shard_state: transient shard state.

    Returns:
      True if scan should be continued, False if scan should be stopped.
    """
    if data is not input_readers.ALLOW_CHECKPOINT:
      ctx.counters.increment(context.COUNTER_MAPPER_CALLS)

      handler = transient_shard_state.handler

      if input_reader.expand_parameters:
        result = handler(*data)
      else:
        result = handler(data)

      if util.is_generator(result):
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

    if self._time() - self._start_time >= parameters._SLICE_DURATION_SEC:
      return False
    return True

  def _save_state_and_schedule_next(self, shard_state, tstate, retry_shard):
    """Save state to datastore and schedule next task for this shard.

    Update and save shard state. Schedule next slice if needed.
    This method handles interactions with datastore and taskqueue.

    Args:
      shard_state: model.ShardState for current shard.
      tstate: model.TransientShardState for current shard.
      retry_shard: whether to retry shard.
    """

    spec = tstate.mapreduce_spec
    config = util.create_datastore_write_config(spec)


    task = None
    if retry_shard:


      task = self._state_to_task(tstate, shard_state)
    elif shard_state.active:
      shard_state.advance_for_next_slice()
      tstate.advance_for_next_slice()
      countdown = self._get_countdown_for_next_slice(spec)
      task = self._state_to_task(tstate, shard_state, countdown=countdown)
    queue_name = os.environ.get("HTTP_X_APPENGINE_QUEUENAME", "default")

    @db.transactional(retries=5)
    def _tx():
      fresh_shard_state = model.ShardState.get_by_shard_id(tstate.shard_id)
      if not fresh_shard_state:
        raise db.Rollback()
      if (not fresh_shard_state.active or
          "worker_active_state_collision" in _TEST_INJECTED_FAULTS):
        logging.error("Shard %s is not active. Possible spurious task "
                      "execution. Dropping this task.", tstate.shard_id)
        logging.error("Datastore's %s", str(fresh_shard_state))
        logging.error("Slice's %s", str(shard_state))
        return
      fresh_shard_state.copy_from(shard_state)
      fresh_shard_state.put(config=config)




      if fresh_shard_state.active:
        assert task is not None


        self._add_task(task, spec, queue_name)

    try:
      _tx()
    except (datastore_errors.Error,
            taskqueue.Error,
            runtime.DeadlineExceededError,
            apiproxy_errors.Error), e:
      logging.error(
          "Can't transactionally continue shard. "
          "Will retry slice %s %s for the %s time.",
          tstate.shard_id,
          tstate.slice_id,
          self.task_retry_count() + 1)
      self._try_free_lease(shard_state)
      raise e
    finally:
      gc.collect()

  def _retry_logic(self, e, shard_state, tstate, mr_id):
    """Handle retry for this slice.

    This method may modify shard_state and tstate to prepare for retry or fail.

    Args:
      e: the exception caught.
      shard_state: model.ShardState for current shard.
      tstate: model.TransientShardState for current shard.
      mr_id: mapreduce id.

    Returns:
      True if shard should be retried. None if slice should be retried.
    False otherwise.
    """
    logging.error("Shard %s got error.", shard_state.shard_id)


    logging.error(traceback.format_exc())


    if type(e) is errors.FailJobError:
      logging.error("Got FailJobError. Shard %s failed permanently.",
                    shard_state.shard_id)
      shard_state.set_for_failure()
      return False

    if type(e) in errors.SHARD_RETRY_ERRORS:
      return self._attempt_shard_retry(shard_state, tstate, mr_id)
    else:
      if self._attempt_slice_retry(shard_state, tstate):
        return
      return False

  def _attempt_shard_retry(self, shard_state, tstate, mr_id):
    """Whether to retry shard.

    This method may modify shard_state and tstate to prepare for retry or fail.

    Args:
      shard_state: model.ShardState for current shard.
      tstate: model.TransientShardState for current shard.
      mr_id: mapreduce id.

    Returns:
      True if shard should be retried. False otherwise.
    """
    shard_retry = shard_state.retries
    permanent_shard_failure = False
    if shard_retry >= parameters.DEFAULT_SHARD_RETRY_LIMIT:
      logging.error(
          "Shard has been retried %s times. Shard %s will fail permanently.",
          shard_retry, shard_state.shard_id)
      permanent_shard_failure = True

    if tstate.output_writer and (
        not tstate.output_writer._can_be_retried(tstate)):
      logging.error("Can not retry shard. Shard %s failed permanently.",
                    shard_state.shard_id)
      permanent_shard_failure = True

    if permanent_shard_failure:
      shard_state.set_for_failure()
      return False

    shard_state.reset_for_retry()
    logging.error("Shard %s will be retried for the %s time.",
                  shard_state.shard_id,
                  shard_state.retries)
    output_writer = None
    if tstate.output_writer:
      mr_state = model.MapreduceState.get_by_job_id(mr_id)
      output_writer = tstate.output_writer.create(
          mr_state, shard_state)
    tstate.reset_for_retry(output_writer)
    return True

  def _attempt_slice_retry(self, shard_state, tstate):
    """Attempt to retry this slice.

    This method may modify shard_state and tstate to prepare for retry or fail.

    Args:
      shard_state: model.ShardState for current shard.
      tstate: model.TransientShardState for current shard.

    Returns:
      True when slice should be retried.
    False when slice can't be retried anymore.

    Raises:
      errors.RetrySliceError: in order to trigger a slice retry.
    """
    if shard_state.slice_retries < parameters._RETRY_SLICE_ERROR_MAX_RETRIES:
      logging.error(
          "Will retry slice %s %s for the %s time.",
          tstate.shard_id,
          tstate.slice_id,

          self.task_retry_count() + 1)



      sys.exc_clear()
      self._try_free_lease(shard_state, slice_retry=True)
      return True

    logging.error("Slice reached max retry limit of %s. "
                  "Shard %s failed permanently.",
                  self.task_retry_count(),
                  shard_state.shard_id)
    shard_state.set_for_failure()
    return False

  @staticmethod
  def get_task_name(shard_id, slice_id, retry=0):
    """Compute single worker task name.

    Args:
      shard_id: shard id.
      slice_id: slice id.
      retry: current shard retry count.

    Returns:
      task name which should be used to process specified shard/slice.
    """


    return "appengine-mrshard-%s-%s-retry-%s" % (
        shard_id, slice_id, retry)

  def _get_countdown_for_next_slice(self, spec):
    """Get countdown for next slice's task.

    When user sets processing rate, we set countdown to delay task execution.

    Args:
      spec: model.MapreduceSpec

    Returns:
      countdown in int.
    """
    countdown = 0
    if self._processing_limit(spec) != -1:
      countdown = max(
          int(parameters._SLICE_DURATION_SEC -
              (self._time() - self._start_time)), 0)
    return countdown

  @classmethod
  def _state_to_task(cls,
                     tstate,
                     shard_state,
                     eta=None,
                     countdown=None):
    """Generate task for slice according to current states.

    Args:
      tstate: An instance of TransientShardState.
      shard_state: An instance of ShardState.
      eta: Absolute time when the MR should execute. May not be specified
        if 'countdown' is also supplied. This may be timezone-aware or
        timezone-naive.
      countdown: Time in seconds into the future that this MR should execute.
        Defaults to zero.

    Returns:
      A model.HugeTask instance for the slice specified by current states.
    """
    base_path = tstate.base_path

    task_name = MapperWorkerCallbackHandler.get_task_name(
        tstate.shard_id,
        tstate.slice_id,
        tstate.retries)

    headers = util._get_task_headers(tstate.mapreduce_spec)
    headers[util._MR_SHARD_ID_TASK_HEADER] = tstate.shard_id

    worker_task = model.HugeTask(
        url=base_path + "/worker_callback",
        params=tstate.to_dict(),
        name=task_name,
        eta=eta,
        countdown=countdown,
        parent=shard_state,
        headers=headers)
    return worker_task

  @classmethod
  def _add_task(cls,
                worker_task,
                mapreduce_spec,
                queue_name):
    """Schedule slice scanning by adding it to the task queue.

    Args:
      worker_task: a model.HugeTask task for slice. This is NOT a taskqueue
        task.
      mapreduce_spec: an instance of model.MapreduceSpec.
      queue_name: Optional queue to run on; uses the current queue of
        execution or the default queue if unspecified.
    """
    if not _run_task_hook(mapreduce_spec.get_hooks(),
                          "enqueue_worker_task",
                          worker_task,
                          queue_name):
      try:


        worker_task.add(queue_name)
      except (taskqueue.TombstonedTaskError,
              taskqueue.TaskAlreadyExistsError), e:
        logging.warning("Task %r already exists. %s: %s",
                        worker_task.name,
                        e.__class__,
                        e)

  def _processing_limit(self, spec):
    """Get the limit on the number of map calls allowed by this slice.

    Args:
      spec: a Mapreduce spec.

    Returns:
      The limit as a positive int if specified by user. -1 otherwise.
    """
    processing_rate = float(spec.mapper.params.get("processing_rate", 0))
    slice_processing_limit = -1
    if processing_rate > 0:
      slice_processing_limit = int(math.ceil(
          parameters._SLICE_DURATION_SEC*processing_rate/
          int(spec.mapper.shard_count)))
    return slice_processing_limit



  @classmethod
  def _schedule_slice(cls,
                      shard_state,
                      tstate,
                      queue_name=None,
                      eta=None,
                      countdown=None):
    """Schedule slice scanning by adding it to the task queue.

    Args:
      shard_state: An instance of ShardState.
      tstate: An instance of TransientShardState.
      queue_name: Optional queue to run on; uses the current queue of
        execution or the default queue if unspecified.
      eta: Absolute time when the MR should execute. May not be specified
        if 'countdown' is also supplied. This may be timezone-aware or
        timezone-naive.
      countdown: Time in seconds into the future that this MR should execute.
        Defaults to zero.
    """
    queue_name = queue_name or os.environ.get("HTTP_X_APPENGINE_QUEUENAME",
                                              "default")
    task = cls._state_to_task(tstate, shard_state, eta, countdown)
    cls._add_task(task, tstate.mapreduce_spec, queue_name)


class ControllerCallbackHandler(base_handler.HugeTaskHandler):
  """Supervises mapreduce execution.

  Is also responsible for gathering execution status from shards together.

  This task is "continuously" running by adding itself again to taskqueue if
  and only if mapreduce is still active. A mapreduce is active if it has
  actively running shards.
  """

  def __init__(self, *args):
    """Constructor."""
    super(ControllerCallbackHandler, self).__init__(*args)
    self._time = time.time

  def _drop_gracefully(self):
    """Gracefully drop controller task.

    This method is called when decoding controller task payload failed.
    Upon this we mark ShardState and MapreduceState as failed so all
    tasks can stop.

    Writing to datastore is forced (ignore read-only mode) because we
    want the tasks to stop badly, and if force_writes was False,
    the job would have never been started.
    """
    mr_id = self.request.headers[util._MR_ID_TASK_HEADER]
    state = model.MapreduceState.get_by_job_id(mr_id)
    if not state or not state.active:
      return

    state.active = False
    state.result_status = model.MapreduceState.RESULT_FAILED
    shard_states = model.ShardState.find_by_mapreduce_state(state)
    puts = []
    for ss in shard_states:
      if ss.active:
        ss.set_for_failure()
        puts.append(ss)
    config = util.create_datastore_write_config(state.mapreduce_spec)
    db.put(puts, config=config)

    db.put(state, config=config)

  def handle(self):
    """Handle request."""
    spec = model.MapreduceSpec.from_json_str(
        self.request.get("mapreduce_spec"))
    state, control = db.get([
        model.MapreduceState.get_key_by_job_id(spec.mapreduce_id),
        model.MapreduceControl.get_key_by_job_id(spec.mapreduce_id),
    ])

    if not state:
      logging.warning("State not found for MR '%s'; dropping controller task.",
                      spec.mapreduce_id)
      return
    if not state.active:
      logging.warning(
          "MR %r is not active. Looks like spurious controller task execution.",
          spec.mapreduce_id)
      self._clean_up_mr(spec, self.base_path())
      return

    shard_states = model.ShardState.find_by_mapreduce_state(state)
    if len(shard_states) != spec.mapper.shard_count:
      logging.error("Found %d shard states. Expect %d. "
                    "Issuing abort command to job '%s'",
                    len(shard_states), spec.mapper.shard_count,
                    spec.mapreduce_id)

      model.MapreduceControl.abort(spec.mapreduce_id)

    self._update_state_from_shard_states(state, shard_states, control)

    if state.active:
      ControllerCallbackHandler.reschedule(
          state, self.base_path(), spec, self.serial_id() + 1)

  def _update_state_from_shard_states(self, state, shard_states, control):
    """Update mr state by examing shard states.

    Args:
      state: current mapreduce state as MapreduceState.
      shard_states: all shard states (active and inactive). list of ShardState.
      control: model.MapreduceControl entity.
    """
    active_shards = [s for s in shard_states if s.active]
    failed_shards = [s for s in shard_states
                     if s.result_status == model.ShardState.RESULT_FAILED]
    aborted_shards = [s for s in shard_states
                     if s.result_status == model.ShardState.RESULT_ABORTED]
    spec = state.mapreduce_spec



    state.active = bool(active_shards)
    state.active_shards = len(active_shards)
    state.failed_shards = len(failed_shards)
    state.aborted_shards = len(aborted_shards)
    if not control and (failed_shards or aborted_shards):

      model.MapreduceControl.abort(spec.mapreduce_id)

    self._aggregate_stats(state, shard_states)
    state.last_poll_time = datetime.datetime.utcfromtimestamp(self._time())

    if not state.active:

      if failed_shards or not shard_states:
        state.result_status = model.MapreduceState.RESULT_FAILED


      elif aborted_shards:
        state.result_status = model.MapreduceState.RESULT_ABORTED
      else:
        state.result_status = model.MapreduceState.RESULT_SUCCESS
      self._finalize_outputs(spec, state)
      self._finalize_job(spec, state, self.base_path())
    else:
      @db.transactional(retries=5)
      def _put_state():
        fresh_state = model.MapreduceState.get_by_job_id(spec.mapreduce_id)


        if not fresh_state.active:
          logging.warning(
              "Job %s is not active. Looks like spurious task execution. "
              "Dropping controller task.", spec.mapreduce_id)
          return
        config = util.create_datastore_write_config(spec)
        state.put(config=config)

      _put_state()

  def _aggregate_stats(self, mapreduce_state, shard_states):
    """Update stats in mapreduce state by aggregating stats from shard states.

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

  def serial_id(self):
    """Get serial unique identifier of this task from request.

    Returns:
      serial identifier as int.
    """
    return int(self.request.get("serial_id"))

  @classmethod
  def _finalize_outputs(cls, mapreduce_spec, mapreduce_state):
    """Finalize outputs.

    Args:
      mapreduce_spec: an instance of MapreduceSpec.
      mapreduce_state: an instance of MapreduceState.
    """

    if (mapreduce_spec.mapper.output_writer_class() and
        mapreduce_state.result_status == model.MapreduceState.RESULT_SUCCESS):
      mapreduce_spec.mapper.output_writer_class().finalize_job(mapreduce_state)

  @classmethod
  def _finalize_job(cls, mapreduce_spec, mapreduce_state, base_path):
    """Finalize job execution.

    Invokes done callback and save mapreduce state in a transaction,
    and schedule necessary clean ups. This method is idempotent.

    Args:
      mapreduce_spec: an instance of MapreduceSpec
      mapreduce_state: an instance of MapreduceState
      base_path: handler_base path.
    """
    config = util.create_datastore_write_config(mapreduce_spec)
    queue_name = util.get_queue_name(mapreduce_spec.params.get(
        model.MapreduceSpec.PARAM_DONE_CALLBACK_QUEUE))
    done_callback = mapreduce_spec.params.get(
        model.MapreduceSpec.PARAM_DONE_CALLBACK)
    done_task = None
    if done_callback:
      done_task = taskqueue.Task(
          url=done_callback,
          headers=util._get_task_headers(mapreduce_spec,
                                         util.CALLBACK_MR_ID_TASK_HEADER),
          method=mapreduce_spec.params.get("done_callback_method", "POST"))

    @db.transactional(retries=5)
    def _put_state():
      fresh_state = model.MapreduceState.get_by_job_id(
          mapreduce_spec.mapreduce_id)
      if not fresh_state.active:
        logging.warning(
            "Job %s is not active. Looks like spurious task execution. "
            "Dropping task.", mapreduce_spec.mapreduce_id)
        return
      mapreduce_state.put(config=config)

      if done_task and not _run_task_hook(
          mapreduce_spec.get_hooks(),
          "enqueue_done_task",
          done_task,
          queue_name):
        done_task.add(queue_name, transactional=True)

    _put_state()
    logging.info("Final result for job '%s' is '%s'",
                 mapreduce_spec.mapreduce_id, mapreduce_state.result_status)
    cls._clean_up_mr(mapreduce_spec, base_path)

  @classmethod
  def _clean_up_mr(cls, mapreduce_spec, base_path):
    FinalizeJobHandler.schedule(base_path, mapreduce_spec)

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

    controller_callback_task = model.HugeTask(
        url=base_path + "/controller_callback",
        name=task_name, params=task_params,
        countdown=parameters._CONTROLLER_PERIOD_SEC,
        parent=mapreduce_state,
        headers=util._get_task_headers(mapreduce_spec))

    if not _run_task_hook(mapreduce_spec.get_hooks(),
                          "enqueue_controller_task",
                          controller_callback_task,
                          queue_name):
      try:
        controller_callback_task.add(queue_name)
      except (taskqueue.TombstonedTaskError,
              taskqueue.TaskAlreadyExistsError), e:
        logging.warning("Task %r with params %r already exists. %s: %s",
                        task_name, task_params, e.__class__, e)


class KickOffJobHandler(base_handler.TaskQueueHandler):
  """Taskqueue handler which kicks off a mapreduce processing.

  This handler is idempotent.

  Precondition:
    The Model.MapreduceState entity for this mr is already created and
    saved to datastore by StartJobHandler._start_map.

  Request Parameters:
    mapreduce_id: in string.
  """


  _SERIALIZED_INPUT_READERS_KEY = "input_readers_for_mr_%s"

  def handle(self):
    """Handles kick off request."""

    mr_id = self.request.get("mapreduce_id")

    logging.info("Processing kickoff for job %s", mr_id)
    state = model.MapreduceState.get_by_job_id(mr_id)
    if not self._check_mr_state(state, mr_id):
      return


    readers, serialized_readers_entity = self._get_input_readers(state)
    if readers is None:

      logging.warning("Found no mapper input data to process.")
      state.active = False
      state.result_status = model.MapreduceState.RESULT_SUCCESS
      ControllerCallbackHandler._finalize_job(
          state.mapreduce_spec, state, self.base_path())
      return False


    self._setup_output_writer(state)



    result = self._save_states(state, serialized_readers_entity)
    if result is None:
      readers, _ = self._get_input_readers(state)
    elif not result:
      return

    queue_name = self.request.headers.get("X-AppEngine-QueueName")
    KickOffJobHandler._schedule_shards(state.mapreduce_spec, readers,
                                       queue_name, self.base_path(), state)

    ControllerCallbackHandler.reschedule(
        state, self.base_path(), state.mapreduce_spec, serial_id=0,
        queue_name=queue_name)

  def _get_input_readers(self, state):
    """Get input readers.

    Args:
      state: a MapreduceState model.

    Returns:
      A tuple: (a list of input readers, a model._HugeTaskPayload entity).
    The payload entity contains the json serialized input readers.
    (None, None) when input reader inplitting returned no data to process.
    """
    serialized_input_readers_key = (self._SERIALIZED_INPUT_READERS_KEY %
                                    state.key().id_or_name())
    serialized_input_readers = model._HugeTaskPayload.get_by_key_name(
        serialized_input_readers_key, parent=state)


    input_reader_class = state.mapreduce_spec.mapper.input_reader_class()
    if serialized_input_readers is None:
      readers = input_reader_class.split_input(
          state.mapreduce_spec.mapper)
    else:
      readers = [input_reader_class.from_json_str(json) for json in
                 simplejson.loads(serialized_input_readers.payload)]

    if not readers:
      return None, None


    state.mapreduce_spec.mapper.shard_count = len(readers)
    state.active_shards = len(readers)


    if serialized_input_readers is None:

      serialized_input_readers = model._HugeTaskPayload(
          key_name=serialized_input_readers_key, parent=state)
      readers_json_str = [i.to_json_str() for i in readers]
      serialized_input_readers.payload = simplejson.dumps(readers_json_str)
    return readers, serialized_input_readers

  def _setup_output_writer(self, state):
    if not state.writer_state:
      output_writer_class = state.mapreduce_spec.mapper.output_writer_class()
      if output_writer_class:
        output_writer_class.init_job(state)

  @db.transactional
  def _save_states(self, state, serialized_readers_entity):
    """Run transaction to save state.

    Args:
      state: a model.MapreduceState entity.
      serialized_readers_entity: a model._HugeTaskPayload entity containing
        json serialized input readers.

    Returns:
      False if a fatal error is encountered and this task should be dropped
    immediately. True if transaction is successful. None if a previous
    attempt of this same transaction has already succeeded.
    """
    mr_id = state.key().id_or_name()
    fresh_state = model.MapreduceState.get_by_job_id(mr_id)
    if not self._check_mr_state(fresh_state, mr_id):
      return False
    if fresh_state.active_shards != 0:
      logging.warning(
          "Mapreduce %s already has active shards. Looks like spurious task "
          "execution.", mr_id)
      return None
    config = util.create_datastore_write_config(state.mapreduce_spec)
    db.put([state, serialized_readers_entity], config=config)
    return True

  @classmethod
  def _schedule_shards(cls,
                       spec,
                       readers,
                       queue_name,
                       base_path,
                       mr_state):
    """Prepares shard states and schedules their execution.

    Even though this method does not schedule shard task and save shard state
    transactionally, it's safe for taskqueue to retry this logic because
    the initial shard_state for each shard is the same from any retry.
    This is an important yet reasonable assumption on model.ShardState.

    Args:
      spec: mapreduce specification as MapreduceSpec.
      readers: list of InputReaders describing shard splits.
      queue_name: The queue to run this job on.
      base_path: The base url path of mapreduce callbacks.
      mr_state: The MapReduceState of current job.
    """

    shard_states = []
    for shard_number, input_reader in enumerate(readers):
      shard_state = model.ShardState.create_new(spec.mapreduce_id, shard_number)
      shard_state.shard_description = str(input_reader)
      shard_states.append(shard_state)


    writer_class = spec.mapper.output_writer_class()
    writers = [None] * len(readers)
    if writer_class:
      for shard_number, shard_state in enumerate(shard_states):
        writers[shard_number] = writer_class.create(mr_state, shard_state)


    existing_shard_states = db.get(shard.key() for shard in shard_states)
    existing_shard_keys = set(shard.key() for shard in existing_shard_states
                              if shard is not None)


    db.put((shard for shard in shard_states
            if shard.key() not in existing_shard_keys),
           config=util.create_datastore_write_config(spec))
















    for shard_number, (input_reader, output_writer) in enumerate(
        zip(readers, writers)):
      shard_id = model.ShardState.shard_id_from_number(
          spec.mapreduce_id, shard_number)
      task = MapperWorkerCallbackHandler._state_to_task(
          model.TransientShardState(
              base_path, spec, shard_id, 0, input_reader, input_reader,
              output_writer=output_writer),
          shard_states[shard_number])
      MapperWorkerCallbackHandler._add_task(task,
                                            spec,
                                            queue_name)

  @classmethod
  def _check_mr_state(cls, state, mr_id):
    """Check MapreduceState.

    Args:
      state: an MapreduceState instance.
      mr_id: mapreduce id.

    Returns:
      True if state is valid. False if not and this task should be dropped.
    """
    if state is None:
      logging.warning(
          "Mapreduce State for job %s is missing. Dropping Task.",
          mr_id)
      return False
    if not state.active:
      logging.warning(
          "Mapreduce %s is not active. Looks like spurious task "
          "execution. Dropping Task.", mr_id)
      return False
    return True


class StartJobHandler(base_handler.PostJsonHandler):
  """Command handler starts a mapreduce job.

  This handler allows user to start a mr via a web form. It's _start_map
  method can also be used independently to start a mapreduce.
  """

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
        "processing_rate") or parameters._DEFAULT_PROCESSING_RATE_PER_SEC)
    queue_name = mapper_params["queue_name"] = util.get_queue_name(
        mapper_params.get("queue_name", None))


    mapper_spec = model.MapperSpec(
        mapper_handler_spec,
        mapper_input_reader_spec,
        mapper_params,
        int(mapper_params.get("shard_count", parameters.DEFAULT_SHARD_COUNT)),
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
                 base_path,
                 queue_name,
                 eta=None,
                 countdown=None,
                 hooks_class_name=None,
                 _app=None,
                 in_xg_transaction=False):


    """See control.start_map.

    Requirements for this method:
    1. The request that invokes this method can either be regular or
       from taskqueue. So taskqueue specific headers can not be used.
    2. Each invocation transactionally starts an isolated mapreduce job with
       a unique id. MapreduceState should be immediately available after
       returning. See control.start_map's doc on transactional.
    3. Method should be lightweight.
    """

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

      mapper_spec.handler
    finally:
      context.Context._set(None)


    if in_xg_transaction:
      propagation = db.MANDATORY
    else:
      propagation = db.INDEPENDENT

    @db.transactional(propagation=propagation)
    def _txn():
      cls._create_and_save_state(mapreduce_spec, _app)
      cls._add_kickoff_task(base_path, mapreduce_spec, eta,
                            countdown, queue_name)
    _txn()

    return mapreduce_id

  @classmethod
  def _create_and_save_state(cls, mapreduce_spec, _app):
    """Save mapreduce state to datastore.

    Save state to datastore so that UI can see it immediately.

    Args:
      mapreduce_spec: model.MapreduceSpec,
      _app: app id if specified. None otherwise.

    Returns:
      The saved Mapreduce state.
    """
    state = model.MapreduceState.create_new(mapreduce_spec.mapreduce_id)
    state.mapreduce_spec = mapreduce_spec
    state.active = True
    state.active_shards = 0
    if _app:
      state.app_id = _app
    config = util.create_datastore_write_config(mapreduce_spec)
    state.put(config=config)
    return state

  @classmethod
  def _add_kickoff_task(cls,
                        base_path,
                        mapreduce_spec,
                        eta,
                        countdown,
                        queue_name):
    params = {"mapreduce_id": mapreduce_spec.mapreduce_id}

    kickoff_task = taskqueue.Task(
        url=base_path + "/kickoffjob_callback",
        headers=util._get_task_headers(mapreduce_spec),
        params=params,
        eta=eta,
        countdown=countdown)
    hooks = mapreduce_spec.get_hooks()
    if hooks is not None:
      try:
        hooks.enqueue_kickoff_task(kickoff_task, queue_name)
        return
      except NotImplementedError:
        pass
    kickoff_task.add(queue_name, transactional=True)


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
        db.delete(model._HugeTaskPayload.all().ancestor(shard_state),
                  config=config)
      db.delete(model._HugeTaskPayload.all().ancestor(mapreduce_state),
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
        params={"mapreduce_id": mapreduce_spec.mapreduce_id},
        headers=util._get_task_headers(mapreduce_spec))
    queue_name = util.get_queue_name(None)
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

    mapreduce_state = model.MapreduceState.get_by_job_id(mapreduce_id)
    if mapreduce_state:
      shard_keys = model.ShardState.calculate_keys_by_mapreduce_state(
          mapreduce_state)
      db.delete(shard_keys)
      db.delete(mapreduce_state)
    self.json_response["status"] = ("Job %s successfully cleaned up." %
                                    mapreduce_id)


class AbortJobHandler(base_handler.PostJsonHandler):
  """Command to abort a running job."""

  def handle(self):
    model.MapreduceControl.abort(self.request.get("mapreduce_id"))
    self.json_response["status"] = "Abort signal sent."
