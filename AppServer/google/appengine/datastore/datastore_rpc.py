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




"""Asynchronous datastore API.

This is designed to be the lowest-level API to be used by all Python
datastore client libraries.

A refactoring is in progress to rebuild datastore.py on top of this,
while remaining nearly 100% backwards compatible.  A new (not intended
to be compatible) library to replace db.py is also under development.
"""








__all__ = ['AbstractAdapter',
           'BaseConfiguration',
           'BaseConnection',
           'ConfigOption',
           'Configuration',
           'Connection',
           'IdentityAdapter',
           'MultiRpc',
           'TransactionalConnection',
           ]




import logging
import os


from google.appengine.datastore import entity_pb


from google.appengine.api import api_base_pb
from google.appengine.api import apiproxy_rpc
from google.appengine.api import apiproxy_stub_map

from google.appengine.api import datastore_errors
from google.appengine.api import datastore_types
from google.appengine.datastore import datastore_pb
from google.appengine.runtime import apiproxy_errors





_MAX_ID_BATCH_SIZE = 1000 * 1000 * 1000



def _positional(max_pos_args):
  """A decorator to declare that only the first N arguments may be positional.

  Note that for methods, n includes 'self'.
  """
  def positional_decorator(wrapped):
    def positional_wrapper(*args, **kwds):
      if len(args) > max_pos_args:
        plural_s = ''
        if max_pos_args != 1:
          plural_s = 's'
        raise TypeError(
          '%s() takes at most %d positional argument%s (%d given)' %
          (wrapped.__name__, max_pos_args, plural_s, len(args)))
      return wrapped(*args, **kwds)
    return positional_wrapper
  return positional_decorator


class AbstractAdapter(object):
  """Abstract interface between protobufs and user-level classes.

  This class defines conversions between the protobuf classes defined
  in entity_pb.py on the one hand, and the corresponding user-level
  classes (which are defined by higher-level API libraries such as
  datastore.py or db.py) on the other hand.

  The premise is that the code in this module is agnostic about the
  user-level classes used to represent keys and entities, while at the
  same time provinging APIs that accept or return such user-level
  classes.

  Higher-level libraries must subclass this abstract class and pass an
  instance of the subclass to the Connection they want to use.

  These methods may raise datastore_errors.Error for bad inputs.
  """

  def pb_to_key(self, pb):
    """Turn an entity_pb.Reference into a user-level key."""
    raise NotImplementedError

  def pb_to_entity(self, pb):
    """Turn an entity_pb.EntityProto into a user-level entity."""
    raise NotImplementedError

  def pb_to_query_result(self, pb, keys_only=False):
    """Turn an entity_pb.EntityProto into a user-level query result."""
    if keys_only:
      return self.pb_to_key(pb.key())
    else:
      return self.pb_to_entity(pb)

  def key_to_pb(self, key):
    """Turn a user-level key into an entity_pb.Reference."""
    raise NotImplementedError

  def entity_to_pb(self, entity):
    """Turn a user-level entity into an entity_pb.EntityProto."""
    raise NotImplementedError

  def new_key_pb(self):
    """Create a new, empty entity_pb.Reference."""
    return entity_pb.Reference()

  def new_entity_pb(self):
    """Create a new, empty entity_pb.EntityProto."""
    return entity_pb.EntityProto()


class IdentityAdapter(AbstractAdapter):
  """A concrete adapter that implements the identity mapping.

  This is used as the default when a Connection is created without
  specifying an adapter; that's primarily for testing.
  """

  def pb_to_key(self, pb):
    return pb

  def pb_to_entity(self, pb):
    return pb

  def key_to_pb(self, key):
    return key

  def entity_to_pb(self, entity):
    return entity


class ConfigOption(object):
  """A descriptor for a Configuration option.

  This class is used to create a configuration option on a class that inherits
  from BaseConfiguration. A validator function decorated with this class will
  be converted to a read-only descriptor and BaseConfiguration will implement
  constructor and merging logic for that configuration option. A validator
  function takes a single non-None value to validate and either throws
  an exception or returns that value (or an equivalent value). A validator is
  called once at construction time, but only if a non-None value for the
  configuration option is specified the constructor's keyword arguments.
  """

  def __init__(self, validator):
    self.validator = validator

  def __get__(self, obj, objtype):
    if obj is None:
      return self
    return obj._values.get(self.validator.__name__, None)

  def __set__(self, obj, value):
    raise AttributeError('Configuration options are immutable (%s)' %
                         (self.validator.__name__,))

  def __call__(self, *args):
    """Gets the first non-None value for this option from the given args.

    Args:
      *arg: Any number of configuration objects or None values.

    Returns:
      The first value for this ConfigOption found in the given configuration
    objects or None.

    Raises:
      datastore_errors.BadArgumentError if a given in object is not a
    configuration object.
    """
    for config in args:
      if isinstance(config, self._cls):
        if self.validator.__name__ in config._values:
          return config._values[self.validator.__name__]
      elif config is not None and not isinstance(config, BaseConfiguration):
        raise datastore_errors.BadArgumentError(
            'invalid config argument (%r)' % (config,))
    return None


class _ConfigurationMetaClass(type):
  """The metaclass for all Configuration types.

  This class is needed to store a class specific list of all ConfigOptions in
  cls._options, and insert a __slots__ variable into the class dict before the
  class is created to impose immutability.
  """

  def __new__(metaclass, classname, bases, classDict):
    classDict['__slots__'] = ['_values']
    cls = type.__new__(metaclass, classname, bases, classDict)
    if object not in bases:
      cls._options = cls._options.copy()
      for option, value in cls.__dict__.iteritems():
        if isinstance(value, ConfigOption):
          if cls._options.has_key(option):
            raise TypeError('%s cannot be overridden (%s)' %
                            (option, cls.__name__))
          cls._options[option] = value
          value._cls = cls
    return cls


class BaseConfiguration(object):
  """A base class for a configuration object.

  Subclasses should provide validation functions for every configuration option
  they accept. Any public function decorated with ConfigOption is assumed to be
  a validation function for an option of the same name. All validation functions
  take a single non-None value to validate and must throw an exception or return
  the value to store.

  This class forces subclasses to be immutable and exposes a read-only
  property for every accepted configuration option. Configuration options set by
  passing keyword arguments to the constructor. The constructor and merge
  function are designed to avoid creating redundant copies and may return
  the configuration objects passed to them if appropriate.

  Setting an option to None is the same as not specifying the option except in
  the case where the 'config' argument is given. In this case the value on
  'config' of the same name is ignored. Options that are not specified will
  return 'None' when accessed.
  """

  __metaclass__ = _ConfigurationMetaClass
  _options = {}

  def __new__(cls, config=None, **kwargs):
    """Immutable constructor.

    If 'config' is non-None all configuration options will default to the value
    it contains unless the configuration option is explicitly set to 'None' in
    the keyword arguments. If 'config' is None then all configuration options
    default to None.

    Args:
      config: Optional base configuration providing default values for
        parameters not specified in the keyword arguments.
      **kwargs: Configuration options to store on this object.

    Returns:
      Either a new Configuration object or (if it would be equivalent)
      the config argument unchanged, but never None.
    """
    if config is None:
      pass
    elif isinstance(config, BaseConfiguration):
      if cls is config.__class__ and config.__is_stronger(**kwargs):

        return config

      for key, value in config._values.iteritems():
        kwargs.setdefault(key, value)
    else:
      raise datastore_errors.BadArgumentError(
        'config argument should be Configuration (%r)' % (config,))

    obj = super(BaseConfiguration, cls).__new__(cls)
    obj._values = {}
    for key, value in kwargs.iteritems():
      if value is not None:
        try:
          config_option = obj._options[key]
        except KeyError, err:
          raise TypeError('Unknown configuration option (%s)' % err)
        obj._values[key] = config_option.validator(value)
    return obj

  def __eq__(self, other):
    if self is other:
      return True

    if (not isinstance(other, self.__class__) and
        not isinstance(self, other.__class__)):
      return NotImplemented
    return self._values == other._values

  def __ne__(self, other):
    equal = self.__eq__(other)
    if equal is NotImplemented:
      return equal
    return not equal

  def __is_stronger(self, **kwargs):
    """Internal helper to ask whether a configuration is stronger than another.

    A configuration is stronger when every value it contains is equal to or
    missing from the values in the kwargs.

    Example: a configuration with:
      (deadline=5, on_configuration=None, read_policy=EVENTUAL_CONSISTENCY)
    is stronger than:
      (deadline=5, on_configuration=None)
    but not stronger than:
      (deadline=5, on_configuration=None, read_policy=None)
    or
      (deadline=10, on_configuration=None, read_policy=None).

    More formally:
      - Any value is stronger than an unset value;
      - Any value is stronger than itself.

    Returns:
      True if each of the self attributes is stronger than the
    corresponding argument.
    """
    for key, value in kwargs.iteritems():
      if key not in self._values or value != self._values[key]:
        return False
    return True

  def merge(self, config):
    """Merge two configurations.

    The configuration given as an argument (if any) takes priority;
    defaults are filled in from the current configuration.

    Args:
      config: Configuration providing overrides, or None (but cannot
        be omitted).

    Returns:
      Either a new Configuration object or (if it would be equivalent)
      self or the config argument unchanged, but never None.
    """
    if config is None or config is self:

      return self



    if isinstance(config, self.__class__):
      for key in self._values:
        if key not in config._values:
          break
      else:
        return config

    if self.__is_stronger(**config._values):
      return self


    obj = type(self)()
    obj._values = self._values.copy()
    obj._values.update(config._values)
    return obj


class Configuration(BaseConfiguration):
  """Configuration parameters for datastore RPCs.

  This class reserves the right to define configuration options of any name
  except those that start with 'user_'. External subclasses should only define
  function or variables with names that start with in 'user_'.

  The options defined on this class include generic RPC parameters (deadline)
  but also datastore-specific parameters (on_completion and read_policy).

  Options are set by passing keyword arguments to the constructor corresponding
  to the configuration options defined below.
  """


  STRONG_CONSISTENCY = 0
  """A read consistency that will return up to date results."""

  EVENTUAL_CONSISTENCY = 1
  """A read consistency that allows requests to return possibly stale results.

  This read_policy tends to be faster and less prone to unavailability/timeouts.
  May return transactionally inconsistent results in rare cases.
  """

  APPLY_ALL_JOBS_CONSISTENCY = 2
  """A read consistency that aggressively tries to find write jobs to apply.

  Use of this read policy is strongly discouraged.

  This read_policy tends to be more costly and is only useful in a few specific
  cases. It is equivalent to splitting a request by entity group and wrapping
  each batch in a separate transaction. Cannot be used with non-ancestor
  queries.
  """


  ALL_READ_POLICIES = frozenset((STRONG_CONSISTENCY,
                                 EVENTUAL_CONSISTENCY,
                                 APPLY_ALL_JOBS_CONSISTENCY,
                                 ))



  @ConfigOption
  def deadline(value):
    """The deadline for any RPC issued.

    If unset the system default will be used which is typically 5 seconds.

    Raises:
      BadArgumentError if value is not a number or is less than zero.
    """
    if not isinstance(value, (int, long, float)):
      raise datastore_errors.BadArgumentError(
        'deadline argument should be int/long/float (%r)' % (value,))
    if value <= 0:
      raise datastore_errors.BadArgumentError(
        'deadline argument should be > 0 (%r)' % (value,))
    return value

  @ConfigOption
  def on_completion(value):
    """A callback that is invoked when any RPC completes.

    If specified, it will be called with a UserRPC object as argument when an
    RPC completes.

    NOTE: There is a subtle but important difference between
    UserRPC.callback and Configuration.on_completion: on_completion is
    called with the RPC object as its first argument, where callback is
    called without arguments.  (Because a Configuration's on_completion
    function can be used with many UserRPC objects, it would be awkward
    if it was called without passing the specific RPC.)
    """


    return value

  @ConfigOption
  def read_policy(value):
    """The read policy to use for any relevent RPC.

    if unset STRONG_CONSISTENCY will be used.

    Raises:
      BadArgumentError if value is not a known read policy.
    """
    if value not in Configuration.ALL_READ_POLICIES:
      raise datastore_errors.BadArgumentError(
        'read_policy argument invalid (%r)' % (value,))
    return value

  @ConfigOption
  def force_writes(value):
    """If a write request should succeed even if the app is read-only.

    This only applies to user controlled read-only periods.
    """
    if not isinstance(value, bool):
      raise datastore_errors.BadArgumentError(
        'force_writes argument invalid (%r)' % (value,))
    return value


  @ConfigOption
  def max_rpc_bytes(value):
    """The maximum serialized size of a Get/Put/Delete without batching."""
    if not (isinstance(value, (int, long)) and value > 0):
      raise datastore_errors.BadArgumentError(
        'max_rpc_bytes should be a positive integer')
    return value

  @ConfigOption
  def max_get_keys(value):
    """The maximum number of keys in a Get without batching."""
    if not (isinstance(value, (int, long)) and value > 0):
      raise datastore_errors.BadArgumentError(
        'max_get_keys should be a positive integer')
    return value

  @ConfigOption
  def max_put_entities(value):
    """The maximum number of entities in a Put without batching."""
    if not (isinstance(value, (int, long)) and value > 0):
      raise datastore_errors.BadArgumentError(
        'max_put_entities should be a positive integer')
    return value

  @ConfigOption
  def max_delete_keys(value):
    """The maximum number of keys in a Delete without batching."""
    if not (isinstance(value, (int, long)) and value > 0):
      raise datastore_errors.BadArgumentError(
        'max_delete_keys should be a positive integer')
    return value

class MultiRpc(object):
  """A wrapper around multiple UserRPC objects.

  This provides an API similar to that of UserRPC, but wraps multiple
  RPCs such that e.g. .wait() blocks until all wrapped RPCs are
  complete, and .get_result() returns the combined results from all
  wrapped RPCs.

  Class methods:
    flatten(rpcs): Expand a list of UserRPCs and MultiRpcs
      into a list of UserRPCs.
    wait_any(rpcs): Call UserRPC.wait_any(flatten(rpcs)).
    wait_all(rpcs): Call UserRPC.wait_all(flatten(rpcs)).

  Instance methods:
    wait(): Wait for all RPCs.
    check_success(): Wait and then check success for all RPCs.
    get_result(): Wait for all, check successes, then merge
      all results.

  Instance attributes:
    rpcs: The list of wrapped RPCs (returns a copy).
    state: The combined state of all RPCs.
  """

  def __init__(self, rpcs, extra_hook=None):
    """Constructor.

    Args:
      rpcs: A list of UserRPC and MultiRpc objects; it is flattened
        before being stored.
      extra_hook: Optional function to be applied to the final result
        or list of results.
    """
    self.__rpcs = self.flatten(rpcs)
    self.__extra_hook = extra_hook

  @property
  def rpcs(self):
    """Get a flattened list containing the RPCs wrapped.

    This returns a copy to prevent users from modifying the state.
    """
    return list(self.__rpcs)

  @property
  def state(self):
    """Get the combined state of the wrapped RPCs.

    This mimics the UserRPC.state property.  If all wrapped RPCs have
    the same state, that state is returned; otherwise, RUNNING is
    returned (which here really means 'neither fish nor flesh').
    """
    lo = apiproxy_rpc.RPC.FINISHING
    hi = apiproxy_rpc.RPC.IDLE
    for rpc in self.__rpcs:
      lo = min(lo, rpc.state)
      hi = max(hi, rpc.state)
    if lo == hi:
      return lo
    return apiproxy_rpc.RPC.RUNNING

  def wait(self):
    """Wait for all wrapped RPCs to finish.

    This mimics the UserRPC.wait() method.
    """
    apiproxy_stub_map.UserRPC.wait_all(self.__rpcs)

  def check_success(self):
    """Check success of all wrapped RPCs, failing if any of the failed.

    This mimics the UserRPC.check_success() method.

    NOTE: This first waits for all wrapped RPCs to finish before
    checking the success of any of them.  This makes debugging easier.
    """
    self.wait()
    for rpc in self.__rpcs:
      rpc.check_success()

  def get_result(self):
    """Return the combined results of all wrapped RPCs.

    This mimics the UserRPC.get_results() method.  Multiple results
    are combined using the following rules:

    1. If there are no wrapped RPCs, an empty list is returned.

    2. If exactly one RPC is wrapped, its result is returned.

    3. If more than one RPC is wrapped, the result is always a list,
       which is constructed from the wrapped results as follows:

       a. A wrapped result equal to None is ignored;

       b. A wrapped result that is a list (but not any other type of
          sequence!) has its elements added to the result list.

       c. Any other wrapped result is appended to the result list.

    After all results are combined, if __extra_hook is set, it is
    called with the combined results and its return value becomes the
    final result.

    NOTE: This first waits for all wrapped RPCs to finish, and then
    checks all their success.  This makes debugging easier.
    """

    self.check_success()

    if len(self.__rpcs) == 1:
      results = self.__rpcs[0].get_result()
    else:
      results = []


      for rpc in self.__rpcs:
        result = rpc.get_result()
        if isinstance(result, list):
          results.extend(result)
        elif result is not None:
          results.append(result)
    if self.__extra_hook is not None:
      results = self.__extra_hook(results)
    return results

  @classmethod
  def flatten(cls, rpcs):
    """Return a list of UserRPCs, expanding MultiRpcs in the argument list.

    For example: given 4 UserRPCs rpc1 through rpc4,
    flatten(rpc1, MultiRpc([rpc2, rpc3], rpc4)
    returns [rpc1, rpc2, rpc3, rpc4].

    Args:
      rpcs: A list of UserRPC and MultiRpc objects.

    Returns:
      A list of UserRPC objects.
    """
    flat = []
    for rpc in rpcs:
      if isinstance(rpc, MultiRpc):



        flat.extend(rpc.__rpcs)
      else:
        if not isinstance(rpc, apiproxy_stub_map.UserRPC):
          raise datastore_errors.BadArgumentError(
            'Expected a list of UserRPC object (%r)' % (rpc,))
        flat.append(rpc)
    return flat

  @classmethod
  def wait_any(cls, rpcs):
    """Wait until one of the RPCs passed in is finished.

    This mimics UserRPC.wait_any().

    Args:
      rpcs: A list of UserRPC and MultiRpc objects.

    Returns:
      A UserRPC object or None.
    """
    return apiproxy_stub_map.UserRPC.wait_any(cls.flatten(rpcs))

  @classmethod
  def wait_all(cls, rpcs):
    """Wait until all RPCs passed in are finished.

    This mimics UserRPC.wait_all().

    Args:
      rpcs: A list of UserRPC and MultiRpc objects.
    """
    apiproxy_stub_map.UserRPC.wait_all(cls.flatten(rpcs))


class BaseConnection(object):
  """Datastore connection base class.

  NOTE: Do not instantiate this class; use Connection or
  TransactionalConnection instead.

  This is not a traditional database connection -- with App Engine, in
  the end the connection is always implicit in the process state.
  There is also no intent to be compatible with PEP 249 (Python's
  Database-API).  But it is a useful abstraction to have an explicit
  object that manages the database interaction, and especially
  transactions.  Other settings related to the App Engine datastore
  are also stored here (e.g. the RPC timeout).

  A similar class in the Java API to the App Engine datastore is
  DatastoreServiceConfig (but in Java, transaction state is always
  held by the current thread).

  To use transactions, call connection.new_transaction().  This
  returns a new connection (an instance of the TransactionalConnection
  subclass) which you should use for all operations in the
  transaction.

  This model supports multiple unrelated concurrent transactions (but
  not nested transactions as this concept is commonly understood in
  the relational database world).

  When the transaction is done, call .commit() or .rollback() on the
  transactional connection.  If .commit() returns False, the
  transaction failed and none of your operations made it to the
  datastore; if it returns True, all your operations were committed.
  The transactional connection cannot be used once .commit() or
  .rollback() is called.

  Transactions are created lazily.  The first operation that requires
  a transaction handle will issue the low-level BeginTransaction
  request and wait for it to return.

  Transactions keep track of the entity group.  All operations within
  a transaction must use the same entity group.  An entity group
  (currently) comprises an app id, a namespace, and a top-level key (a
  kind and an id or name).  The first operation performed determines
  the entity group.  There is some special-casing when the first
  operation is a put() of an entity with an incomplete key; in this case
  the entity group is determined after the operation returns.

  NOTE: the datastore stubs in the dev_appserver currently support
  only a single concurrent transaction.  Specifically, the (old) file
  stub locks up if an attempt is made to start a new transaction while
  a transaction is already in use, whereas the sqlite stub fails an
  assertion.
  """

  UNKNOWN_DATASTORE = 0
  MASTER_SLAVE_DATASTORE = 1

  HIGH_REPLICATION_DATASTORE = 2

  @_positional(1)
  def __init__(self, adapter=None, config=None):
    """Constructor.

    All arguments should be specified as keyword arguments.

    Args:
      adapter: Optional AbstractAdapter subclass instance;
        default IdentityAdapter.
      config: Optional Configuration object.
    """
    if adapter is None:
      adapter = IdentityAdapter()
    if not isinstance(adapter, AbstractAdapter):
      raise datastore_errors.BadArgumentError(
        'invalid adapter argument (%r)' % (adapter,))
    self.__adapter = adapter

    if config is None:
      config = Configuration()
    elif not isinstance(config, Configuration):
      raise datastore_errors.BadArgumentError(
        'invalid config argument (%r)' % (config,))
    self.__config = config

    self.__pending_rpcs = set()



  @property
  def adapter(self):
    """The adapter used by this connection."""
    return self.__adapter

  @property
  def config(self):
    """The default configuration used by this connection."""
    return self.__config




  def _add_pending(self, rpc):
    """Add an RPC object to the list of pending RPCs.

    The argument must be a UserRPC object, not a MultiRpc object.
    """
    assert not isinstance(rpc, MultiRpc)
    self.__pending_rpcs.add(rpc)

  def _remove_pending(self, rpc):
    """Remove an RPC object from the list of pending RPCs.

    If the argument is a MultiRpc object, the wrapped RPCs are removed
    from the list of pending RPCs.
    """
    if isinstance(rpc, MultiRpc):


      for wrapped_rpc in rpc._MultiRpc__rpcs:
        self._remove_pending(wrapped_rpc)
    else:
      try:
        self.__pending_rpcs.remove(rpc)
      except KeyError:


        pass

  def is_pending(self, rpc):
    """Check whether an RPC object is currently pending.

    Note that 'pending' in this context refers to an RPC associated
    with this connection for which _remove_pending() hasn't been
    called yet; normally this is called by check_rpc_success() which
    itself is called by the various result hooks.  A pending RPC may
    be in the RUNNING or FINISHING state.

    If the argument is a MultiRpc object, this returns true if at least
    one of its wrapped RPCs is pending.
    """
    if isinstance(rpc, MultiRpc):
      for wrapped_rpc in rpc._MultiRpc__rpcs:
        if self.is_pending(wrapped_rpc):
          return True
      return False
    else:
      return rpc in self.__pending_rpcs

  def get_pending_rpcs(self):
    """Return (a copy of) the list of currently pending RPCs."""
    return set(self.__pending_rpcs)

  def get_datastore_type(self, app=None):
    """Tries to get the datastore type for the given app.

    This function is only guaranteed to return something other than
    UNKNOWN_DATASTORE when running in production and querying the current app.
    """





    current_app = datastore_types.ResolveAppId(None)
    if app not in (current_app, None):
      return BaseConnection.UNKNOWN_DATASTORE
    if current_app.startswith('s~'):
      return BaseConnection.HIGH_REPLICATION_DATASTORE
    return BaseConnection.MASTER_SLAVE_DATASTORE

  def wait_for_all_pending_rpcs(self):
    """Wait for all currently pending RPCs to complete."""
    while self.__pending_rpcs:
      try:
        rpc = apiproxy_stub_map.UserRPC.wait_any(self.__pending_rpcs)
      except Exception:




        logging.info('wait_for_all_pending_rpcs(): exception in wait_any()',
                     exc_info=True)
        continue
      if rpc is None:
        logging.debug('wait_any() returned None')
        continue
      assert rpc.state == apiproxy_rpc.RPC.FINISHING
      if rpc in self.__pending_rpcs:






        try:
          self.check_rpc_success(rpc)
        except Exception:

          logging.info('wait_for_all_pending_rpcs(): '
                       'exception in check_rpc_success()',
                       exc_info=True)




  def _check_entity_group(self, key_pbs):
    pass

  def _update_entity_group(self, key_pbs):
    pass

  def _get_transaction(self, request=None):
    return None

  def create_rpc(self, config=None):
    """Create an RPC object using the configuration parameters.

    Args:
      config: Optional Configuration object.

    Returns:
      A new UserRPC object with the designated settings.

    NOTES:

    (1) The RPC object returned can only be used to make a single call
        (for details see apiproxy_stub_map.UserRPC).

    (2) To make a call, use one of the specific methods on the
        Connection object, such as conn.put(entities).  This sends the
        call to the server but does not wait.  To wait for the call to
        finish and get the result, call rpc.get_result().
    """
    deadline = Configuration.deadline(config, self.__config)
    on_completion = Configuration.on_completion(config, self.__config)
    callback = None
    if on_completion is not None:


      def callback():
        return on_completion(rpc)
    rpc = apiproxy_stub_map.UserRPC('datastore_v3', deadline, callback)
    return rpc

  def _set_request_read_policy(self, request, config=None):
    """Set the read policy on a request.

    This takes the read policy from the config argument or the
    configuration's default configuration, and if it is
    EVENTUAL_CONSISTENCY, sets the failover_ms field in the protobuf.

    Args:
      request: A protobuf with a failover_ms field.
      config: Optional Configuration object.
    """
    if not (hasattr(request, 'set_failover_ms') and hasattr(request, 'strong')):
      raise datastore_errors.BadRequestError(
          'read_policy is only supported on read operations.')

    if isinstance(config, apiproxy_stub_map.UserRPC):
      read_policy = getattr(config, 'read_policy', None)
    else:
      read_policy = Configuration.read_policy(config)


    if read_policy is None:
      read_policy = self.__config.read_policy

    if read_policy == Configuration.APPLY_ALL_JOBS_CONSISTENCY:
      request.set_strong(True)
    elif read_policy == Configuration.EVENTUAL_CONSISTENCY:
      request.set_strong(False)



      request.set_failover_ms(-1)

  def _set_request_transaction(self, request):
    """Set the current transaction on a request.

    NOTE: This version of the method does nothing.  The version
    overridden by TransactionalConnection is the real thing.

    Args:
      request: A protobuf with a transaction field.

    Returns:
      A datastore_pb.Transaction object or None.
    """
    return None

  def make_rpc_call(self, config, method, request, response,
                get_result_hook=None, user_data=None):
    """Make an RPC call.

    Except for the added config argument, this is a thin wrapper
    around UserRPC.make_call().

    Args:
      config: A Configuration object or None.  Defaults are taken from
        the connection's default configuration.
      method: The method name.
      request: The request protocol buffer.
      response: The response protocol buffer.
      get_result_hook: Optional get-result hook function.  If not None,
        this must be a function with exactly one argument, the RPC
        object (self).  Its return value is returned from get_result().
      user_data: Optional additional arbitrary data for the get-result
        hook function.  This can be accessed as rpc.user_data.  The
        type of this value is up to the service module.

    Returns:
      The UserRPC object used for the call.
    """


    if isinstance(config, apiproxy_stub_map.UserRPC):
      rpc = config
    else:
      rpc = self.create_rpc(config)
    rpc.make_call(method, request, response, get_result_hook, user_data)
    self._add_pending(rpc)
    return rpc

  def check_rpc_success(self, rpc):
    """Check for RPC success and translate exceptions.

    This wraps rpc.check_success() and should be called instead of that.

    This also removes the RPC from the list of pending RPCs, once it
    has completed.

    Args:
      rpc: A UserRPC or MultiRpc object.

    Raises:
      Nothing if the call succeeded; various datastore_errors.Error
      subclasses if ApplicationError was raised by rpc.check_success().
    """
    try:
      rpc.wait()
    finally:


      self._remove_pending(rpc)
    try:
      rpc.check_success()
    except apiproxy_errors.ApplicationError, err:
      raise _ToDatastoreError(err)





  MAX_RPC_BYTES = 1024 * 1024
  MAX_GET_KEYS = 1000
  MAX_PUT_ENTITIES = 500
  MAX_DELETE_KEYS = 500




  def __generate_pb_lists(self, values, value_to_pb, base_size, max_count,
                          config):
    """Internal helper: repeatedly yield a list of protobufs to fit a batch."""
    max_size = (Configuration.max_rpc_bytes(config, self.__config) or
                self.MAX_RPC_BYTES)
    pbs = []
    size = base_size
    for value in values:
      pb = value_to_pb(value)

      incr_size = pb.lengthString(pb.ByteSize()) + 1




      if (not isinstance(config, apiproxy_stub_map.UserRPC) and
          (len(pbs) >= max_count or (pbs and size + incr_size > max_size))):
        yield pbs
        pbs = []
        size = base_size
      pbs.append(pb)
      size += incr_size
    yield pbs

  def _get_base_size(self, base_req):
    """Internal helper: return request size in bytes."""
    return base_req.ByteSize()

  def get(self, keys):
    """Synchronous Get operation.

    Args:
      keys: An iterable of user-level key objects.

    Returns:
      A list of user-level entity objects and None values, corresponding
      1:1 to the argument keys.  A None means there is no entity for the
      corresponding key.
    """
    return self.async_get(None, keys).get_result()

  def async_get(self, config, keys, extra_hook=None):
    """Asynchronous Get operation.

    Args:
      config: A Configuration object or None.  Defaults are taken from
        the connection's default configuration.
      keys: An iterable of user-level key objects.
      extra_hook: Optional function to be called on the result once the
        RPC has completed.

    Returns:
      A MultiRpc object.
    """

    def make_get_call(req, pbs, user_data=None):
      req.key_list().extend(pbs)
      self._check_entity_group(req.key_list())
      self._set_request_transaction(req)
      resp = datastore_pb.GetResponse()
      return self.make_rpc_call(config, 'Get', req, resp,
                                self.__get_hook, user_data)

    base_req = datastore_pb.GetRequest()
    self._set_request_read_policy(base_req, config)


    if isinstance(config, apiproxy_stub_map.UserRPC):
      pbs = [self.__adapter.key_to_pb(key) for key in keys]
      return make_get_call(base_req, pbs, extra_hook)

    base_size = self._get_base_size(base_req)
    max_count = (Configuration.max_get_keys(config, self.__config) or
                 self.MAX_GET_KEYS)


    pbsgen = self.__generate_pb_lists(keys, self.__adapter.key_to_pb,
                                      base_size, max_count, config)
    rpcs = []
    for pbs in pbsgen:
      req = datastore_pb.GetRequest()
      req.CopyFrom(base_req)
      rpcs.append(make_get_call(req, pbs))
    return MultiRpc(rpcs, extra_hook)

  def __get_hook(self, rpc):
    """Internal method used as get_result_hook for Get operation."""
    self.check_rpc_success(rpc)
    entities = []
    for group in rpc.response.entity_list():
      if group.has_entity():
        entity = self.__adapter.pb_to_entity(group.entity())
      else:
        entity = None
      entities.append(entity)
    if rpc.user_data is not None:
      entities = rpc.user_data(entities)
    return entities

  def put(self, entities):
    """Synchronous Put operation.

    Args:
      entities: An iterable of user-level entity objects.

    Returns:
      A list of user-level key objects, corresponding 1:1 to the
      argument entities.

    NOTE: If any of the entities has an incomplete key, this will
    *not* patch up those entities with the complete key.
    """
    return self.async_put(None, entities).get_result()

  def async_put(self, config, entities, extra_hook=None):
    """Asynchronous Put operation.

    Args:
      config: A Configuration object or None.  Defaults are taken from
        the connection's default configuration.
      entities: An iterable of user-level entity objects.
      extra_hook: Optional function to be called on the result once the
        RPC has completed.

     Returns:
      A MultiRpc object.

    NOTE: If any of the entities has an incomplete key, this will
    *not* patch up those entities with the complete key.
    """

    def make_put_call(req, pbs, user_data=None):
      req.entity_list().extend(pbs)
      self._check_entity_group(e.key() for e in req.entity_list())
      self._set_request_transaction(req)
      resp = datastore_pb.PutResponse()
      return self.make_rpc_call(config, 'Put', req, resp,
                                self.__put_hook, user_data)


    base_req = datastore_pb.PutRequest()


    if isinstance(config, apiproxy_stub_map.UserRPC):
      if self.__config.force_writes:
        base_req.set_force(True)
      pbs = [self.__adapter.entity_to_pb(entity) for entity in entities]
      return make_put_call(base_req, pbs, extra_hook)

    if Configuration.force_writes(config, self.__config):
      base_req.set_force(True)
    base_size = self._get_base_size(base_req)
    max_count = (Configuration.max_put_entities(config, self.__config) or
                 self.MAX_PUT_ENTITIES)
    pbsgen = self.__generate_pb_lists(entities, self.__adapter.entity_to_pb,
                                      base_size, max_count, config)
    rpcs = []
    for pbs in pbsgen:
      req = datastore_pb.PutRequest()
      req.CopyFrom(base_req)
      rpcs.append(make_put_call(req, pbs))
    return MultiRpc(rpcs, extra_hook)

  def __put_hook(self, rpc):
    """Internal method used as get_result_hook for Put operation."""
    self.check_rpc_success(rpc)
    self._update_entity_group(rpc.response.key_list())
    keys = [self.__adapter.pb_to_key(pb)
            for pb in rpc.response.key_list()]


    if rpc.user_data is not None:
      keys = rpc.user_data(keys)
    return keys

  def delete(self, keys):
    """Synchronous Delete operation.

    Args:
      keys: An iterable of user-level key objects.

    Returns:
      None.
    """
    return self.async_delete(None, keys).get_result()

  def async_delete(self, config, keys, extra_hook=None):
    """Asynchronous Delete operation.

    Args:
      config: A Configuration object or None.  Defaults are taken from
        the connection's default configuration.
      keys: An iterable of user-level key objects.
      extra_hook: Optional function to be called once the RPC has completed.

    Returns:
      A MultiRpc object.
    """

    def make_delete_call(req, pbs, user_data=None):
      req.key_list().extend(pbs)
      self._check_entity_group(req.key_list())
      self._set_request_transaction(req)
      resp = datastore_pb.DeleteResponse()
      return self.make_rpc_call(config, 'Delete', req, resp,
                                self.__delete_hook, user_data)


    base_req = datastore_pb.DeleteRequest()


    if isinstance(config, apiproxy_stub_map.UserRPC):
      if self.__config.force_writes:
        base_req.set_force(True)
      pbs = [self.__adapter.key_to_pb(key) for key in keys]
      return make_delete_call(base_req, pbs, extra_hook)

    if Configuration.force_writes(config, self.__config):
      base_req.set_force(True)
    base_size = self._get_base_size(base_req)
    max_count = (Configuration.max_delete_keys(config, self.__config) or
                 self.MAX_DELETE_KEYS)
    pbsgen = self.__generate_pb_lists(keys, self.__adapter.key_to_pb,
                                      base_size, max_count, config)
    rpcs = []
    for pbs in pbsgen:
      req = datastore_pb.DeleteRequest()
      req.CopyFrom(base_req)
      rpcs.append(make_delete_call(req, pbs))
    return MultiRpc(rpcs, extra_hook)

  def __delete_hook(self, rpc):
    """Internal method used as get_result_hook for Delete operation."""
    self.check_rpc_success(rpc)
    if rpc.user_data is not None:

      rpc.user_data(None)



  def begin_transaction(self, app):
    """Syncnronous BeginTransaction operation.

    NOTE: In most cases the new_transaction() method is preferred,
    since that returns a TransactionalConnection object which will
    begin the transaction lazily.

    Args:
      app: Application ID.

    Returns:
      A datastore_pb.Transaction object.
    """
    return self.async_begin_transaction(None, app).get_result()

  def async_begin_transaction(self, config, app):
    """Asynchronous BeginTransaction operation.

    Args:
      config: A Configuration object or None.  Defaults are taken from
        the connection's default configuration.
      app: Application ID.

    Returns:
      A MultiRpc object.
    """
    if not isinstance(app, basestring) or not app:
      raise datastore_errors.BadArgumentError(
        'begin_transaction requires an application id argument (%r)' %
        (app,))
    req = datastore_pb.BeginTransactionRequest()
    req.set_app(app)
    resp = datastore_pb.Transaction()
    rpc = self.make_rpc_call(config, 'BeginTransaction', req, resp,
                             self.__begin_transaction_hook)
    return rpc

  def __begin_transaction_hook(self, rpc):
    """Internal method used as get_result_hook for BeginTransaction."""
    self.check_rpc_success(rpc)
    return rpc.response


class Connection(BaseConnection):
  """Transaction-less connection class.

  This contains those operations that are not allowed on transactional
  connections.  (Currently only allocate_ids.)
  """

  @_positional(1)
  def __init__(self, adapter=None, config=None):
    """Constructor.

    All arguments should be specified as keyword arguments.

    Args:
      adapter: Optional AbstractAdapter subclass instance;
        default IdentityAdapter.
      config: Optional Configuration object.
    """
    super(Connection, self).__init__(adapter=adapter, config=config)
    self.__adapter = self.adapter
    self.__config = self.config



  def new_transaction(self):
    """Create a new transactional connection based on this one.

    This is different from, and usually preferred over, the
    begin_transaction() method; new_transaction() returns a new
    TransactionalConnection object which will begin the transaction
    lazily.  This is necessary because the low-level
    begin_transaction() method needs the app id which will be gleaned
    from the transaction's entity group, which in turn is gleaned from
    the first key used in the transaction.
    """

    return TransactionalConnection(adapter=self.__adapter,
                                   config=self.__config)



  def allocate_ids(self, key, size=None, max=None):
    """Synchronous AllocateIds operation.

    Exactly one of size and max must be specified.

    Args:
      key: A user-level key object.
      size: Optional number of IDs to allocate.
      max: Optional maximum ID to allocate.

    Returns:
      A pair (start, end) giving the (inclusive) range of IDs allocation.
    """
    return self.async_allocate_ids(None, key, size, max).get_result()

  def async_allocate_ids(self, config, key, size=None, max=None,
                         extra_hook=None):
    """Asynchronous Get operation.

    Args:
      config: A Configuration object or None.  Defaults are taken from
        the connection's default configuration.
      key: A user-level key object.
      size: Optional number of IDs to allocate.
      max: Optional maximum ID to allocate.
      extra_hook: Optional function to be called on the result once the
        RPC has completed.

    Returns:
      A MultiRpc object.
    """
    if size is not None:
      if max is not None:
        raise datastore_errors.BadArgumentError(
          'Cannot allocate ids using both size and max')
      if not isinstance(size, (int, long)):
        raise datastore_errors.BadArgumentError('Invalid size (%r)' % (size,))
      if size > _MAX_ID_BATCH_SIZE:
        raise datastore_errors.BadArgumentError(
          'Cannot allocate more than %s ids at a time; received %s'
          % (_MAX_ID_BATCH_SIZE, size))
      if size <= 0:
        raise datastore_errors.BadArgumentError(
          'Cannot allocate less than 1 id; received %s' % size)
    if max is not None:
      if not isinstance(max, (int, long)):
        raise datastore_errors.BadArgumentError('Invalid max (%r)' % (max,))
      if max < 0:
        raise datastore_errors.BadArgumentError(
          'Cannot allocate a range with a max less than 0 id; received %s' %
          size)
    req = datastore_pb.AllocateIdsRequest()
    req.mutable_model_key().CopyFrom(self.__adapter.key_to_pb(key))
    if size is not None:
      req.set_size(size)
    if max is not None:
      req.set_max(max)
    resp = datastore_pb.AllocateIdsResponse()
    rpc = self.make_rpc_call(config, 'AllocateIds', req, resp,
                             self.__allocate_ids_hook, extra_hook)
    return rpc

  def __allocate_ids_hook(self, rpc):
    """Internal method used as get_result_hook for AllocateIds."""
    self.check_rpc_success(rpc)
    pair = rpc.response.start(), rpc.response.end()
    if rpc.user_data is not None:
      pair = rpc.user_data(pair)
    return pair


class TransactionalConnection(BaseConnection):
  """A connection specific to one transaction.

  It is possible to pass the transaction and entity group to the
  constructor, but typically the transaction is lazily created by
  _get_transaction() when the first operation is started.
  """

  @_positional(1)
  def __init__(self,
               adapter=None, config=None, transaction=None, entity_group=None):
    """Constructor.

    All arguments should be specified as keyword arguments.

    Args:
      adapter: Optional AbstractAdapter subclass instance;
        default IdentityAdapter.
      config: Optional Configuration object.
      transaction: Optional datastore_db.Transaction object.
      entity_group: Optional user-level key to be used as entity group
        constraining the transaction.  If specified, must be a
        top-level key.
    """
    super(TransactionalConnection, self).__init__(adapter=adapter,
                                                  config=config)
    self.__adapter = self.adapter
    if transaction is not None:
      if not isinstance(transaction, datastore_pb.Transaction):
        raise datastore_errors.BadArgumentError(
          'Invalid transaction (%r)' % (transaction,))
    self.__transaction = transaction
    self.__entity_group_pb = None
    if entity_group is not None:
      self.__entity_group_pb = self.__adapter.key_to_pb(entity_group)
      if self.__entity_group_pb.path().element_list()[1:]:
        raise datastore_errors.BadArgumentError(
          'Entity group must be a toplevel key')
      if transaction is not None:
        if self.__entity_group_pb.app() != transaction.app():
          raise datastore_errors.BadArgumentError(
            'Entity group app (%s) does not match transaction app (%s)' %
            (self.__entity_group_pb.app(), transaction.app()))
    self.__finished = False

  def _get_base_size(self, base_req):
    """Internal helper: return size in bytes plus room for transaction."""
    trans = self.__transaction
    if trans is None:




      incr_size = 1000
    else:

      incr_size = trans.lengthString(trans.ByteSize()) + 1
    return (super(TransactionalConnection, self)._get_base_size(base_req) +
            incr_size)

  @property
  def finished(self):
    return self.__finished

  @property
  def transaction(self):
    return self.__transaction

  @property
  def entity_group(self):
    return self.adapter.pb_to_key(self.__entity_group_pb)

  def _set_request_transaction(self, request):
    """Set the current transaction on a request.

    This calls _get_transaction() (see below).  The transaction object
    returned is both set as the transaction field on the request
    object and returned.

    Args:
      request: A protobuf with a transaction field.

    Returns:
      A datastore_pb.Transaction object or None.
    """
    transaction = self._get_transaction(request)
    request.mutable_transaction().CopyFrom(transaction)
    return transaction

  def _check_entity_group(self, key_pbs):
    """Check that a list of keys are consistent with the entity group.

    This also updates the connection's entity group if necessary.

    Args:
      key_pbs: A list of entity_pb.Reference objects.

    Raises:
      datastore_errors.BadRequestError if one or more of the keys
      refers to a different top-level key than the the connection's
      entity group.
    """
    for ref in key_pbs:
      entity_group_pb = ref
      if entity_group_pb.path().element_list()[1:]:
        entity_group_pb = self.__adapter.new_key_pb()
        entity_group_pb.CopyFrom(ref)
        del entity_group_pb.path().element_list()[1:]
      if self.__entity_group_pb is None:





        self.__entity_group_pb = entity_group_pb
      else:
        pb1 = entity_group_pb.path().element(0)
        ok = (entity_group_pb == self.__entity_group_pb)
        if ok:




          ok = (entity_group_pb is self.__entity_group_pb or
                pb1.id() or pb1.name())
        if not ok:
          pb0 = self.__entity_group_pb.path().element(0)
          def helper(pb):
            if pb.name():
              return 'name=%r' % pb.name()
            else:
              return 'id=%r' % pb.id()
          raise datastore_errors.BadRequestError(
              'Cannot operate on different entity groups in a transaction: '
              '(kind=%r, %s) and (kind=%r, %s).' %
              (pb0.type(), helper(pb0), pb1.type(), helper(pb1)))

  def _update_entity_group(self, key_pbs):
    """Patch up the entity group if we wrote an entity with an incomplete key.

    This should be called after a put() which could have assigned a
    key to an entity with an incomplete key.

    Args:
      key_pbs: A list of entity_pb.Reference objects.
    """
    pb = self.__entity_group_pb.path().element(0)
    if pb.id() or pb.name():
      return
    if not key_pbs:
      return
    ref = key_pbs[0]
    assert not ref.path().element_list()[1:]
    self.__entity_group_pb = ref

  def _get_transaction(self, request=None):
    """Get the transaction object for the current connection.

    This may send an RPC to get the transaction object and block
    waiting for it to complete.

    Args:
      request: Optional request protobuf object.  This is only used
        if it is a Query object; it is then used to extract the ancestor
        key for purposes of checking or setting the entity group.

    Returns:
      A datastore_pb.Transaction object.

    Raises:
      datastore_errors.BadRequestError if the transaction is already
      finished, or if the request argument represents an ancestor-less
      query, or if the ancestor does not match the connection's entity
      group.
    """

    if self.__finished:
      raise datastore_errors.BadRequestError(
        'Cannot start a new operation in a finished transaction.')
    key_pbs = None
    if isinstance(request, datastore_pb.Query):
      ok = request.has_ancestor()
      if ok:
        ref = request.ancestor()
        path = ref.path()
        ok = path.element_size()
        if ok:
          elem = path.element(ok - 1)
          ok = elem.id() or elem.name()
      if not ok:
        raise datastore_errors.BadRequestError(
          'Only ancestor queries are allowed inside a transaction.')
      key_pbs = [ref]
    if key_pbs is not None:
      self._check_entity_group(key_pbs)

    if self.__transaction is not None:
      return self.__transaction
    app = None
    if self.__entity_group_pb is not None:
      app = self.__entity_group_pb.app()
    if app is None:

      app = os.getenv('APPLICATION_ID')
    self.__transaction = self.begin_transaction(app)
    return self.__transaction

  def _end_transaction(self):
    """Finish the current transaction.

    This blocks waiting for all pending RPCs to complete, and then
    marks the connection as finished.  After that no more operations
    can be started using this connection.

    Returns:
      A datastore_pb.Transaction object or None.

    Raises:
      datastore_errors.BadRequestError if the transaction is already
      finished.
    """
    if self.__finished:
      raise datastore_errors.BadRequestError(
        'The transaction is already finished.')


    self.wait_for_all_pending_rpcs()
    assert not self.get_pending_rpcs()
    transaction = self.__transaction
    self.__finished = True
    self.__transaction = None
    return transaction



  def commit(self):
    """Synchronous Commit operation.

    Returns:
      True if the transaction was successfully committed.  False if
      the backend reported a concurrent transaction error.
    """


    rpc = self.create_rpc()
    rpc = self.async_commit(rpc)
    if rpc is None:
      return True
    return rpc.get_result()

  def async_commit(self, config):
    """Asynchronous Commit operation.

    Args:
      config: A Configuration object or None.  Defaults are taken from
        the connection's default configuration.

     Returns:
      A MultiRpc object.
    """
    transaction = self._end_transaction()
    if transaction is None:
      return None
    resp = datastore_pb.CommitResponse()
    rpc = self.make_rpc_call(config, 'Commit', transaction, resp,
                             self.__commit_hook)
    return rpc

  def __commit_hook(self, rpc):
    """Internal method used as get_result_hook for Commit."""
    try:
      rpc.check_success()
    except apiproxy_errors.ApplicationError, err:
      if err.application_error == datastore_pb.Error.CONCURRENT_TRANSACTION:
        return False
      else:
        raise _ToDatastoreError(err)
    else:
      return True



  def rollback(self):
    """Synchronous Rollback operation."""
    rpc = self.async_rollback(None)
    if rpc is None:
      return None
    return rpc.get_result()

  def async_rollback(self, config):
    """Asynchronous Rollback operation.

    Args:
      config: A Configuration object or None.  Defaults are taken from
        the connection's default configuration.

     Returns:
      A MultiRpc object.
    """
    transaction = self._end_transaction()
    if transaction is None:
      return None
    resp = api_base_pb.VoidProto()
    rpc = self.make_rpc_call(config, 'Rollback', transaction, resp,
                             self.__rollback_hook)
    return rpc

  def __rollback_hook(self, rpc):
    """Internal method used as get_result_hook for Rollback."""
    self.check_rpc_success(rpc)





def _ToDatastoreError(err):
  """Converts an apiproxy.ApplicationError to an error in datastore_errors.

  Args:
    err: An apiproxy.ApplicationError object.

  Returns:
    An instance of a subclass of datastore_errors.Error.
  """
  return _DatastoreExceptionFromErrorCodeAndDetail(err.application_error,
                                                   err.error_detail)


def _DatastoreExceptionFromErrorCodeAndDetail(error, detail):
  """Converts a datastore_pb.Error into a datastore_errors.Error.

  Args:
    error: A member of the datastore_pb.Error enumeration.
    detail: A string providing extra details about the error.

  Returns:
    An instance of a subclass of datastore_errors.Error.
  """
  exception_class = {
      datastore_pb.Error.BAD_REQUEST: datastore_errors.BadRequestError,
      datastore_pb.Error.CONCURRENT_TRANSACTION:
          datastore_errors.TransactionFailedError,
      datastore_pb.Error.INTERNAL_ERROR: datastore_errors.InternalError,
      datastore_pb.Error.NEED_INDEX: datastore_errors.NeedIndexError,
      datastore_pb.Error.TIMEOUT: datastore_errors.Timeout,
      datastore_pb.Error.BIGTABLE_ERROR: datastore_errors.Timeout,
      datastore_pb.Error.COMMITTED_BUT_STILL_APPLYING:
          datastore_errors.CommittedButStillApplying,
      datastore_pb.Error.CAPABILITY_DISABLED:
          apiproxy_errors.CapabilityDisabledError,
  }.get(error, datastore_errors.Error)

  if detail is None:
    return exception_class()
  else:
    return exception_class(detail)
