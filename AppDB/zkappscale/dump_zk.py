""" Prints all of zookeeper state. """
import zookeeper
PATH_SEPARATOR = "/"
TOP_LEVEL = "/appscale"
def receive_and_notify(_, event_type, state, path):
  pass

def print_recursive(handle, path):
  try:
    children = zookeeper.get_children(handle, path)
    for child in children:
      print_recursive(handle, PATH_SEPARATOR.join([path, child]))
    value = zookeeper.get(handle, path)[0]
    print "{0} = {1}".format(path, value)
  except zookeeper.NoNodeException:
    pass

handle = zookeeper.init("localhost:2181", receive_and_notify)
print_recursive(handle, TOP_LEVEL)
