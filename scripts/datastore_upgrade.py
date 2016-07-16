""" This script performs a data upgrade. """

import logging
import os
import subprocess
import sys
import time

sys.path.append(os.path.join(os.path.dirname(__file__), '../lib'))
import appscale_info
from constants import APPSCALE_HOME
from constants import CONTROLLER_SERVICE

sys.path.append(os.path.join(os.path.dirname(__file__), '../AppDB'))
import appscale_datastore_batch
import datastore_server
import dbconstants

from cassandra_env import cassandra_interface
from dbconstants import APP_ENTITY_SCHEMA
from dbconstants import APP_ENTITY_TABLE
from zkappscale import zktransaction as zk

sys.path.append(os.path.join(os.path.dirname(__file__), "../AppServer"))
from google.appengine.api import datastore_errors

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

# Success status.
SUCCESS = 'Success'

# Failed status for error encountered in a process.
FAILURE = 'Failed'

# Process keys for recording the status of the different steps
# in the upgrade script.
COMPLETION_STATUS = 'Completion-Status'
DELETE_JOURNAL_TABLE = 'Delete-Journal-Table'
STORE_DATASTORE_VERSION = 'Store-Datastore-version'
CLOSE_ZKTRANSACTION = 'Close-ZKTransaction-connection'
STOP_ZOO_KEEPER = 'Stop-ZooKeeper'
STOP_CASSANDRA = 'Stop-Cassandra'
VALIDATE_ENTITIES = 'Validate-Entities'
START_ZOOKEEPER = 'Start-ZooKeeper'
START_CASSANDRA = 'Start-Cassandra'

# The monit script to start the given service.
START_SERVICE_SCRIPT = "python " + APPSCALE_HOME + "/scripts/monit_start_service.py "

# The monit script to stop the given service.
STOP_SERVICE_SCRIPT = "python " + APPSCALE_HOME + "/scripts/monit_stop_service.py "

# The location of the script that initializes Cassandra config files.
SETUP_CASSANDRA_SCRIPT = os.path.join(APPSCALE_HOME, 'scripts',
                                      'setup_cassandra_config_files.py')

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

    logging.info("Successfully started Cassandra.")

def start_zookeeper(status_dict, zk_ips, keyname):
  """ Creates a monit configuration file and prompts Monit to start ZooKeeper.
    Args:
      status_dict: A dictionary to record the status of the executed process.
      zk_ips: A list of zookeeper node IPs to start ZooKeeper on.
      keyname: A string containing the deployment's keyname.
    """
  logging.info("Starting ZooKeeper...")
  for ip in zk_ips:
    start_service_cmd = START_SERVICE_SCRIPT + ZK_WATCH_NAME
    cmd_status = utils.ssh(ip, keyname, start_service_cmd)

    start_zookeeper_ip = START_ZOOKEEPER + "@" + ip
    if not cmd_status == 0:
      logging.error("Monit was unable to start ZooKeeper.")
      status_dict[start_zookeeper_ip] = FAILURE
      continue
    logging.info("Successfully started ZooKeeper.")
    status_dict[start_zookeeper_ip] = SUCCESS

def get_datastore():
  """ Returns a reference to the batch datastore interface. Validates where
  the <database>_interface.py is and adds that path to the system path.
  """
  db_info = appscale_info.get_db_info()
  db_type = db_info[':table']
  datastore_batch = appscale_datastore_batch.DatastoreFactory.getDatastore(db_type)
  return datastore_batch

def get_datastore_distributed(datastore, zk_location_ips):
  """ Returns a reference to the distributed datastore.
  Args:
    datastore: A reference to the batch datastore interface.
    zk_location_ips: A list of ZooKeeper location ips.
  """
  zookeeper_locations = get_zk_locations_string(zk_location_ips)
  zookeeper = zk.ZKTransaction(host=zookeeper_locations)
  datastore_distributed = datastore_server.DatastoreDistributed(datastore, zookeeper=zookeeper)
  return datastore_distributed, zookeeper

def get_zk_locations_string(zk_location_ips):
  """ Generates a ZooKeeper IP locations string.
  Args:
    zk_location_ips: A list of ZooKeeper IP locations.
  Returns:
    A string of ZooKeeper IP locations.
  """
  return (":" + str(zk.DEFAULT_PORT) + ",").join(zk_location_ips) + ":" + str(zk.DEFAULT_PORT)

def validate_and_update_entities(datastore, ds_distributed, zookeeper, db_ips,
  zk_ips, status_dict, keyname):
  """ Validates entities in batches of BATCH_SIZE, deletes tombstoned
  entities (if any) and updates invalid entities.
  Args:
    datastore: A reference to the batch datastore interface.
    ds_distributed: A reference to the distributed datastore.
    zookeeper: A reference to ZKTransaction, which communicates with
      ZooKeeper on the given host.
    db_ips: A list of database node IPs to stop Cassandra on, in case of error.
    zk_ips: A list of zookeeper node IPs to stop ZooKeeper on, in case of error.
    status_dict: A dictionary to record the status of the executed process.
    keyname: A string containing the deployment's keyname.
  """
  last_key = ""
  entities_checked = 0
  last_logged = time.time()
  while True:
    try:
      logging.debug("Fetching {} entities".format(BATCH_SIZE))
      entities = get_entity_batch(last_key, datastore, BATCH_SIZE)

      if not entities:
        break

      for entity in entities:
        process_entity(entity, datastore, ds_distributed)

      last_key = entities[-1].keys()[0]
      entities_checked += len(entities)

      if time.time() > last_logged + LOG_PROGRESS_FREQUENCY:
        logging.info("Checked {} entities".format(entities_checked))
        last_logged = time.time()

    except datastore_errors.Error as error:
      logging.error("Error getting and validating batch of entities: {}".format(error))
      status_dict[VALIDATE_ENTITIES] = str(error)
      close_connections(zookeeper, db_ips, zk_ips, status_dict, keyname)
      return
    except dbconstants.AppScaleDBConnectionError as conn_error:
      logging.error("Error getting and validating batch of entities: {}".format(conn_error))
      status_dict[VALIDATE_ENTITIES] = str(conn_error)
      close_connections(zookeeper, db_ips, zk_ips, status_dict, keyname)
      return

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

def process_entity(entity, datastore, ds_distributed):
  """ Processes an entity by updating it if necessary and removing tombstones.
  Args:
    entity: The entity to process.
    datastore: A reference to the batch datastore interface.
    ds_distributed: A reference to the distributed datastore.
  Returns:
    True on success, False otherwise.
  Raises:
    AppScaleDBConnectionError: If the operation could not be performed due to
       an error with Cassandra.
  """
  logging.debug("Process entity {}".format(str(entity)))
  key = entity.keys()[0]
  entity_data = entity[key][APP_ENTITY_SCHEMA[0]]
  version = entity[key][APP_ENTITY_SCHEMA[1]]

  app_id = key.split(dbconstants.KEY_DELIMITER)[0]
  validated_entity = ds_distributed.validated_result(app_id, entity)

  if key not in validated_entity:
    return delete_entity_from_table(key, datastore)

  valid_entity_data = validated_entity[key][APP_ENTITY_SCHEMA[0]]
  valid_entity_version = validated_entity[key][APP_ENTITY_SCHEMA[1]]
  if valid_entity_data == datastore_server.TOMBSTONE:
    return delete_entity_from_table(key, datastore)

  if valid_entity_data != entity_data or valid_entity_version != version:
    return update_entity_in_table(key, validated_entity, datastore)

  return True

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
                             {key: validated_entity[key]})

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

def stop_cassandra(db_ips, status_dict, keyname):
  """ Stops Cassandra.
  Args:
    db_ips: A list of database node IPs to stop Cassandra on.
    status_dict: A dictionary to record the status of the executed process.
    keyname: A string containing the deployment's keyname.
  """
  logging.info("Stopping Cassandra...")
  for ip in db_ips:
    stop_service_cmd = STOP_SERVICE_SCRIPT + CASSANDRA_WATCH_NAME
    cmd_status = utils.ssh(ip, keyname, stop_service_cmd)

    stop_cassandra_ip = STOP_CASSANDRA + "@" + ip
    if not cmd_status == 0:
      logging.error("Monit was unable to stop Cassandra.")
      status_dict[stop_cassandra_ip] = FAILURE
      continue
    logging.info("Successfully stopped Cassandra.")
    status_dict[stop_cassandra_ip] = SUCCESS

def stop_zookeeper(zk_ips, status_dict, keyname):
  """ Stops ZooKeeper.
  Args:
    zk_ips: A list of zookeeper node IPs to stop ZooKeeper on.
    status_dict: A dictionary to record the status of the executed process.
    keyname: A string containing the deployment's keyname.
  """
  logging.info("Stopping ZooKeeper...")
  for ip in zk_ips:
    stop_service_cmd = STOP_SERVICE_SCRIPT + ZK_WATCH_NAME
    cmd_status = utils.ssh(ip, keyname, stop_service_cmd)

    stop_zookeeper_ip = STOP_ZOO_KEEPER + "@" + ip
    if not cmd_status == 0:
      logging.error("Monit was unable to stop ZooKeeper.")
      status_dict[stop_zookeeper_ip] = FAILURE
      continue
    logging.info("Successfully stopped ZooKeeper.")
    status_dict[stop_zookeeper_ip] = SUCCESS

def close_zktransaction(zookeeper, status_dict):
  """ Closes the connection to ZKTransaction.
  Args:
    zookeeper: A reference to ZKTransaction, which communicates with
      ZooKeeper on the given host.
    status_dict: A dictionary to record the status of the executed process.
  """
  zookeeper.close()
  logging.info("Closed the connection to ZKTransaction.")
  status_dict[CLOSE_ZKTRANSACTION] = SUCCESS

def close_connections(zookeeper, db_ips, zk_ips, status_dict, keyname):
  """ Close connections to Cassandra, ZooKeeper and ZKTransaction.
  Args:
    zookeeper: A reference to ZKTransaction, which communicates with
      ZooKeeper on the given host.
    db_ips: A list of database node IPs to stop Cassandra on.
    zk_ips: A list of zookeeper node IPs to stop ZooKeeper on.
    status_dict: A dictionary to record the status of the executed process.
    keyname: A string containing the deployment's keyname.
  """
  close_zktransaction(zookeeper, status_dict)
  stop_cassandra(db_ips, status_dict, keyname)
  stop_zookeeper(zk_ips, status_dict, keyname)

def drop_journal_table(datastore, zookeeper,db_ips, zk_ips, status_dict, keyname):
  """ Drop JOURNAL_TABLE.
  Args:
    datastore: A reference to the batch datastore interface.
    zookeeper: A reference to ZKTransaction, which communicates with
      ZooKeeper on the given host.
    db_ips: A list of database node IPs to stop Cassandra on, in case of error.
    zk_ips: A list of zookeeper node IPs to stop ZooKeeper on, in case of error.
    status_dict: A dictionary to record the status of the executed process.
    keyname: A string containing the deployment's keyname.
  """
  try:
    datastore.delete_table(dbconstants.JOURNAL_TABLE)
  except dbconstants.AppScaleDBConnectionError as conn_error:
    logging.error("Error deleting the JOURNAL_TABLE: {}".format(conn_error))
    status_dict[DELETE_JOURNAL_TABLE] = str(conn_error)
    close_connections(zookeeper, db_ips, zk_ips, status_dict, keyname)
    return

def all_services_started(status_dict):
  """ Loops through the values of the status dictionary to check the status
  of ZooKeeper and Cassandra started on their nodes.
  Args:
    status_dict: A dictionary to record the status of the executed process.
  """
  for value in status_dict.values():
    if value == FAILURE:
      return False
  return True

def ensure_cassandra_nodes_match_replication(keyname):
  """ Waits until enough Cassandra nodes are up to match the required
  replication factor.
  Args:
    keyname: A string containing the deployment's keyname.
  """
  command = cassandra_interface.NODE_TOOL + " " + 'status'
  key_file = '{}/{}.key'.format(utils.KEY_DIRECTORY, keyname)
  ssh_cmd = ['ssh', '-i', key_file, appscale_info.get_db_master_ip(), command]
  cmd_output = subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE)

  nodes_ready = 0
  # Get the replication factor from the database_info.yaml file.
  db_info = appscale_info.get_db_info()
  replication = db_info[':replication']

  while True:
    for line in cmd_output.stdout:
      if line.startswith('UN'):
        nodes_ready += 1

    logging.info("{0} nodes are up. {1} are needed.".format(nodes_ready, replication))
    if nodes_ready >= int(replication):
      break
    time.sleep(1)

def run_datastore_upgrade(zk_ips, db_ips, db_master, status_dict, keyname):
  """ Runs the data upgrade process of fetching, validating and updating data
  within ZooKeeper & Cassandra.
  Args:
    zk_ips: A list of ZooKeeper node IPs.
    db_ips: A list of database node IPs.
    db_master: The IP address of the DB master.
    status_dict: A dictionary to record the status of the executed process.
    keyname: A string containing the deployment's keyname.
  """
  # This datastore upgrade script is to be run offline, so make sure
  # appscale is not up while running this script.
  ensure_app_is_not_running()

  # Start Cassandra and ZooKeeper.
  try:
    start_cassandra(db_ips, db_master, keyname)
    status_dict[START_CASSANDRA] = SUCCESS
  except dbconstants.AppScaleDBError:
    status_dict[START_CASSANDRA] = FAILURE
    return

  # Ensure enough Cassandra nodes are available.
  ensure_cassandra_nodes_match_replication(keyname)

  start_zookeeper(status_dict, zk_ips, keyname)

  if not all_services_started(status_dict):
    stop_cassandra(db_ips, status_dict, keyname)
    stop_zookeeper(zk_ips, status_dict, keyname)
    return

  datastore = get_datastore()
  ds_distributed, zookeeper = get_datastore_distributed(datastore, zk_ips)

  # Loop through entities table, fetch valid entities from journal table
  # if necessary, delete tombstoned entities and updated invalid ones.
  validate_and_update_entities(datastore, ds_distributed, zookeeper, db_ips,
    zk_ips, status_dict, keyname)

  # If validating and updating entities logged an error in the status dict,
  # return from this script.
  if VALIDATE_ENTITIES in status_dict:
    return

  status_dict[VALIDATE_ENTITIES] = SUCCESS
  logging.info("Updated invalid entities and deleted tombstoned entities.")

  # Update the data version.
  try:
    datastore.set_metadata(cassandra_interface.VERSION_INFO_KEY,
                           str(cassandra_interface.DATA_VERSION))
    status_dict[STORE_DATASTORE_VERSION] = SUCCESS
    logging.info('Stored the data version successfully.')
  except dbconstants.AppScaleDBConnectionError as db_error:
    status_dict[STORE_DATASTORE_VERSION] = db_error.message
    close_connections(zookeeper, db_ips, zk_ips, status_dict, keyname)
    return

  # Drop the JOURNAL_TABLE.
  drop_journal_table(datastore, zookeeper, db_ips, zk_ips, status_dict,
                     keyname)

  # If dropping the Journal Table logged an error in the status dict,
  # return from this script.
  if DELETE_JOURNAL_TABLE in status_dict:
    return

  status_dict[DELETE_JOURNAL_TABLE] = SUCCESS
  logging.info("Deleted Journal Table sucessfully.")

  # Stop Cassandra & ZooKeeper and close connection to ZKTransaction.
  close_connections(zookeeper, db_ips, zk_ips, status_dict, keyname)
  status_dict[COMPLETION_STATUS] = SUCCESS
