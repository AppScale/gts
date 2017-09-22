""" A wrapper that converts Kazoo operations to Tornado futures. """
from tornado.concurrent import Future as TornadoFuture


class IncompleteOperation(Exception):
  """ Indicates that a Kazoo operation is not complete. """
  pass


class TornadoKazooFuture(TornadoFuture):
  """ A TornadoFuture that handles Kazoo results. """
  def handle_zk_result(self, async_result):
    """ Completes the TornadoFuture.

    Args:
      async_result: An IAsyncResult.
    """
    # This method should not be called if the result is not ready.
    if not async_result.ready():
      self.set_exception(IncompleteOperation('Kazoo operation is not ready'))
      return

    if async_result.successful():
      self.set_result(async_result.value)
    else:
      self.set_exception(async_result.exception)


class TornadoKazoo(object):
  """ A wrapper that converts Kazoo operations to Tornado futures. """
  def __init__(self, zk_client):
    """ Creates a new TornadoKazoo manager.

    Args:
      zk_client: A KazooClient.
    """
    self._zk_client = zk_client

  def get(self, path, watch=None):
    """ Gets the value of a node.

    Args:
      path: A string specifying the path of the node.
      watch: A function that is called when the node changes.
    Returns:
      A TornadoKazooFuture.
    """
    tornado_future = TornadoKazooFuture()
    zk_future = self._zk_client.get_async(path, watch)
    zk_future.rawlink(tornado_future.handle_zk_result)
    return tornado_future

  def get_children(self, path, watch=None, include_data=False):
    """ Gets a list of child nodes of a path.

    Args:
      path: A string specifying the path of the parent node.
      watch: A function that is called when the node changes.
      include_data: A boolean specifying that the parent node contents should
        also be fetched.
    Returns:
      A TornadoKazooFuture.
    """
    tornado_future = TornadoKazooFuture()
    zk_future = self._zk_client.get_children_async(path, watch, include_data)
    zk_future.rawlink(tornado_future.handle_zk_result)
    return tornado_future

  def delete(self, path, version=-1):
    """ Deletes a node.

    Args:
      path: A string specifying the path of the node.
      version: An integer specifying the expected version of the node.
    Returns:
      A TornadoKazooFuture.
    """
    tornado_future = TornadoKazooFuture()
    zk_future = self._zk_client.delete_async(path, version=version)
    zk_future.rawlink(tornado_future.handle_zk_result)
    return tornado_future
