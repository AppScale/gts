#!/usr/bin/env python2

import appscale_datastore_batch
import appscale_info
from datastore_server import DatastoreDistributed
import getopt
import sys
from zkappscale import zktransaction as zk

from google.appengine.datastore import datastore_pb

def usage():
  """ Prints the usage of this script. """
  print('Usage: update_index.py OPTION')
  print('Updates a composite index.\n')
  print('Options:')
  print('  -t, --type=DATASTORE_TYPE    e.g. cassandra')
  print('  -a, --app_ID=APPLICATION_ID  e.g. guestbook')

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

def main(app_id, db_type):
  """ Updates a composite index after prompting the user.

  Args:
    app_id: A string containing the application ID.
    db_type: A string specifying which database backend to use.
  """
  datastore_batch = appscale_datastore_batch.DatastoreFactory.\
    getDatastore(db_type)
  zookeeper_locations = appscale_info.get_zk_locations_string()
  zookeeper = zk.ZKTransaction(host=zookeeper_locations)
  datastore_access = DatastoreDistributed(datastore_batch,
    zookeeper=zookeeper)

  pb_indices = datastore_access.get_indices(app_id)
  indices = [datastore_pb.CompositeIndex(index) for index in pb_indices]
  if len(indices) == 0:
      print('No composite indices found for app {}'.format(app_id))
      zookeeper.close()
      sys.exit(1)

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
  datastore_access.update_composite_index(app_id, selected_index)

  zookeeper.close()

if __name__ == '__main__':
  try:
    opts, remainder = getopt.getopt(sys.argv[1:], 't:a:',
      ['type=', 'app_id='])
  except getopt.GetoptError:
    usage()
    sys.exit(1)

  db_type = None
  app_id = None
  for opt, arg in opts:
    if opt in ('-t', '--type'):
      db_type = arg
    elif opt in ('-a', '--app_id'):
      app_id = arg

  if not db_type or not app_id:
    usage()
    sys.exit(1)

  main(app_id, db_type)
