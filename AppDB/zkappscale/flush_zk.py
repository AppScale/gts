""" Removes all of zookeeper state. """
import kazoo.client

PATH_SEPARATOR = "/"
TOP_LEVEL = "/appscale"

def delete_recursive(handle, path):
  try:
    children = handle.get_children(path)
    for child in children:
      delete_recursive(handle, PATH_SEPARATOR.join([path, child]))
    handle.delete(path)
  except kazoo.exceptions.NoNodeError:
    pass

handle = kazoo.client.KazooClient(hosts="localhost:2181")
delete_recursive(handle, TOP_LEVEL)
