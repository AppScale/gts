""" Keeps track of the head node's controller state. """
import json

from kazoo.client import NoNodeError
from tornado.ioloop import IOLoop


class InvalidControllerState(Exception):
  """ Indicates that the controller state is not currently available. """
  pass


class ControllerState(object):
  """ Keeps track of the head node's controller state. """

  # The ZooKeeper path that the controller uses to store its state.
  STATE_PATH = '/appcontroller/state'

  def __init__(self, zk_client):
    """ Creates a new ControllerState object.

    Args:
      zk_client: A KazooClient.
    """
    self._callback_functions = []
    self._state = {}
    self._zk_client = zk_client

    # Populate the state in case this container is used synchronously.
    try:
      encoded_state = self._zk_client.get(self.STATE_PATH)[0]
      self._update_state(encoded_state)
      self._valid = True
    except NoNodeError:
      self._valid = False

    self._zk_client.DataWatch(self.STATE_PATH, self._update_state_watch)

  def add_callback(self, callback_function):
    """ Add a function to be called whenever the state is updated.

    Args:
      callback_function: A function that should be called.
    """
    self._callback_functions.append(callback_function)

  def get(self, key):
    """ Provides access to the controller state by key.

    Args:
      key: A string specifying the key to retrieve.
    Returns:
      Whatever object is present at the given key or None.
    Raises:
      InvalidControllerState if the state is not available.
    """
    if not self._valid:
      raise InvalidControllerState('Invalid controller state')

    return self._state.get(key)

  def __getitem__(self, key):
    """ Provides access to the controller state by key.

    Args:
      key: A string specifying the key to retrieve.
    Returns:
      Whatever object is present at the given key.
    Raises:
      InvalidControllerState if the state is not available.
      KeyError if the state does not contain the key.
    """
    if not self._valid:
      raise InvalidControllerState('Invalid controller state')

    return self._state[key]

  def _update_state(self, encoded_state):
    """ Updates the copy of the controller's state.

    Args:
      encoded_state: A JSON-encoded string containing the controller's state
        dump.
    """
    try:
      self._state = json.loads(encoded_state)
    except (TypeError, ValueError):
      self._valid = False
      return

    if not isinstance(self._state, dict):
      self._valid = False
      return

    self._valid = True
    for callback_function in self._callback_functions:
      callback_function(self._state)

  def _update_state_watch(self, encoded_state, _):
    """ Updates the copy of the controller state.

    Args:
      encoded_state: A JSON-encoded string containing the controller's state
        dump.
    """
    IOLoop.current().add_callback(self._update_state, encoded_state)
