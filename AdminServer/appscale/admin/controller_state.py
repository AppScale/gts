import json
from tornado.ioloop import IOLoop

from appscale.admin.constants import CONTROLLER_STATE_NODE


class ControllerState(object):
  """ Keeps track of the latest controller state. """
  def __init__(self, zk_client):
    """ Creates a new ControllerState object.

    Args:
      zk_client: A KazooClient.
    """
    self.options = None
    zk_client.DataWatch(CONTROLLER_STATE_NODE, self._controller_state_watch)

  def _update_controller_state(self, encoded_controller_state):
    """ Handles updates to controller state.

    Args:
      encoded_controller_state: A JSON-encoded string containing controller
        state.
    """
    if not encoded_controller_state:
      return

    controller_state = json.loads(encoded_controller_state)
    self.options = controller_state.get('@options')

  def _controller_state_watch(self, encoded_controller_state, _):
    """ Handles updates to controller state.

    Args:
      encoded_controller_state: A JSON-encoded string containing controller
        state.
    """
    IOLoop.instance().add_callback(self._update_controller_state,
                                   encoded_controller_state)
