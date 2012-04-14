"""Context class."""

import logging
import sys

from google.appengine.api import datastore  # For taskqueue coordination
from google.appengine.api import datastore_errors
from google.appengine.api import memcache
from google.appengine.api import namespace_manager
from google.appengine.datastore import datastore_rpc
from google.appengine.datastore import entity_pb

from google.net.proto import ProtocolBuffer

from . import key as key_module
from . import model
from . import tasklets
from . import eventloop
from . import utils

logging_debug = utils.logging_debug

_LOCK_TIME = 32  # Time to lock out memcache.add() after datastore updates.
_LOCKED = 0  # Special value to store in memcache indicating locked value.


class ContextOptions(datastore_rpc.TransactionOptions):
  """Configuration options that may be passed along with get/put/delete."""

  @datastore_rpc.ConfigOption
  def use_cache(value):
    if not isinstance(value, bool):
      raise datastore_errors.BadArgumentError(
        'use_cache should be a bool (%r)' % (value,))
    return value

  @datastore_rpc.ConfigOption
  def use_memcache(value):
    if not isinstance(value, bool):
      raise datastore_errors.BadArgumentError(
        'use_memcache should be a bool (%r)' % (value,))
    return value

  @datastore_rpc.ConfigOption
  def use_datastore(value):
    if not isinstance(value, bool):
      raise datastore_errors.BadArgumentError(
        'use_datastore should be a bool (%r)' % (value,))
    return value

  @datastore_rpc.ConfigOption
  def memcache_timeout(value):
    if not isinstance(value, (int, long)):
      raise datastore_errors.BadArgumentError(
        'memcache_timeout should be an integer (%r)' % (value,))
    return value

  @datastore_rpc.ConfigOption
  def max_memcache_items(value):
    if not isinstance(value, (int, long)):
      raise datastore_errors.BadArgumentError(
        'max_memcache_items should be an integer (%r)' % (value,))
    return value


# options and config can be used interchangeably.
_OPTION_TRANSLATIONS = {
  'options': 'config',
}


def _make_ctx_options(ctx_options):
  """Helper to construct a ContextOptions object from keyword arguments.

  Args:
    ctx_options: a dict of keyword arguments.

  Note that either 'options' or 'config' can be used to pass another
  ContextOptions object, but not both.  If another ContextOptions
  object is given it provides default values.

  Returns:
    A ContextOptions object, or None if ctx_options is empty.
  """
  if not ctx_options:
    return None
  for key in list(ctx_options):
    translation = _OPTION_TRANSLATIONS.get(key)
    if translation:
      if translation in ctx_options:
        raise ValueError('Cannot specify %s and %s at the same time' %
                         (key, translation))
      ctx_options[translation] = ctx_options.pop(key)
  return ContextOptions(**ctx_options)


class AutoBatcher(object):

  def __init__(self, todo_tasklet, limit):
    # todo_tasklet is a tasklet to be called with list of (future, arg) pairs
    self._todo_tasklet = todo_tasklet
    self._limit = limit  # No more than this many per callback
    self._queues = {}  # Map options to lists of (future, arg) tuples
    self._running = []  # Currently running tasklets
    self._cache = {}  # Cache of in-flight todo_tasklet futures

  def __repr__(self):
    return '%s(%s)' % (self.__class__.__name__, self._todo_tasklet.__name__)

  def run_queue(self, options, todo):
    logging_debug('AutoBatcher(%s): %d items',
                  self._todo_tasklet.__name__, len(todo))
    fut = self._todo_tasklet(todo, options)
    self._running.append(fut)
    # Add a callback when we're done.
    fut.add_callback(self._finished_callback, fut)

  def _on_idle(self):
    if not self.action():
      return None
    return True

  def add(self, arg, options=None):
    fut = tasklets.Future('%s.add(%s, %s)' % (self, arg, options))
    todo = self._queues.get(options)
    if todo is None:
      logging_debug('AutoBatcher(%s): creating new queue for %r',
                    self._todo_tasklet.__name__, options)
      if not self._queues:
        eventloop.add_idle(self._on_idle)
      todo = self._queues[options] = []
    todo.append((fut, arg))
    if len(todo) >= self._limit:
      del self._queues[options]
      self.run_queue(options, todo)
    return fut

  def add_once(self, arg, options=None):
    cache_key = (arg, options)
    fut = self._cache.get(cache_key)
    if fut is None:
      fut = self.add(arg, options)
      self._cache[cache_key] = fut
      fut.add_immediate_callback(self._cache.__delitem__, cache_key)
    return fut

  def action(self):
    queues = self._queues
    if not queues:
      return False
    options, todo = queues.popitem()  # TODO: Should this use FIFO ordering?
    self.run_queue(options, todo)
    return True

  def _finished_callback(self, fut):
    self._running.remove(fut)
    fut.check_success()

  @tasklets.tasklet
  def flush(self):
    while self._running or self.action():
      if self._running:
        yield self._running  # A list of Futures


class Context(object):

  def __init__(self, conn=None, auto_batcher_class=AutoBatcher, config=None):
    # NOTE: If conn is not None, config is only used to get the
    # auto-batcher limits.
    if conn is None:
      conn = model.make_connection(config)
    self._conn = conn
    self._auto_batcher_class = auto_batcher_class
    # Get the get/put/delete limits (defaults 1000, 500, 500).
    # Note that the explicit config passed in overrides the config
    # attached to the connection, if it was passed in.
    max_get = (datastore_rpc.Configuration.max_get_keys(config, conn.config) or
               datastore_rpc.Connection.MAX_GET_KEYS)
    max_put = (datastore_rpc.Configuration.max_put_entities(config,
                                                            conn.config) or
               datastore_rpc.Connection.MAX_PUT_ENTITIES)
    max_delete = (datastore_rpc.Configuration.max_delete_keys(config,
                                                              conn.config) or
                  datastore_rpc.Connection.MAX_DELETE_KEYS)
    # Create the get/put/delete auto-batchers.
    self._get_batcher = auto_batcher_class(self._get_tasklet, max_get)
    self._put_batcher = auto_batcher_class(self._put_tasklet, max_put)
    self._delete_batcher = auto_batcher_class(self._delete_tasklet, max_delete)
    # We only have a single limit for memcache (default 1000).
    max_memcache = (ContextOptions.max_memcache_items(config, conn.config) or
                    datastore_rpc.Connection.MAX_GET_KEYS)
    # Create the memcache auto-batchers.
    self._memcache_get_batcher = auto_batcher_class(self._memcache_get_tasklet,
                                                    max_memcache)
    self._memcache_set_batcher = auto_batcher_class(self._memcache_set_tasklet,
                                                    max_memcache)
    self._memcache_del_batcher = auto_batcher_class(self._memcache_del_tasklet,
                                                    max_memcache)
    self._memcache_off_batcher = auto_batcher_class(self._memcache_off_tasklet,
                                                    max_memcache)
    # Create a list of batchers for flush().
    self._batchers = [self._get_batcher,
                      self._put_batcher,
                      self._delete_batcher,
                      self._memcache_get_batcher,
                      self._memcache_set_batcher,
                      self._memcache_del_batcher,
                      self._memcache_off_batcher,
                      ]
    self._cache = {}
    self._memcache = memcache.Client()

  # NOTE: The default memcache prefix is altered if an incompatible change is
  # required. Remember to check release notes when using a custom prefix.
  _memcache_prefix = 'NDB9:'  # TODO: Might make this configurable.

  @tasklets.tasklet
  def flush(self):
    # Rinse and repeat until all batchers are completely out of work.
    more = True
    while more:
      yield [batcher.flush() for batcher in self._batchers]
      more = False
      for batcher in self._batchers:
        if batcher._running or batcher._queues:
          more = True
          break

  @tasklets.tasklet
  def _get_tasklet(self, todo, options):
    if not todo:
      raise RuntimeError('Nothing to do.')
    # Make the datastore RPC call.
    datastore_keys = []
    for unused_fut, key in todo:
      datastore_keys.append(key)
    # Now wait for the datastore RPC(s) and pass the results to the futures.
    entities = yield self._conn.async_get(options, datastore_keys)
    for ent, (fut, unused_key) in zip(entities, todo):
      fut.set_result(ent)

  @tasklets.tasklet
  def _put_tasklet(self, todo, options):
    if not todo:
      raise RuntimeError('Nothing to do.')
    # TODO: What if the same entity is being put twice?
    # TODO: What if two entities with the same key are being put?
    datastore_entities = []
    for unused_fut, ent in todo:
      datastore_entities.append(ent)
    # Wait for datastore RPC(s).
    keys = yield self._conn.async_put(options, datastore_entities)
    for key, (fut, ent) in zip(keys, todo):
      if key != ent._key:
        if ent._has_complete_key():
          raise datastore_errors.BadKeyError(
              'Entity key differs from the one returned by the datastore. '
              'Expected %r, got %r' % (key, ent._key))
        ent._key = key
      fut.set_result(key)

  @tasklets.tasklet
  def _delete_tasklet(self, todo, options):
    if not todo:
      raise RuntimeError('Nothing to do.')
    futures = []
    datastore_keys = []
    for fut, key in todo:
      futures.append(fut)
      datastore_keys.append(key)
    # Wait for datastore RPC(s).
    yield self._conn.async_delete(options, datastore_keys)
    # Send a dummy result to all original Futures.
    for fut in futures:
      fut.set_result(None)

  # TODO: Unify the policy docstrings (they're getting too verbose).

  # All the policy functions may also:
  # - be a constant of the right type (instead of a function);
  # - return None (instead of a value of the right type);
  # - be None (instead of a function or constant).

  # Model classes may define class variables or class methods
  # _use_{cache,memcache,datastore} or _memcache_timeout to set the
  # default policy of that type for that class.

  @staticmethod
  def default_cache_policy(key):
    """Default cache policy.

    This defers to _use_cache on the Model class.

    Args:
      key: Key instance.

    Returns:
      A bool or None.
    """
    flag = None
    if key is not None:
      modelclass = model.Model._kind_map.get(key.kind())
      if modelclass is not None:
        policy = getattr(modelclass, '_use_cache', None)
        if policy is not None:
          if isinstance(policy, bool):
            flag = policy
          else:
            flag = policy(key)
    return flag

  _cache_policy = default_cache_policy

  def get_cache_policy(self):
    """Return the current context cache policy function.

    Returns:
      A function that accepts a Key instance as argument and returns
      a bool indicating if it should be cached.  May be None.
    """
    return self._cache_policy

  def set_cache_policy(self, func):
    """Set the context cache policy function.

    Args:
      func: A function that accepts a Key instance as argument and returns
        a bool indicating if it should be cached.  May be None.
    """
    if func is None:
      func = self.default_cache_policy
    elif isinstance(func, bool):
      func = lambda unused_key, flag=func: flag
    self._cache_policy = func

  def _use_cache(self, key, options=None):
    """Return whether to use the context cache for this key.

    Args:
      key: Key instance.
      options: ContextOptions instance, or None.

    Returns:
      True if the key should be cached, False otherwise.
    """
    flag = ContextOptions.use_cache(options)
    if flag is None:
      flag = self._cache_policy(key)
    if flag is None:
      flag = ContextOptions.use_cache(self._conn.config)
    if flag is None:
      flag = True
    return flag

  @staticmethod
  def default_memcache_policy(key):
    """Default memcache policy.

    This defers to _use_memcache on the Model class.

    Args:
      key: Key instance.

    Returns:
      A bool or None.
    """
    flag = None
    if key is not None:
      modelclass = model.Model._kind_map.get(key.kind())
      if modelclass is not None:
        policy = getattr(modelclass, '_use_memcache', None)
        if policy is not None:
          if isinstance(policy, bool):
            flag = policy
          else:
            flag = policy(key)
    return flag

  _memcache_policy = default_memcache_policy

  def get_memcache_policy(self):
    """Return the current memcache policy function.

    Returns:
      A function that accepts a Key instance as argument and returns
      a bool indicating if it should be cached.  May be None.
    """
    return self._memcache_policy

  def set_memcache_policy(self, func):
    """Set the memcache policy function.

    Args:
      func: A function that accepts a Key instance as argument and returns
        a bool indicating if it should be cached.  May be None.
    """
    if func is None:
      func = self.default_memcache_policy
    elif isinstance(func, bool):
      func = lambda unused_key, flag=func: flag
    self._memcache_policy = func

  def _use_memcache(self, key, options=None):
    """Return whether to use memcache for this key.

    Args:
      key: Key instance.
      options: ContextOptions instance, or None.

    Returns:
      True if the key should be cached in memcache, False otherwise.
    """
    flag = ContextOptions.use_memcache(options)
    if flag is None:
      flag = self._memcache_policy(key)
    if flag is None:
      flag = ContextOptions.use_memcache(self._conn.config)
    if flag is None:
      flag = True
    return flag

  @staticmethod
  def default_datastore_policy(key):
    """Default datastore policy.

    This defers to _use_datastore on the Model class.

    Args:
      key: Key instance.

    Returns:
      A bool or None.
    """
    flag = None
    if key is not None:
      modelclass = model.Model._kind_map.get(key.kind())
      if modelclass is not None:
        policy = getattr(modelclass, '_use_datastore', None)
        if policy is not None:
          if isinstance(policy, bool):
            flag = policy
          else:
            flag = policy(key)
    return flag

  _datastore_policy = default_datastore_policy

  def get_datastore_policy(self):
    """Return the current context datastore policy function.

    Returns:
      A function that accepts a Key instance as argument and returns
      a bool indicating if it should use the datastore.  May be None.
    """
    return self._datastore_policy

  def set_datastore_policy(self, func):
    """Set the context datastore policy function.

    Args:
      func: A function that accepts a Key instance as argument and returns
        a bool indicating if it should use the datastore.  May be None.
    """
    if func is None:
      func = self.default_datastore_policy
    elif isinstance(func, bool):
      func = lambda unused_key, flag=func: flag
    self._datastore_policy = func

  def _use_datastore(self, key, options=None):
    """Return whether to use the datastore for this key.

    Args:
      key: Key instance.
      options: ContextOptions instance, or None.

    Returns:
      True if the datastore should be used, False otherwise.
    """
    flag = ContextOptions.use_datastore(options)
    if flag is None:
      flag = self._datastore_policy(key)
    if flag is None:
      flag = ContextOptions.use_datastore(self._conn.config)
    if flag is None:
      flag = True
    return flag

  @staticmethod
  def default_memcache_timeout_policy(key):
    """Default memcache timeout policy.

    This defers to _memcache_timeout on the Model class.

    Args:
      key: Key instance.

    Returns:
      Memcache timeout to use (integer), or None.
    """
    timeout = None
    if key is not None and isinstance(key, model.Key):
      modelclass = model.Model._kind_map.get(key.kind())
      if modelclass is not None:
        policy = getattr(modelclass, '_memcache_timeout', None)
        if policy is not None:
          if isinstance(policy, (int, long)):
            timeout = policy
          else:
            timeout = policy(key)
    return timeout

  _memcache_timeout_policy = default_memcache_timeout_policy

  def set_memcache_timeout_policy(self, func):
    """Set the policy function for memcache timeout (expiration).

    Args:
      func: A function that accepts a key instance as argument and returns
        an integer indicating the desired memcache timeout.  May be None.

    If the function returns 0 it implies the default timeout.
    """
    if func is None:
      func = self.default_memcache_timeout_policy
    elif isinstance(func, (int, long)):
      func = lambda unused_key, flag=func: flag
    self._memcache_timeout_policy = func

  def get_memcache_timeout_policy(self):
    """Return the current policy function for memcache timeout (expiration)."""
    return self._memcache_timeout_policy

  def _get_memcache_timeout(self, key, options=None):
    """Return the memcache timeout (expiration) for this key."""
    timeout = ContextOptions.memcache_timeout(options)
    if timeout is None:
      timeout = self._memcache_timeout_policy(key)
    if timeout is None:
      timeout = ContextOptions.memcache_timeout(self._conn.config)
    if timeout is None:
      timeout = 0
    return timeout

  # TODO: What about conflicting requests to different autobatchers,
  # e.g. tasklet A calls get() on a given key while tasklet B calls
  # delete()?  The outcome is nondeterministic, depending on which
  # autobatcher gets run first.  Maybe we should just flag such
  # conflicts as errors, with an overridable policy to resolve them
  # differently?

  @tasklets.tasklet
  def get(self, key, **ctx_options):
    """Return a Model instance given the entity key.

    It will use the context cache if the cache policy for the given
    key is enabled.

    Args:
      key: Key instance.
      **ctx_options: Context options.

    Returns:
      A Model instance it the key exists in the datastore; None otherwise.
    """
    options = _make_ctx_options(ctx_options)
    use_cache = self._use_cache(key, options)
    if use_cache:
      if key in self._cache:
        entity = self._cache[key]  # May be None, meaning "doesn't exist".
        if entity is None or entity._key == key:
          # If entity's key didn't change later, it is ok.
          # See issue #13.  http://goo.gl/jxjOP
          raise tasklets.Return(entity)

    use_datastore = self._use_datastore(key, options)
    use_memcache = self._use_memcache(key, options)
    using_tconn = isinstance(self._conn, datastore_rpc.TransactionalConnection)
    in_transaction = (use_datastore and using_tconn)
    ns = key.namespace()

    if use_memcache and not in_transaction:
      mkey = self._memcache_prefix + key.urlsafe()
      mvalue = yield self.memcache_get(mkey, for_cas=use_datastore,
                                       namespace=ns, use_cache=True)
      if mvalue not in (_LOCKED, None):
        cls = model.Model._kind_map.get(key.kind())
        if cls is None:
          raise TypeError('Cannot find model class for kind %s' % key.kind())
        pb = entity_pb.EntityProto()

        try:
          pb.MergePartialFromString(mvalue)
        except ProtocolBuffer.ProtocolBufferDecodeError:
          logging.warning('Corrupt memcache entry found '
                          'with key %s and namespace %s' % (mkey, ns))
          mvalue = None
        else:
          entity = cls._from_pb(pb)
          # Store the key on the entity since it wasn't written to memcache.
          entity._key = key
          raise tasklets.Return(entity)

      if mvalue is None and use_datastore:
        yield self.memcache_set(mkey, _LOCKED, time=_LOCK_TIME, namespace=ns,
                                use_cache=True)
        yield self.memcache_gets(mkey, namespace=ns, use_cache=True)
    if not use_datastore:
      raise tasklets.Return(None)

    if use_cache:
      entity = yield self._get_batcher.add_once(key, options)
    else:
      entity = yield self._get_batcher.add(key, options)

    if entity is not None:
      if not in_transaction and use_memcache and mvalue != _LOCKED:
        # Don't serialize the key since it's already the memcache key.
        pbs = entity._to_pb(set_key=False).SerializePartialToString()
        timeout = self._get_memcache_timeout(key, options)
        # Don't yield -- this can run in the background.
        self.memcache_cas(mkey, pbs, time=timeout, namespace=ns)
      if use_cache:
        self._cache[key] = entity
    raise tasklets.Return(entity)

  @tasklets.tasklet
  def put(self, entity, **ctx_options):
    options = _make_ctx_options(ctx_options)
    # TODO: What if the same entity is being put twice?
    # TODO: What if two entities with the same key are being put?
    key = entity._key
    if key is None:
      # Pass a dummy Key to _use_datastore().
      key = model.Key(entity.__class__, None)
    use_datastore = self._use_datastore(key, options)

    if entity._has_complete_key():
      if self._use_memcache(key, options):
        # Wait for memcache operations before starting datastore RPCs.
        mkey = self._memcache_prefix + key.urlsafe()
        ns = key.namespace()
        if use_datastore:
          yield self.memcache_set(mkey, _LOCKED, time=_LOCK_TIME,
                                  namespace=ns, use_cache=True)
        else:
          pbs = entity._to_pb(set_key=False).SerializePartialToString()
          timeout = self._get_memcache_timeout(key, options)
          yield self.memcache_set(mkey, pbs, time=timeout, namespace=ns)

    if use_datastore:
      key = yield self._put_batcher.add(entity, options)
      if self._use_memcache(key, options):
        mkey = self._memcache_prefix + key.urlsafe()
        ns = key.namespace()
        yield self.memcache_delete(mkey, namespace=ns)

    if key is not None:
      if entity._key != key:
        logging.info('replacing key %s with %s', entity._key, key)
        entity._key = key
      # TODO: For updated entities, could we update the cache first?
      if self._use_cache(key, options):
        # TODO: What if by now the entity is already in the cache?
        self._cache[key] = entity

    raise tasklets.Return(key)

  @tasklets.tasklet
  def delete(self, key, **ctx_options):
    options = _make_ctx_options(ctx_options)
    if self._use_memcache(key, options):
      mkey = self._memcache_prefix + key.urlsafe()
      ns = key.namespace()
      yield self.memcache_set(mkey, _LOCKED, time=_LOCK_TIME, namespace=ns,
                              use_cache=True)

    if self._use_datastore(key, options):
      yield self._delete_batcher.add(key, options)

    if self._use_cache(key, options):
      self._cache[key] = None

  @tasklets.tasklet
  def allocate_ids(self, key, size=None, max=None, **ctx_options):
    options = _make_ctx_options(ctx_options)
    lo_hi = yield self._conn.async_allocate_ids(options, key, size, max)
    raise tasklets.Return(lo_hi)

  @datastore_rpc._positional(3)
  def map_query(self, query, callback, options=None, merge_future=None):
    mfut = merge_future
    if mfut is None:
      mfut = tasklets.MultiFuture('map_query')

    @tasklets.tasklet
    def helper():
      try:
        inq = tasklets.SerialQueueFuture()
        query.run_to_queue(inq, self._conn, options)
        is_ancestor_query = query.ancestor is not None
        while True:
          try:
            batch, i, ent = yield inq.getq()
          except EOFError:
            break
          if isinstance(ent, model.Key):
            pass  # It was a keys-only query and ent is really a Key.
          else:
            key = ent._key
            if key in self._cache:
              hit = self._cache[key]
              if hit is not None and hit.key != key:
                # The cached entry has been mutated to have a different key.
                # That's a false hit.  Get rid of it.
                # See issue #13.  http://goo.gl/jxjOP
                del self._cache[key]
            if key in self._cache:
              # Assume the cache is more up to date.
              if self._cache[key] is None:
                # This is a weird case.  Apparently this entity was
                # deleted concurrently with the query.  Let's just
                # pretend the delete happened first.
                logging.info('Conflict: entity %s was deleted', key)
                continue
              # Replace the entity the callback will see with the one
              # from the cache.
              if ent != self._cache[key]:
                logging.info('Conflict: entity %s was modified', key)
              ent = self._cache[key]
            else:
              # Cache the entity only if this is an ancestor query;
              # non-ancestor queries may return stale results, since in
              # the HRD these queries are "eventually consistent".
              # TODO: Shouldn't we check this before considering cache hits?
              if is_ancestor_query and self._use_cache(key, options):
                self._cache[key] = ent
          if callback is None:
            val = ent
          else:
            # TODO: If the callback raises, log and ignore.
            if options is not None and options.produce_cursors:
              val = callback(batch, i, ent)
            else:
              val = callback(ent)
          mfut.putq(val)
      except Exception, err:
        _, _, tb = sys.exc_info()
        mfut.set_exception(err, tb)
        raise
      else:
        mfut.complete()

    helper()
    return mfut

  @datastore_rpc._positional(2)
  def iter_query(self, query, callback=None, options=None):
    return self.map_query(query, callback=callback, options=options,
                          merge_future=tasklets.SerialQueueFuture())

  @tasklets.tasklet
  def transaction(self, callback, **ctx_options):
    # Will invoke callback() one or more times with the default
    # context set to a new, transactional Context.  Returns a Future.
    # Callback may be a tasklet.
    options = _make_ctx_options(ctx_options)
    app = ContextOptions.app(options) or key_module._DefaultAppId()
    # Note: zero retries means try it once.
    retries = ContextOptions.retries(options)
    if retries is None:
      retries = 3
    yield self.flush()
    for _ in xrange(1 + max(0, retries)):
      transaction = yield self._conn.async_begin_transaction(options, app)
      tconn = datastore_rpc.TransactionalConnection(
        adapter=self._conn.adapter,
        config=self._conn.config,
        transaction=transaction)
      old_ds_conn = datastore._GetConnection()
      tctx = self.__class__(conn=tconn,
                            auto_batcher_class=self._auto_batcher_class)
      try:
        # Copy memcache policies.  Note that get() will never use
        # memcache in a transaction, but put and delete should do their
        # memcache thing (which is to mark the key as deleted for
        # _LOCK_TIME seconds).  Also note that the in-process cache and
        # datastore policies keep their default (on) state.
        tctx.set_memcache_policy(self.get_memcache_policy())
        tctx.set_memcache_timeout_policy(self.get_memcache_timeout_policy())
        tasklets.set_context(tctx)
        datastore._SetConnection(tconn)  # For taskqueue coordination
        try:
          try:
            result = callback()
            if isinstance(result, tasklets.Future):
              result = yield result
          finally:
            yield tctx.flush()
        except Exception:
          t, e, tb = sys.exc_info()
          yield tconn.async_rollback(options)  # TODO: Don't block???
          if issubclass(t, datastore_errors.Rollback):
            return
          else:
            raise t, e, tb
        else:
          ok = yield tconn.async_commit(options)
          if ok:
            # TODO: This is questionable when self is transactional.
            self._cache.update(tctx._cache)
            yield self._clear_memcache(tctx._cache)
            raise tasklets.Return(result)
      finally:
        datastore._SetConnection(old_ds_conn)

    # Out of retries
    raise datastore_errors.TransactionFailedError(
      'The transaction could not be committed. Please try again.')

  def in_transaction(self):
    """Return whether a transaction is currently active."""
    return isinstance(self._conn, datastore_rpc.TransactionalConnection)

  def clear_cache(self):
    """Clears the in-memory cache.

    NOTE: This does not affect memcache.
    """
    self._cache.clear()
    self._get_queue.clear()

  @tasklets.tasklet
  def _clear_memcache(self, keys):
    # Note: This doesn't technically *clear* the keys; it locks them.
    keys = set(key for key in keys if self._use_memcache(key))
    futures = []
    for key in keys:
      mkey = self._memcache_prefix + key.urlsafe()
      ns = key.namespace()
      fut = self.memcache_set(mkey, _LOCKED, time=_LOCK_TIME, namespace=ns,
                              use_cache=True)
      futures.append(fut)
    yield futures

  @tasklets.tasklet
  def get_or_insert(*args, **kwds):
    # NOTE: The signature is really weird here because we want to support
    # models with properties named e.g. 'self' or 'name'.
    self, model_class, name = args  # These must always be positional.
    our_kwds = {}
    for kwd in 'app', 'namespace', 'parent', 'context_options':
      # For each of these keyword arguments, if there is a property
      # with the same name, the caller *must* use _foo=..., otherwise
      # they may use either _foo=... or foo=..., but _foo=... wins.
      alt_kwd = '_' + kwd
      if alt_kwd in kwds:
        our_kwds[kwd] = kwds.pop(alt_kwd)
      elif (kwd in kwds and
          not isinstance(getattr(model_class, kwd, None), model.Property)):
        our_kwds[kwd] = kwds.pop(kwd)
    app = our_kwds.get('app')
    namespace = our_kwds.get('namespace')
    parent = our_kwds.get('parent')
    context_options = our_kwds.get('context_options')
    # (End of super-special argument parsing.)
    # TODO: Test the heck out of this, in all sorts of evil scenarios.
    if not isinstance(name, basestring):
      raise TypeError('name must be a string; received %r' % name)
    elif not name:
      raise ValueError('name cannot be an empty string.')
    key = model.Key(model_class, name,
                    app=app, namespace=namespace, parent=parent)
    # TODO: Can (and should) the cache be trusted here?
    ent = yield self.get(key)
    if ent is None:
      @tasklets.tasklet
      def txn():
        ent = yield key.get_async(options=context_options)
        if ent is None:
          ent = model_class(**kwds)  # TODO: Check for forbidden keys
          ent._key = key
          yield ent.put_async(options=context_options)
        raise tasklets.Return(ent)
      ent = yield self.transaction(txn)
    raise tasklets.Return(ent)

  @tasklets.tasklet
  def _memcache_get_tasklet(self, todo, options):
    if not todo:
      raise RuntimeError('Nothing to do.')
    for_cas, namespace = options
    keys = set()
    for unused_fut, key in todo:
      keys.add(key)
    results = yield self._memcache.get_multi_async(keys, for_cas=for_cas,
                                                   namespace=namespace)
    for fut, key in todo:
      fut.set_result(results.get(key))

  @tasklets.tasklet
  def _memcache_set_tasklet(self, todo, options):
    if not todo:
      raise RuntimeError('Nothing to do.')
    opname, time, namespace = options
    methodname = opname + '_multi_async'
    method = getattr(self._memcache, methodname)
    mapping = {}
    for unused_fut, (key, value) in todo:
      mapping[key] = value
    results = yield method(mapping, time=time, namespace=namespace)
    for fut, (key, unused_value) in todo:
      if results is None:
        status = memcache.MemcacheSetResponse.ERROR
      else:
        status = results.get(key)
      fut.set_result(status == memcache.MemcacheSetResponse.STORED)

  @tasklets.tasklet
  def _memcache_del_tasklet(self, todo, options):
    if not todo:
      raise RuntimeError('Nothing to do.')
    seconds, namespace = options
    keys = set()
    for unused_fut, key in todo:
      keys.add(key)
    statuses = yield self._memcache.delete_multi_async(keys, seconds=seconds,
                                                       namespace=namespace)
    status_key_mapping = {}
    if statuses:  # On network error, statuses is None.
      for key, status in zip(keys, statuses):
        status_key_mapping[key] = status
    for fut, key in todo:
      status = status_key_mapping.get(key, memcache.DELETE_NETWORK_FAILURE)
      fut.set_result(status)

  @tasklets.tasklet
  def _memcache_off_tasklet(self, todo, options):
    if not todo:
      raise RuntimeError('Nothing to do.')
    initial_value, namespace = options
    mapping = {}  # {key: delta}
    for unused_fut, (key, delta) in todo:
      mapping[key] = delta
    results = yield self._memcache.offset_multi_async(mapping,
                               initial_value=initial_value, namespace=namespace)
    for fut, (key, unused_delta) in todo:
      result = results.get(key)
      if isinstance(result, basestring):
        # See http://code.google.com/p/googleappengine/issues/detail?id=2012
        # We can fix this without waiting for App Engine to fix it.
        result = int(result)
      fut.set_result(result)

  def memcache_get(self, key, for_cas=False, namespace=None, use_cache=False):
    """An auto-batching wrapper for memcache.get() or .get_multi().

    Args:
      key: Key to set.  This must be a string; no prefix is applied.
      for_cas: If True, request and store CAS ids on the Context.
      namespace: Optional namespace.

    Returns:
      A Future (!) whose return value is the value retrieved from
      memcache, or None.
    """
    if not isinstance(key, str):
      raise TypeError('key must be a string; received %r' % key)
    if not isinstance(for_cas, bool):
      raise ValueError('for_cas must be a bool; received %r' % for_cas)
    if namespace is None:
      namespace = namespace_manager.get_namespace()
    options = (for_cas, namespace)
    batcher = self._memcache_get_batcher
    if use_cache:
      return batcher.add_once(key, options)
    else:
      return batcher.add(key, options)

  # XXX: Docstrings below.

  def memcache_gets(self, key, namespace=None, use_cache=False):
    return self.memcache_get(key, for_cas=True, namespace=namespace,
                             use_cache=use_cache)

  def memcache_set(self, key, value, time=0, namespace=None, use_cache=False):
    if not isinstance(key, str):
      raise TypeError('key must be a string; received %r' % key)
    if not isinstance(time, (int, long)):
      raise ValueError('time must be a number; received %r' % time)
    if namespace is None:
      namespace = namespace_manager.get_namespace()
    options = ('set', time, namespace)
    batcher = self._memcache_set_batcher
    if use_cache:
      return batcher.add_once((key, value), options)
    else:
      return batcher.add((key, value), options)

  def memcache_add(self, key, value, time=0, namespace=None):
    if not isinstance(key, str):
      raise TypeError('key must be a string; received %r' % key)
    if not isinstance(time, (int, long)):
      raise ValueError('time must be a number; received %r' % time)
    if namespace is None:
      namespace = namespace_manager.get_namespace()
    return self._memcache_set_batcher.add((key, value),
                                          ('add', time, namespace))

  def memcache_replace(self, key, value, time=0, namespace=None):
    if not isinstance(key, str):
      raise TypeError('key must be a string; received %r' % key)
    if not isinstance(time, (int, long)):
      raise ValueError('time must be a number; received %r' % time)
    if namespace is None:
      namespace = namespace_manager.get_namespace()
    return self._memcache_set_batcher.add((key, value),
                                          ('replace', time, namespace))

  def memcache_cas(self, key, value, time=0, namespace=None):
    if not isinstance(key, str):
      raise TypeError('key must be a string; received %r' % key)
    if not isinstance(time, (int, long)):
      raise ValueError('time must be a number; received %r' % time)
    if namespace is None:
      namespace = namespace_manager.get_namespace()
    return self._memcache_set_batcher.add((key, value),
                                          ('cas', time, namespace))

  def memcache_delete(self, key, seconds=0, namespace=None):
    if not isinstance(key, str):
      raise TypeError('key must be a string; received %r' % key)
    if not isinstance(seconds, (int, long)):
      raise ValueError('seconds must be a number; received %r' % seconds)
    if namespace is None:
      namespace = namespace_manager.get_namespace()
    return self._memcache_del_batcher.add(key, (seconds, namespace))

  def memcache_incr(self, key, delta=1, initial_value=None, namespace=None):
    if not isinstance(key, str):
      raise TypeError('key must be a string; received %r' % key)
    if not isinstance(delta, (int, long)):
      raise ValueError('delta must be a number; received %r' % delta)
    if initial_value is not None and not isinstance(initial_value, (int, long)):
      raise ValueError('initial_value must be a number or None; received %r' %
                       initial_value)
    if namespace is None:
      namespace = namespace_manager.get_namespace()
    return self._memcache_off_batcher.add((key, delta),
                                          (initial_value, namespace))

  def memcache_decr(self, key, delta=1, initial_value=None, namespace=None):
    if not isinstance(key, str):
      raise TypeError('key must be a string; received %r' % key)
    if not isinstance(delta, (int, long)):
      raise ValueError('delta must be a number; received %r' % delta)
    if initial_value is not None and not isinstance(initial_value, (int, long)):
      raise ValueError('initial_value must be a number or None; received %r' %
                       initial_value)
    if namespace is None:
      namespace = namespace_manager.get_namespace()
    return self._memcache_off_batcher.add((key, -delta),
                                          (initial_value, namespace))


def toplevel(func):
  """A sync tasklet that sets a fresh default Context.

  Use this for toplevel view functions such as
  webapp.RequestHandler.get() or Django view functions.
  """
  @utils.wrapping(func)
  def add_context_wrapper(*args, **kwds):
    __ndb_debug__ = utils.func_info(func)
    tasklets._state.clear_all_pending()
    # Create and install a new context.
    ctx = tasklets.make_default_context()
    try:
      tasklets.set_context(ctx)
      return tasklets.synctasklet(func)(*args, **kwds)
    finally:
      tasklets.set_context(None)
      ctx.flush().check_success()
      eventloop.run()  # Ensure writes are flushed, etc.
  return add_context_wrapper
