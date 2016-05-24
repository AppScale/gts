import json
import os
import subprocess
import sys
import time

sys.path.append(os.path.join(os.path.dirname(__file__), '../lib'))
import appscale_info
from constants import CONTROLLER_SERVICE
from constants import APPSCALE_HOME
import monit_interface

sys.path.append(os.path.join(os.path.dirname(__file__), '../AppDB'))
import appscale_datastore_batch
import datastore_server
from dbconstants import *
from zkappscale import zktransaction as zk

sys.path.append(os.path.join(os.path.dirname(__file__), "../AppServer"))
from google.appengine.datastore import entity_pb

# The location on the local filesystem where Cassandra is installed.
CASSANDRA_DIR = "/opt/cassandra"

# The location of the Cassandra binary on the local filesystem.
CASSANDRA_EXECUTABLE = CASSANDRA_DIR + "/cassandra/bin/cassandra"

PID_FILE = "/var/appscale/appscale-cassandra.pid"

# The default port to connect to ZooKeeper.
ZK_PORT = ":2181"

# The location on the local filesystem where we should store ZooKeeper data.
ZK_DATA_LOCATION = "/opt/appscale/zookeeper"

# The maximum number of entities to be returned from the query.
_MAX_ENTITIES = 1000000

def ensure_app_is_not_running():
    """ Ensures AppScale is not running as this is an offline script. """
    print ("Ensure AppScale is not currently running...")
    appscale_running = subprocess.call(['service', CONTROLLER_SERVICE, 'status']) == 0
    if appscale_running:
        print ("AppScale is running, please shut it down and try again.")
        exit(1)

def start_cassandra():
    """ Creates a monit configuration file and prompts Monit to start Cassandra. """
    print ("Starting Cassandra...")
    watch = "cassandra"
    start_cmd = CASSANDRA_EXECUTABLE + " start -p " + PID_FILE
    stop_cmd = "/usr/bin/python2 " + APPSCALE_HOME + "/scripts/stop_service.py java cassandra"
    monit_interface.create_monit_config_file(watch, start_cmd, stop_cmd,
        ports=[9999], match_cmd=CASSANDRA_DIR)
    if not monit_interface.start(watch):
        print ("Unable to start Cassandra.")
        exit(1)
    else:
        print ("Successfully started Cassandra.")

def start_zookeeper():
    """ Creates a monit configuration file and prompts Monit to start ZooKeeper. """
    print ("Starting ZooKeeper...")
    os.system("rm -rfv /var/lib/zookeeper")
    os.system("rm -rfv {}".format(ZK_DATA_LOCATION))
    zk_server = "zookeeper-server"
    if os.system("service --status-all|grep zookeeper$"):
        zk_server = "zookeeper"

    if not os.path.isdir(ZK_DATA_LOCATION):
        print ("Initializing ZooKeeper")
        os.system("/usr/sbin/service " + "zookeeper" + " stop")
        os.system("mkdir -pv " + ZK_DATA_LOCATION)
        os.system("chown -Rv zookeeper:zookeeper " + ZK_DATA_LOCATION)

        if zk_server == "zookeeper-server":
            if not os.system("/usr/sbin/service " + "zookeeper" + " init"):
                print ("Failed to start zookeeper!")
                exit(1)
    os.system("ln -sfv /etc/zookeeper/conf/myid " + ZK_DATA_LOCATION + "/myid")
    watch = "zookeeper"
    start_cmd = "/usr/sbin/service " + "zookeeper" + " start"
    stop_cmd = "/usr/sbin/service " + "zookeeper" + " stop"
    match_cmd = "org.apache.zookeeper.server.quorum.QuorumPeerMain"
    monit_interface.create_monit_config_file(watch, start_cmd, stop_cmd,
        ports=[2181], match_cmd=match_cmd)
    if not monit_interface.start(watch):
        print ("Unable to start ZooKeeper")
        exit(1)
    else:
        print ("Successfully started ZooKeeper")

def validate_and_update_entities(datastore, ds_distributed):
    """ Returns the SOAP server accessor to deal with application and users.
    Args:
        datastore: A reference to the batch datastore interface.
    Returns:
        A soap server accessor.
    """
    # Fetch all entities from the APP_ENTITY_TABLE.
    try:
        current_entities = datastore.range_query(APP_ENTITY_TABLE, APP_ENTITY_SCHEMA, "", "", _MAX_ENTITIES)
    except Exception as ex:
        print ("Exception on range query: {}".format(str(ex)))
        exit(1)

    # Remove the tombstoned entities from the list.
    tombstoneless_entities = ds_distributed.remove_tombstoned_entities(current_entities)
    app_ids = get_app_ids_from_entities(tombstoneless_entities)
    entities_to_validate  = tombstoneless_entities

    # Validate the entities grouped by app id.
    for app_id in app_ids:
        validated_entities_for_app = ds_distributed.validated_list_result(app_id, entities_to_validate)
        entities_to_validate = validated_entities_for_app
    return current_entities, tombstoneless_entities, validated_entities_for_app

def delete_tombstoned_entities_from_table(datastore, current_entities, validated_entities):
    """ Deletes the set of rows corresponding to entity keys which have
    tombstoned values from the APP_ENTITY_TABLE.
    Args:
        datastore: A reference to the batch datastore interface.
        current_entities: A list of entities currently in the APP_ENTITY_TABLE.
        validated_entities: A list of validated entities to compare from.
    """
    valid_entity_keys = get_valid_entity_keys(validated_entities)
    invalid_entity_keys = compare_and_get_invalid_keys(current_entities, valid_entity_keys)
    try:
        datastore.batch_delete(APP_ENTITY_TABLE, invalid_entity_keys)
        print ("Batch delete was successful")
    except AppScaleDBConnectionError as error:
        print("Exception on batch delete: {}".format(str(error)))
        exit(1)

def update_entities_table(datastore, entities, validated_entities):
    """ Updates the APP_ENTITY_TABLE with valid entities if any.
    Args:
        ddatastore: A reference to the batch datastore interface.
        entities: A list of tombstonedless entities.
        validated_entities: A list of validated entities to compare from.
    """
    row_keys_to_update = []
    cell_values_to_update = {}
    for valid_entity in validated_entities:
        valid_entity_key = valid_entity.keys()[0]
        for entity in entities:
            entity_key = entity.keys()[0]
            if not valid_entity_key == entity_key:
                continue

            if is_entity_same(entity,entity_key, valid_entity) and is_txn_id_same(entity, entity_key, valid_entity):
                continue

            if not entity_key in row_keys_to_update:
                row_keys_to_update.append(entity_key)
                cell_value = {}
                cell_value[APP_ENTITY_SCHEMA[0]] = valid_entity[entity_key][APP_ENTITY_SCHEMA[0]]
                cell_value[APP_ENTITY_SCHEMA[1]] = valid_entity[entity_key][APP_ENTITY_SCHEMA[1]]
                cell_values_to_update[entity_key] = cell_value
    try:
        datastore.batch_put_entity(APP_ENTITY_TABLE, row_keys_to_update, APP_ENTITY_SCHEMA, cell_values_to_update)
        print("Batch put entities was successful")
    except  AppScaleDBConnectionError as error:
        print("Exception on batch put entity: {}".format(str(error)))
        exit(1)

def is_txn_id_same(entity, key, valid_entity):
    """ Compares if the transaction id is the same for the current and
    validated entity.
    Args:
        entity: Current tombstonedless entity.
        key: A key to look for in the validated entity.
        valid_entity: A validated entity to compare with.
    Returns:
        True if transaction id is the same.
    """
    return entity[key][APP_ENTITY_SCHEMA[1]] == valid_entity[key][APP_ENTITY_SCHEMA[1]]

def is_entity_same(entity, key, valid_entity):
    """ Compares if the transaction id is the same for the current and
        validated entity.
    Args:
        entity: Current tombstonedless entity.
        key: A key to look for in the validated entity.
        valid_entity: A validated entity to compare with.
    Returns:
        True is the encoded entity is the same.
    """
    return entity[key][APP_ENTITY_SCHEMA[0]] == valid_entity[key][APP_ENTITY_SCHEMA[0]]

def compare_and_get_invalid_keys(current_entities, valid_entity_keys):
    """ Looks for the current entities keys in a list of valid entity keys
    and returns the invalid keys.
    Args:
        current_entities: A list of entities currently in APP_ENTITY_TABLE.
        key: A key to look for in the validated entity.
        valid_entity_keys: A list valid entity keys to compare from.
    Returns:
        A list of invalid entity keys
    """
    invalid_entity_keys = []
    for entity in current_entities:
        key = entity.keys()[0]
        if key not in valid_entity_keys:
            if key not in invalid_entity_keys:
                invalid_entity_keys.append(key)
    return invalid_entity_keys

def get_valid_entity_keys(validated_entities):
    """ Loops through the validated entities and creates a list of valid
    entity keys.
    Args:
        validated_entities: A list of validated entities.
    Returns:
        A list of valid entity keys.
    """
    valid_row_keys = []
    # Get all the keys from the validated entities
    for valid_entity in validated_entities:
        valid_key = valid_entity.keys()[0]
        if valid_key not in valid_row_keys:
            valid_row_keys.append(valid_key)
    return valid_row_keys

def get_zk_locations_string(zk_location_ips):
    """ Generates a ZooKeeper IP locations string.
    Args:
        zk_location_ips: A list of ZooKeeper IP locations.
    Returns:
        A string of ZooKeeper IP locations
    """
    return (ZK_PORT + ",").join(zk_location_ips) + ZK_PORT

def get_app_ids_from_entities(entities_without_tombstoned_values):
    app_ids = []
    for entity in entities_without_tombstoned_values:
        key = entity.keys()[0]
        one_entity = entity[key][APP_ENTITY_SCHEMA[0]]
        entity_proto = entity_pb.EntityProto(one_entity)
        app_id = entity_proto.key().app()
        if not app_id in app_ids:
            app_ids.append(app_id)
    return app_ids

def get_datastore():
    """ Returns a reference to the batch datastore interface. Validates where
        the <datastore>_interface.py is and adds that path to
        the system path.
    """
    db_info = appscale_info.get_db_info()
    db_type = db_info[':table']
    datastore_batch = appscale_datastore_batch.DatastoreFactory.getDatastore(db_type)
    return datastore_batch

def get_datastore_distributed(datastore, zk_location_ips):
    """ Returns a reference to the batch datastore interface. Validates where
        the <datastore>_interface.py is and adds that path to
        the system path.
    Args:
        datastore: A reference to the batch datastore interface.
        zk_location_ips: A list of ZooKeeper location ips.
    """
    zookeeper_locations = get_zk_locations_string(zk_location_ips)
    zookeeper = zk.ZKTransaction(host=zookeeper_locations)
    datastore_distributed = datastore_server.DatastoreDistributed(datastore, zookeeper=zookeeper)
    return datastore_distributed

if __name__ == "__main__":
    total = len(sys.argv)
    if not total > 1:
        exit(1)

    zk_location_ips = []
    for i in range(total):
        # Skip first argument as that is not a ZooKeeper location.
        if i == 0:
            continue
        zk_location_ips.append(str(sys.argv[i]))

    # This datastore upgrade script is to be run offline, so make sure
    # appscale is not up while running this script.
    ensure_app_is_not_running()

    # Start Cassandra and ZooKeeper.
    start_cassandra()
    start_zookeeper()

    # Sleep time for Cassandra and ZooKeeper to be started.
    time.sleep(20)

    # Loop through entities table and fetch valid entities from journal
    # table if necessary.
    datastore = get_datastore()
    ds_distributed = get_datastore_distributed(datastore, zk_location_ips)
    current_entities, tombstoneless_entities , validated_entities = \
        validate_and_update_entities(datastore, ds_distributed)

    # Delete the tombstoned entities from the APP_ENTITY_TABLE.
    delete_tombstoned_entities_from_table(datastore, current_entities, validated_entities)

    # Update and replace each non valid entity with the right value from the journal.
    update_entities_table(datastore, tombstoneless_entities, validated_entities)









