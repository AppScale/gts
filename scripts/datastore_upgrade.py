""" This script performs a data upgrade. """

import json
import logging
import math
import os
import subprocess
import sys
import time

from appscale.datastore import appscale_datastore_batch
from appscale.datastore import dbconstants
from appscale.datastore.dbconstants import APP_ENTITY_SCHEMA
from appscale.datastore.dbconstants import APP_ENTITY_TABLE
from appscale.datastore.dbconstants import ID_KEY_LENGTH
from appscale.datastore.dbconstants import TOMBSTONE
from appscale.datastore.cassandra_env import cassandra_interface
from appscale.datastore.zkappscale import zktransaction as zk
from appscale.datastore.zkappscale.zktransaction import ZK_SERVER_CMD_LOCATIONS
from appscale.datastore.zkappscale.zktransaction import ZKInternalException
from cassandra.query import ConsistencyLevel
from cassandra.query import SimpleStatement

sys.path.append(os.path.join(os.path.dirname(__file__), '../lib'))
import appscale_info
from constants import APPSCALE_HOME
from constants import CONTROLLER_SERVICE
from constants import LOG_DIR

sys.path.append(os.path.join(os.path.dirname(__file__), "../InfrastructureManager"))
from utils import utils

# The number of entities retrieved in a datastore request.
BATCH_SIZE = 100

# Log progress every time this many seconds have passed.
LOG_PROGRESS_FREQUENCY = 30

# Monit watch name for Cassandra.
CASSANDRA_WATCH_NAME = "cassandra"

# Monit watch name for ZooKeeper.
ZK_WATCH_NAME = "zookeeper"

# The monit script to start the given service.
START_SERVICE_SCRIPT = "python " + APPSCALE_HOME + "/scripts/monit_start_service.py "

# The monit script to stop the given service.
STOP_SERVICE_SCRIPT = "python " + APPSCALE_HOME + "/scripts/monit_stop_service.py "

# The location of the script that initializes Cassandra config files.
SETUP_CASSANDRA_SCRIPT = os.path.join(APPSCALE_HOME, 'scripts',
                                      'setup_cassandra_config_files.py')

# JSON file location to record the status of the processes.
STATUS_FILE = os.path.join(LOG_DIR, 'upgrade-status-{postfix}.json')


def write_to_json_file(data, timestamp):
  """ Writes the dictionary containing the status of operations performed
  during the upgrade process into a JSON file.
  Args:
    data: A dictionary containing status of upgrade operations performed.
    timestamp: The timestamp passed from the tools to append to the upgrade
    status log file.
  """
  with open(STATUS_FILE.format(postfix=timestamp), 'w') as status_file:
    json.dump(data, status_file)


def ensure_app_is_not_running():
  """ Ensures AppScale is not running as this is an offline script. """
  logging.info("Ensure AppScale is not currently running...")
  appscale_running = subprocess.call(['service', CONTROLLER_SERVICE, 'status']) == 0
  if appscale_running:
    logging.info("AppScale is running, please shut it down and try again.")
    sys.exit(1)


def start_cassandra(db_ips, db_master, keyname):
  """ Creates a monit configuration file and prompts Monit to start Cassandra.
  Args:
    db_ips: A list of database node IPs to start Cassandra on.
    db_master: The IP address of the DB master.
    keyname: A string containing the deployment's keyname.
  Raises:
    AppScaleDBError if unable to start Cassandra.
  """
  logging.info("Starting Cassandra...")
  for ip in db_ips:
    init_config = '{script} --local-ip {ip} --master-ip {db_master}'.format(
      script=SETUP_CASSANDRA_SCRIPT, ip=ip, db_master=db_master)
    try:
      utils.ssh(ip, keyname, init_config)
    except subprocess.CalledProcessError:
      message = 'Unable to configure Cassandra on {}'.format(ip)
      logging.exception(message)
      raise dbconstants.AppScaleDBError(message)

    try:
      start_service_cmd = START_SERVICE_SCRIPT + CASSANDRA_WATCH_NAME
      utils.ssh(ip, keyname, start_service_cmd)
    except subprocess.CalledProcessError:
      message = 'Unable to start Cassandra on {}'.format(ip)
      logging.exception(message)
      raise dbconstants.AppScaleDBError(message)

  logging.info('Waiting for Cassandra to be ready')
  status_cmd = '{} status'.format(cassandra_interface.NODE_TOOL)
  while (utils.ssh(db_master, keyname, status_cmd,
                   method=subprocess.call) != 0):
    time.sleep(5)

  logging.info("Successfully started Cassandra.")


def start_zookeeper(zk_ips, keyname):
  """ Creates a monit configuration file and prompts Monit to start ZooKeeper.
    Args:
      zk_ips: A list of zookeeper node IPs to start ZooKeeper on.
      keyname: A string containing the deployment's keyname.
    """
  logging.info("Starting ZooKeeper...")
  for ip in zk_ips:
    start_service_cmd = START_SERVICE_SCRIPT + ZK_WATCH_NAME
    try:
      utils.ssh(ip, keyname, start_service_cmd)
    except subprocess.CalledProcessError:
      message = 'Unable to start ZooKeeper on {}'.format(ip)
      logging.exception(message)
      raise ZKInternalException(message)

  logging.info('Waiting for ZooKeeper to be ready')
  zk_server_cmd = None
  for script in ZK_SERVER_CMD_LOCATIONS:
    if os.path.isfile(script):
      zk_server_cmd = script
      break
  if zk_server_cmd is None:
    raise ZKInternalException('Unable to find zkServer.sh')

  status_cmd = '{} status'.format(zk_server_cmd)
  while (utils.ssh(zk_ips[0], keyname, status_cmd,
                   method=subprocess.call) != 0):
    time.sleep(5)

  logging.info("Successfully started ZooKeeper.")


def get_datastore():
  """ Returns a reference to the batch datastore interface. Validates where
  the <database>_interface.py is and adds that path to the system path.
  """
  db_info = appscale_info.get_db_info()
  db_type = db_info[':table']
  datastore_batch = appscale_datastore_batch.DatastoreFactory.getDatastore(db_type)
  return datastore_batch


def get_zookeeper(zk_location_ips):
  """ Returns a handler for making ZooKeeper operations.
  Args:
    zk_location_ips: A list of ZooKeeper location ips.
  """
  zookeeper_locations = get_zk_locations_string(zk_location_ips)
  zookeeper = zk.ZKTransaction(host=zookeeper_locations, start_gc=False)
  return zookeeper


def get_zk_locations_string(zk_location_ips):
  """ Generates a ZooKeeper IP locations string.
  Args:
    zk_location_ips: A list of ZooKeeper IP locations.
  Returns:
    A string of ZooKeeper IP locations.
  """
  return (":" + str(zk.DEFAULT_PORT) + ",").join(zk_location_ips) + ":" + str(zk.DEFAULT_PORT)


def validate_and_update_entities(db_access, zookeeper, log_postfix,
                                 total_entities):
  """ Validates entities in batches of BATCH_SIZE, deletes tombstoned
  entities (if any) and updates invalid entities.
  Args:
    db_access: A reference to the batch datastore interface.
    zookeeper: A reference to ZKTransaction, which communicates with
      ZooKeeper on the given host.
    log_postfix: An identifier for the status log.
    total_entities: A string containing an entity count or None.
  """
  last_key = ""
  entities_checked = 0
  last_logged = time.time()
  while True:
    logging.debug("Fetching {} entities".format(BATCH_SIZE))
    entities = get_entity_batch(last_key, db_access, BATCH_SIZE)

    if not entities:
      break

    for entity in entities:
      process_entity(entity, db_access, zookeeper)

    last_key = entities[-1].keys()[0]
    entities_checked += len(entities)

    if time.time() > last_logged + LOG_PROGRESS_FREQUENCY:
      progress = str(entities_checked)
      if total_entities is not None:
        progress += '/{}'.format(total_entities)
      message = 'Processed {} entities'.format(progress)
      logging.info(message)
      write_to_json_file({'status': 'inProgress', 'message': message},
                         log_postfix)
      last_logged = time.time()


def get_entity_batch(last_key, datastore, batch_size):
  """ Gets a batch of entities to operate on.
  Args:
    last_key: The last key from a previous query.
    datastore: A reference to the batch datastore interface.
    batch_size: The max number of entities retrieved in the datastore request.
  Returns:
    A list of entities with a limit of batch_size.
  """
  return datastore.range_query(APP_ENTITY_TABLE, APP_ENTITY_SCHEMA, last_key,
    "", batch_size, start_inclusive=False)


def validate_row(app_id, row, zookeeper, db_access):
  """ Fetch the valid version of a given entity.

  Args:
    app_id: A string containing the application ID.
    row: A dictionary containing a row from the entities table.
    zookeeper: A handler for making ZooKeeper operations.
    db_access: A handler for making database operations.
  Returns:
    An dictionary with a valid entity row or None.
  """
  row_key = row.keys()[0]
  entity = row.values()[0]

  # If there is no transaction ID for the record, assume it is valid.
  if APP_ENTITY_SCHEMA[1] not in entity:
    return row

  row_txn = long(entity[APP_ENTITY_SCHEMA[1]])
  valid_txn = zookeeper.get_valid_transaction_id(app_id, row_txn, row_key)

  # If the transaction ID is valid, the entity is valid.
  if row_txn == valid_txn:
    return row

  # A transaction ID of 0 indicates that the entity doesn't exist yet.
  if valid_txn == 0:
    return None

  padded_version = str(valid_txn).zfill(ID_KEY_LENGTH)
  journal_key = dbconstants.KEY_DELIMITER.join([row_key, padded_version])
  journal_results = db_access.batch_get_entity(
    dbconstants.JOURNAL_TABLE, [journal_key], dbconstants.JOURNAL_SCHEMA)
  journal_row = journal_results[journal_key]

  if dbconstants.JOURNAL_SCHEMA[0] not in journal_row:
    return None

  valid_entity = journal_row[dbconstants.JOURNAL_SCHEMA[0]]
  return {row_key: {APP_ENTITY_SCHEMA[0]: valid_entity,
                    APP_ENTITY_SCHEMA[1]: str(valid_txn)}}


def process_entity(entity, datastore, zookeeper):
  """ Processes an entity by updating it if necessary and removing tombstones.
  Args:
    entity: The entity to process.
    datastore: A reference to the batch datastore interface.
    zookeeper: A handler for making ZooKeeper operations.
  Raises:
    AppScaleDBConnectionError: If the operation could not be performed due to
       an error with Cassandra.
  """
  logging.debug("Process entity {}".format(str(entity)))
  key = entity.keys()[0]

  app_id = key.split(dbconstants.KEY_DELIMITER)[0]
  valid_entity = validate_row(app_id, entity, zookeeper, datastore)

  if (valid_entity is None or
      valid_entity[key][APP_ENTITY_SCHEMA[0]] == TOMBSTONE):
    delete_entity_from_table(key, datastore)
    return

  if valid_entity != entity:
    update_entity_in_table(key, valid_entity, datastore)


def update_entity_in_table(key, validated_entity, datastore):
  """ Updates the APP_ENTITY_TABLE with the valid entity.
  Args:
    key: A str representing the row key to update in the table.
    validated_entity: A validated entity which needs to be updated in place of
    the current entity.
    datastore: A reference to the batch datastore interface.
  Raises:
    AppScaleDBConnectionError: If the batch_put could not be performed due to
      an error with Cassandra.
  """
  datastore.batch_put_entity(APP_ENTITY_TABLE, [key], APP_ENTITY_SCHEMA,
                             validated_entity)


def delete_entity_from_table(key, datastore):
  """ Performs a hard delete on the APP_ENTITY_TABLE for the given row key.
  Args:
    key: A str representing the row key to delete from the table.
    datastore: A reference to the batch datastore interface.
  Raises:
    AppScaleDBConnectionError: If the batch_delete could not be performed due to
      an error with Cassandra.
  """
  datastore.batch_delete(APP_ENTITY_TABLE, [key])


def stop_cassandra(db_ips, keyname):
  """ Stops Cassandra.
  Args:
    db_ips: A list of database node IPs to stop Cassandra on.
    keyname: A string containing the deployment's keyname.
  """
  logging.info("Stopping Cassandra...")
  for ip in db_ips:
    stop_service_cmd = STOP_SERVICE_SCRIPT + CASSANDRA_WATCH_NAME
    try:
      utils.ssh(ip, keyname, stop_service_cmd)
    except subprocess.CalledProcessError:
      logging.error('Unable to stop Cassandra on {}'.format(ip))


def stop_zookeeper(zk_ips, keyname):
  """ Stops ZooKeeper.
  Args:
    zk_ips: A list of zookeeper node IPs to stop ZooKeeper on.
    keyname: A string containing the deployment's keyname.
  """
  logging.info("Stopping ZooKeeper...")
  for ip in zk_ips:
    stop_service_cmd = STOP_SERVICE_SCRIPT + ZK_WATCH_NAME
    try:
      utils.ssh(ip, keyname, stop_service_cmd)
    except subprocess.CalledProcessError:
      logging.error('Unable to stop ZooKeeper on {}'.format(ip))


def wait_for_quorum(keyname, db_nodes, replication):
  """ Waits until enough Cassandra nodes are up for a quorum.

  Args:
    keyname: A string containing the deployment's keyname.
    db_nodes: An integer specifying the total number of DB nodes.
    replication: An integer specifying the keyspace replication factor.
  """
  command = cassandra_interface.NODE_TOOL + " " + 'status'
  key_file = '{}/{}.key'.format(utils.KEY_DIRECTORY, keyname)
  ssh_cmd = ['ssh', '-i', key_file, appscale_info.get_db_master_ip(), command]

  # Determine the number of nodes needed for a quorum.
  if db_nodes < 1 or replication < 1:
    raise dbconstants.AppScaleDBError('At least 1 database machine is needed.')
  if replication > db_nodes:
    raise dbconstants.AppScaleDBError(
      'The replication factor cannot exceed the number of database machines.')
  can_fail = math.ceil(replication/2.0 - 1)
  needed = int(db_nodes - can_fail)

  while True:
    output = subprocess.check_output(ssh_cmd)
    nodes_ready = len(
      [line for line in output.splitlines() if line.startswith('UN')])
    logging.info('{} nodes are up. {} are needed.'.format(nodes_ready, needed))
    if nodes_ready >= needed:
      break
    time.sleep(1)


def estimate_total_entities(session, db_master, keyname):
  """ Estimate the total number of entities.

  Args:
    session: A cassandra-driver session.
    db_master: A string containing the IP address of the primary DB node.
    keyname: A string containing the deployment keyname.
  Returns:
    A string containing an entity count.
  Raises:
    AppScaleDBError if unable to get a count.
  """
  query = SimpleStatement(
    'SELECT COUNT(*) FROM "{}"'.format(dbconstants.APP_ENTITY_TABLE),
    consistency_level=ConsistencyLevel.ONE
  )
  try:
    rows = session.execute(query)[0].count
    return str(rows / len(dbconstants.APP_ENTITY_SCHEMA))
  except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
    stats_cmd = '{nodetool} cfstats {keyspace}.{table}'.format(
      nodetool=cassandra_interface.NODE_TOOL,
      keyspace=cassandra_interface.KEYSPACE,
      table=dbconstants.APP_ENTITY_TABLE)
    stats = utils.ssh(db_master, keyname, stats_cmd,
                      method=subprocess.check_output)
    for line in stats.splitlines():
      if 'Number of keys (estimate)' in line:
        return '{} (estimate)'.format(line.split()[-1])
  raise dbconstants.AppScaleDBError('Unable to estimate total entities.')


def run_datastore_upgrade(db_access, zookeeper, log_postfix, total_entities):
  """ Runs the data upgrade process of fetching, validating and updating data
  within ZooKeeper & Cassandra.
  Args:
    db_access: A handler for interacting with Cassandra.
    zookeeper: A handler for interacting with ZooKeeper.
    log_postfix: An identifier for the status log.
    total_entities: A string containing an entity count or None.
  """
  # This datastore upgrade script is to be run offline, so make sure
  # appscale is not up while running this script.
  ensure_app_is_not_running()

  # Loop through entities table, fetch valid entities from journal table
  # if necessary, delete tombstoned entities and updated invalid ones.
  validate_and_update_entities(db_access, zookeeper, log_postfix,
                               total_entities)

  logging.info("Updated invalid entities and deleted tombstoned entities.")

  # Update the data version.
  db_access.set_metadata(cassandra_interface.VERSION_INFO_KEY,
                         str(cassandra_interface.EXPECTED_DATA_VERSION))
  logging.info('Stored the data version successfully.')

  db_access.delete_table(dbconstants.JOURNAL_TABLE)
  logging.info("Deleted Journal Table sucessfully.")
