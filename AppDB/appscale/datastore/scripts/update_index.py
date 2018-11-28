import argparse
import sys

from appscale.common import appscale_info
from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from appscale.datastore.index_manager import IndexManager
from appscale.datastore.utils import tornado_synchronous
from .. import appscale_datastore_batch
from ..datastore_distributed import DatastoreDistributed
from ..zkappscale import zktransaction as zk
from ..zkappscale.transaction_manager import TransactionManager

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore import datastore_pb


def prettify_index(index, initial_indent=3):
  """ Formats an index definition as it appears in the YAML definition.

  Args:
    index: An entity_pb.Index object.
  Returns:
    A string describing the index.
  """
  indent = ' ' * initial_indent
  output = 'kind: {}\n'.format(index.entity_type())
  if index.ancestor():
    output += '{}ancestor: yes\n'.format(indent)
  output += '{}properties:\n'.format(indent)
  for prop in index.property_list():
    output += '{}- name: {}\n'.format(indent, prop.name())
    if prop.direction() == prop.DESCENDING:
      output += '{}direction: desc\n'.format(indent + '  ')
  return output


def main():
  """ Updates a composite index after prompting the user. """
  parser = argparse.ArgumentParser(description='Updates composite indexes')
  parser.add_argument('--type', '-t', default='cassandra',
                      help='The datastore backend type')
  parser.add_argument('--app_id', '-a', required=True, help='The project ID')
  parser.add_argument('--all', action='store_true',
                      help='Updates all composite indexes')
  args = parser.parse_args()

  datastore_batch = appscale_datastore_batch.DatastoreFactory.\
    getDatastore(args.type)
  zookeeper_locations = appscale_info.get_zk_locations_string()
  zookeeper = zk.ZKTransaction(host=zookeeper_locations)
  transaction_manager = TransactionManager(zookeeper.handle)
  datastore_access = DatastoreDistributed(
    datastore_batch, transaction_manager, zookeeper=zookeeper)
  index_manager = IndexManager(zookeeper.handle, datastore_access)
  datastore_access.index_manager = index_manager

  indices = index_manager.projects[args.app_id].indexes_pb
  if len(indices) == 0:
    print('No composite indices found for app {}'.format(args.app_id))
    zookeeper.close()
    return

  update_composite_index_sync = tornado_synchronous(
    datastore_access.update_composite_index)

  if args.all:
    for index in indices:
      update_composite_index_sync(args.app_id, index)
    print('Successfully updated all composite indexes')
    return

  selection = -1
  selection_range = range(1, len(indices) + 1)
  while selection not in selection_range:
    for number, index in enumerate(indices, start=1):
      pretty_index = prettify_index(index.definition())
      print('{}) {}'.format(number, pretty_index))

    try:
      selection = int(raw_input('Select the index you want to update. (1-{}) '
        .format(len(indices))))
    except KeyboardInterrupt:
      zookeeper.close()
      sys.exit()

  selected_index = indices[selection - 1]
  update_composite_index_sync(args.app_id, selected_index)

  zookeeper.close()
  print('Index successfully updated')
