""" Removes all of zookeeper state. """
import zookeeper
PATH_SEPARATOR = "/"
TOP_LEVEL = "/appscale"
def receive_and_notify(_, event_type, state, path):
  pass

def delete_recursive(handle, path):
  try:
    children = zookeeper.get_children(handle, path)
    for child in children:
      delete_recursive(handle, PATH_SEPARATOR.join([path, child]))
    zookeeper.delete(handle, path, -1)
  except zookeeper.NoNodeException:
    pass

handle = zookeeper.init("localhost:2181", receive_and_notify)
delete_recursive(handle, TOP_LEVEL)
