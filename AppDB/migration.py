# # A receiver for loading on migration # 
import sys 
import os 
import time 
import hashlib 
import tarfile 
import shutil
import cPickle as pickle
import SOAPpy 

import appscale_logger 
import appscale_datastore
import appscale_server
from zkappscale import zktransaction
from dbconstants import *

VALID_DATASTORE = []
MIGRATION_DATA_DIR = '/root/appscale/AppDB/migration_data'
MAX_TRIES = 10
NON_TRANS_TABLES = ['IPS___','__key__', "USERS__", "APPS__"]
logger = appscale_logger.getLogger("migration_server")
super_secret = ""
db = []
DEFAULT_PORT = 11226
bindport = DEFAULT_PORT
datastore_type = "hbase"
zoo_keeper = ""
try:
  FILE = open(SECRET_LOCATION, 'r')
  super_secret = FILE.read()
  FILE.close()
except:
  print "Temp secret set for testing"
  super_secret = 'x'

def usage():
  print "args --help for this menu"
  print "     -t for the table"

def secret_check(secret):
  return (secret == super_secret)

def md5_check(data_location, md5sum):
  m = hashlib.md5()
  file = open(data_location, 'rb')
  buffer = file.read(2 ** 20)
  while buffer:
    m.update(buffer)
    buffer = file.read(2 ** 20)
    file.close()
  return (m.hexdigest() == md5sum)

def untar_file(data_location):
  # Untar the file and return a file listing (full path)
  tar = tarfile.open(data_location)
  try:
    os.mkdir(MIGRATION_DATA_DIR)
  except:
    pass
  os.chdir(MIGRATION_DATA_DIR)
  tar.extractall()
  dirlist = []
  for ii in tar.getmembers():
    dirlist.append(ii.name)
  tar.close()
  #dirlist = os.listdir(MIGRATION_DATA_DIR) 
  os.chdir('../')
  return dirlist 

def remove_tar(data_location):
  os.remove(data_location)

def remove_data_dir():
  shutil.rmtree(MIGRATION_DATA_DIR)

def get_file_buffer(dataFile):
  os.chdir(MIGRATION_DATA_DIR)
  FILE = open(dataFile)
  buf = FILE.read()
  FILE.close()
  os.chdir('../')
  return buf

def get_dictionary(buf):
  return pickle.loads(buf)

def is_non_trans_table(table_name):
  if "JOURNAL____" in table_name:
    return True
  elif table_name in NON_TRANS_TABLES:
    return True
  elif "___notrans_" in table_name:
    return True
  else:
    return False 

# This is only for transaction tables
#TODO handle namespaces
def get_root_key_table_appid(key):
  toks = key.split('/')
  appid = toks[0].split('___')[0]
  table = toks[0]
  root_key = '/'.join(toks[1:])
  return [root_key, table, appid]

def get_table(key):
  return key.split('/')[0]

def txn_store(key, values):
  global zoo_keeper
  tries = 1
  while tries < MAX_TRIES:
    try:
      root_key, table, appid = get_root_key_table_appid(key)
      handle = zoo_keeper.get_transaction_id(appid)
      gotLock = zoo_keeper.acquireLock(appid, handle, root_key)
      # Make sure there is no other entity already there
      get_res = db.get_entity(table, key, ENTITY_TABLE_SCHEMA[0])
      if get_res:
        put_res = db.put_entity(table, key, ENTITY_TABLE_SCHEMA,
                                           values)
      else:
        print "Entity already had %s, so skipping"%str(res) 
      zoo_keeper.releaseLock(appid, handle)
      break
    except Exception, e:
      print "Exception while trying to store entitiy: %s"%str(e)
      print "Sleeping for " + str(tries ** 2) 
      time.sleep(tries ** 2)
      tries += 1
      zoo_keeper.releaseLock(appid, handle)
  return tries < MAX_TRIES

def nontxn_store(key, fields, values):
  tries = 1
  table = get_table(key)
  while tries < MAX_TRIES:
    try:
      get_res = db.get_entity(table, key, fields)
      if get_res[0] != 'DB_ERROR:':
        put_res = db.put_entity(table, key, fields, values)
      else:
        print "Entity already had %s, so skipping"%str(get_res) 
      
      return True
    except Exception, e:
      print "Exception while trying to store entitiy: %s"%str(e)
      print "Sleeping for " + str(tries ** 2) 
      time.sleep(tries ** 2)
      tries += 1
  return tries < MAX_TRIES

def dict_transform(kv_dict):
  trans_kv = {}
  nontrans_kv = {}
  for entry in kv_dict['cols']:
    ordict = entry[1]  # ordered dictionary
    key = entry[0]
    table = get_table(key)
    if not is_non_trans_table(table):
      vlist = [ordict[ENTITY_TABLE_SCHEMA[0]], ordict[ENTITY_TABLE_SCHEMA[1]]]
      trans_kv[key] = vlist
    else:
      schema_list = []
      value_list = []
      for column in ordict:
        schema_list.append(column)
        value_list.append(ordict[column])
        nontrans_kv[key] = (schema_list, value_list)
  return trans_kv, nontrans_kv

def load_nontrans(diction):
  for ii in diction:
    schema = diction[ii][0]
    values = diction[ii][1]
    nontxn_store(ii, schema, values)

def load_trans(diction):
  for key in diction:
    values = diction[key] 
    txn_store(key, values)

def setup_datastore(datastore_type):
  global db
  db = appscale_datastore.DatastoreFactory.getDatastore(datastore_type)
  ERROR_CODES = appscale_datastore.DatastoreFactory.error_codes()
  VALID_DATASTORES = appscale_datastore.DatastoreFactory.valid_datastores()
  if not datastore_type in VALID_DATASTORES:
    print "Invalid type for datastore type: " + datastore_type
    print "valid datastores include:"
    print VALID_DATASTORES
    usage()
    exit(1)

def setup_zookeeper(zk_locations):
  global zoo_keeper
  zoo_keeper = zktransaction.ZKTransaction(zk_locations)

def get_zk_locations():
  #TODO actually look up the locations
  return "localhost:2181" 

# Eventually want this to be asynch with a callback
def start_migration(secret, data_location, md5):
  if not secret_check(secret): return "Permission denied"
  if not md5_check(data_location, md5): return "Bad CRC"
  listing = untar_file(data_location) 
  if not listing: return "Unable to untar file or no files found"

  trans_dict = {}
  nontrans_dict = {}

  for ii in listing:
    buf = get_file_buffer(ii)
    kv_dict = get_dictionary(buf)
    trans_dict, nontrans_dict = dict_transform(kv_dict) 
  load_nontrans(nontrans_dict)
  load_trans(trans_dict)

  return True 

if __name__ == "__main__":
  for ii in range(1,len(sys.argv)):
    if sys.argv[ii] in ("-h", "--help"):
      usage()
      sys.exit()
    elif sys.argv[ii] in ('-t', "--type"):
      print "setting datastore type to ",sys.argv[ii+1]
      datastore_type = sys.argv[ii + 1]
      ii += 1


  setup_datastore(datastore_type)

  zk_locations = get_zk_locations()
  setup_zookeeper(zk_locations) 

  ip = "0.0.0.0"

  server = SOAPpy.SOAPServer((ip,bindport))
  server.registerFunction(start_migration)

  while 1:
    try:
      # Run Server
      server.serve_forever()
    except SSL.SSLError:
      pass


