import json
import logging
import os
import subprocess
import sys
import time

sys.path.append(os.path.join(os.path.dirname(__file__), '../lib'))
import appscale_info
from constants import CONTROLLER_SERVICE
from constants import APPSCALE_HOME
import monit_interface
import monit_app_configuration

sys.path.append(os.path.join(os.path.dirname(__file__), '../AppDB'))
import appscale_datastore_batch
import datastore_server
import entity_utils
from cassandra_env import cassandra_interface
from dbconstants import *
from zkappscale import zktransaction as zk


sys.path.append(os.path.join(os.path.dirname(__file__), "../AppServer"))
from google.appengine.api import datastore_errors

# The location of the Cassandra binary on the local filesystem.
CASSANDRA_EXECUTABLE = cassandra_interface.CASSANDRA_INSTALL_DIR \
  + "/cassandra/bin/cassandra"

# The location on the local file system where we write the process ID
# that Cassandra runs on.
PID_FILE = "/var/appscale/appscale-cassandra.pid"

# The default port to connect to Cassandra.
CASSANDRA_PORT = 9999

# Default ZooKeeper port formatted with a colon.
ZK_PORT_WITH_COLON = ":" + str(zk.DEFAULT_PORT)

# The location on the local filesystem where we should store ZooKeeper data.
ZK_DATA_LOCATION = "/opt/appscale/zookeeper"

# The number of entities retrieved in a datastore request.
BATCH_SIZE = 100

# Log progress every time this many seconds have passed.
LOG_PROGRESS_FREQUENCY = 30

# Max sleep time for Cassandra and ZooKeeper to be up.
SLEEP_TIME = 20

# Monit watch name for Cassandra.
CASSANDRA_WATCH_NAME = "cassandra"

# Monit watch name for ZooKeeper.
ZK_WATCH_NAME = "zookeeper"

def ensure_app_is_not_running():
  """ Ensures AppScale is not running as this is an offline script. """
  logging.info("Ensure AppScale is not currently running...")
  appscale_running = subprocess.call(['service', CONTROLLER_SERVICE, 'status']) == 0
  if appscale_running:
    logging.info("AppScale is running, please shut it down and try again.")
    sys.exit(1)

def start_cassandra():
  """ Creates a monit configuration file and prompts Monit to start Cassandra. """
  logging.info("Starting Cassandra...")
  start_cmd = CASSANDRA_EXECUTABLE + " start -p " + PID_FILE
  stop_cmd = "/usr/bin/python2 " + APPSCALE_HOME + "/scripts/stop_service.py java cassandra"
  monit_app_configuration.create_config_file(CASSANDRA_WATCH_NAME, start_cmd, stop_cmd,
    ports=[CASSANDRA_PORT], upgrade_flag=True,
    match_cmd=cassandra_interface.CASSANDRA_INSTALL_DIR)
  if not monit_interface.start(CASSANDRA_WATCH_NAME):
    logger.error("Monit was unable to start Cassandra.")
    sys.exit(1)
  else:
    logger.info("Successfully started Cassandra.")

def start_zookeeper():
  """ Creates a monit configuration file and prompts Monit to start ZooKeeper. """
  logging.info("Starting ZooKeeper...")

  zk_server = "zookeeper-server"
  zookeeper_status = subprocess.call(['service', 'zookeeper', 'status']) == 0
  if zookeeper_status:
    zk_server = "zookeeper"

  if not os.path.isdir(ZK_DATA_LOCATION):
    logging.info("Initializing ZooKeeper")
    subprocess.call(['/usr/sbin/service', 'zookeeper', 'stop'])
    os.mkdir(ZK_DATA_LOCATION)
    subprocess.call(['chown -Rv zookeeper:zookeeper' , ZK_DATA_LOCATION])

  if zk_server == "zookeeper-server":
    zk_init = subprocess.call(['/usr/sbin/service', 'zookeeper', 'init']) == 0
    if not zk_init:
      logger.error("Failed to start zookeeper.")
      sys.exit(1)

  start_cmd = "/usr/sbin/service " + "zookeeper" + " start"
  stop_cmd = "/usr/sbin/service " + "zookeeper" + " stop"
  match_cmd = "org.apache.zookeeper.server.quorum.QuorumPeerMain"
  monit_app_configuration.create_config_file(ZK_WATCH_NAME, start_cmd, stop_cmd,
    ports=[zk.DEFAULT_PORT], upgrade_flag=True, match_cmd=match_cmd)

  if not monit_interface.start(ZK_WATCH_NAME):
    logger.error("Monit was unable to start ZooKeeper.")
    sys.exit(1)
  else:
    logger.info("Successfully started ZooKeeper.")

def validate_and_update_entities(datastore, ds_distributed):
  """ Validates entities in batches of BATCH_SIZE, deletes tombstoned
  entities (if any) and updates invalid entities.
  Args:
    datastore: A reference to the batch datastore interface.
    ds_distributed: A reference to the distributed datastore.
  """
  last_key = ""
  entities_checked = 0
  last_logged = time.time()
  while True:
    try:
      logger.debug("Fetching {} entities".format(BATCH_SIZE))
      entities = get_entity_batch(last_key, datastore, BATCH_SIZE)

      for entity in entities:
        process_entity(entity, datastore, ds_distributed)

      last_key = entities[-1].keys()[0]
      entities_checked += len(entities)

      if time.time() > last_logged + LOG_PROGRESS_FREQUENCY:
        logger.info("Checked {} entities".format(entities_checked))
        last_logged = time.time()

      if len(entities) < BATCH_SIZE:
        break

    except datastore_errors.Error as error:
      logger.error("Error getting and validating batch of entities: {}".format(error))
      close_connections()
      sys.exit(1)
    except AppScaleDBConnectionError as conn_error:
      logger.error("Error getting and validating batch of entities: {}".format(conn_error))
      close_connections()
      sys.exit(1)

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
  """
  logger.debug("Process entity {}".format(str(entity)))
  key = entity.keys()[0]
  one_entity = entity[key][APP_ENTITY_SCHEMA[0]]
  version = entity[key][APP_ENTITY_SCHEMA[1]]

  app_id = entity_utils.get_prefix_from_entity_key(key)
  validated_entity = ds_distributed.validated_result(app_id, entity)

  is_tombstone = validated_entity[key][APP_ENTITY_SCHEMA[0]] == datastore_server.TOMBSTONE
  if not validated_entity or is_tombstone:
    return delete_entity_from_table(key, datastore)

  if not (one_entity == validated_entity[key][APP_ENTITY_SCHEMA[0]]
      and version == validated_entity[key][APP_ENTITY_SCHEMA[1]]):
    return update_entity_in_table(key, validated_entity, datastore)

  return True

def update_entity_in_table(key, validated_entity, datastore):
  """ Updates the APP_ENTITY_TABLE with the valid entity.
  Args:
    key: A str representing the row key to update in the table.
    validated_entity: A validated entity which needs to be updated in place of
    the current entity.
    datastore: A reference to the batch datastore interface.
  """
  datastore.batch_put_entity(APP_ENTITY_TABLE, [key], APP_ENTITY_SCHEMA, validated_entity[key])

def delete_entity_from_table(key, datastore):
  """ Performs a hard delete on the APP_ENTITY_TABLE for the given row key.
  Args:
    key: A str representing the row key to delete from the table.
    datastore: A reference to the batch datastore interface.
  """
  datastore.batch_delete(APP_ENTITY_TABLE, [key])

def get_datastore():
  """ Returns a reference to the batch datastore interface. Validates where
  the <datastore>_interface.py is and adds that path to the system path.
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
  return (ZK_PORT_WITH_COLON + ",").join(zk_location_ips) + ZK_PORT_WITH_COLON

def stop_cassandra():
  """ Stops Cassandra. """
  if not monit_interface.stop(CASSANDRA_WATCH_NAME):
    logging.error("Unable to stop Cassandra.")
    sys.exit(1)
  logger.info("Monit successfully stopped Cassandra.")

def stop_zookeeper():
  """ Stops ZooKeeper."""
  if not monit_interface.stop(ZK_WATCH_NAME):
    logging.error("Unable to stop ZooKeeper.")
    sys.exit(1)
  logger.info("Monit successfully stopped ZooKeeper.")

def close_zktransaction():
  """ Closes the connection to ZKTransaction. """
  zookeeper.close()
  logger.info("Closed the connection to ZKTransaction.")

def close_connections():
  """ Close connections to Cassandra, ZooKeeper and ZKTransaction."""
  # Close connection to ZKTransaction.
  close_zktransaction()
  # Stop Cassandra and ZooKeeper.
  stop_cassandra()
  stop_zookeeper()

if __name__ == "__main__":
  args_length = len(sys.argv)
  if args_length < 2:
    sys.exit(1)

  zk_location_ips = []
  for index in range(args_length):
    # Skip first argument as that is not a ZooKeeper location.
    if index == 0:
      continue
    zk_location_ips.append(str(sys.argv[index]))

  # Set up logging.
  level = logging.INFO
  logging.basicConfig(format='%(asctime)s %(levelname)s %(filename)s:' \
    '%(lineno)s %(message)s ', level=level)
  logging.info("Logging started for datastore upgrade script.")
  logger = logging.getLogger('upgrade')
  handler = logging.FileHandler('/var/log/appscale/upgrade.log')
  formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
  handler.setFormatter(formatter)
  logger.addHandler(handler)
  logger.setLevel(logging.INFO)

  # This datastore upgrade script is to be run offline, so make sure
  # appscale is not up while running this script.
  ensure_app_is_not_running()

  # Start Cassandra and ZooKeeper.
  start_cassandra()
  start_zookeeper()

  # Sleep time for Cassandra and ZooKeeper to be started.
  time.sleep(SLEEP_TIME)

  datastore = get_datastore()
  ds_distributed, zookeeper = get_datastore_distributed(datastore, zk_location_ips)

  # Loop through entities table, fetch valid entities from journal table
  # if necessary, delete tombstoned entities and updated invalid ones.
  validate_and_update_entities(datastore, ds_distributed)
  logger.info("Updated invalid entities and deleted tombstoned entities.")

  # Drop the Journal table.
  # datastore.delete_table(JOURNAL_TABLE)
  logger.info("Successfully dropped the Journal Table.")

  # Stop Cassandra & ZooKeeper and close connection to ZKTransaction.
  close_connections()
  logger.info("Data upgrade status: SUCCESS")
