""" Prints all of zookeeper state. """
import kazoo.client

PATH_SEPARATOR = "/"
TOP_LEVEL = "/appscale"

def print_recursive(handle, path):
  try:
    children = handle.get_children(path)
    for child in children:
      print_recursive(handle, PATH_SEPARATOR.join([path, child]))
    value = handle.get(path)[0]
    print "{0} = {1}".format(path, value)
  except kazoo.exceptions.NoNodeError:
    pass

handle = kazoo.client.KazooClient(hosts="localhost:2181")
print_recursive(handle, TOP_LEVEL)
