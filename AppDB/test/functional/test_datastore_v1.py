#Navraj Chohan
import sys
import appscale_datastore
import helper_functions
import os 
import time
hf = helper_functions
if "LOCAL_DB_IP" not in os.environ:
  os.environ["LOCAL_DB_IP"] = "localhost"

datastore_type = "xxx"
def usage():
  print " -t for type of datastore"
for ii in range(1,len(sys.argv)):
  if sys.argv[ii] in ("-h", "--help"):
    print "help menu:"
    usage()
    sys.exit()
  elif sys.argv[ii] in ('-a', "--apps"):
    print "apps location set to ",sys.argv[ii+ 1]
    app_location = sys.argv[ii + 1]
    ii += 1
  elif sys.argv[ii] in ('-t', "--type"):
    print "setting datastore type to ",sys.argv[ii+1]
    datastore_type = sys.argv[ii + 1]
    ii += 1
  else:
    pass
NUM_COLUMNS = 10
def err(test_num, code):
  print "Failed for test at " + sys.argv[0] + ":" + str(test_num) \
  + " with a return of: " + str(code)
  exit(1)

def createRandomList(number_of_columns, column_name_len):
  columns = [] 
  for ii in range(0, number_of_columns):
    columns += [hf.randomString(column_name_len)]
  return columns
start = time.time()
columns = createRandomList(NUM_COLUMNS, 10)
data = createRandomList(NUM_COLUMNS, 100)
table_name = hf.randomString(10)
key = hf.randomString(10)
print "key= " + key
#print "columns= " + str(columns)
#print "data= " + str(data)
print "table= " + table_name
app_datastore = appscale_datastore.DatastoreFactory.getDatastore(datastore_type)
ERROR_CODES = appscale_datastore.DatastoreFactory.error_codes()
VALID_DATASTORES = appscale_datastore.DatastoreFactory.valid_datastores()
if datastore_type not in VALID_DATASTORES:
  print "Bad selection for datastore. Valid selections are:"
  print app_datastore.valid_datastores()
  exit(1)
####################
# Put on a new table
####################
#print columns
ret = app_datastore.put_entity(table_name, key, columns, data)
if ret[0] not in ERROR_CODES or ret[1] != "0":
  err(hf.lineno(),ret)

# And do a partial put on only one column
ret = app_datastore.put_entity(table_name, key, columns[:1], data[:1])
if ret[0] not in ERROR_CODES or ret[1] != "0":
  err(hf.lineno(),ret)
#
####################
# Get on all columns
####################
print columns
ret = app_datastore.get_entity(table_name, key, columns)
if ret[0] not in ERROR_CODES or ret[1:] != data:
  err(hf.lineno(),ret)

###########################################
# Get on a random column and check the data
###########################################
import random
for ii in range(0, NUM_COLUMNS):
  rand = int((random.random() * 1000 ) % NUM_COLUMNS)
  ret = app_datastore.get_entity(table_name, key, [columns[rand]])
  if ret[0] not in ERROR_CODES or ret[1] != data[rand]:
    err(hf.lineno(),ret)
#################################################
# Get random data from two columns and check data
#################################################
for ii in range(0, NUM_COLUMNS):
  rand = int((random.random() * 1000) % NUM_COLUMNS)
  rand2 = int((random.random() * 1000) % NUM_COLUMNS)
  ret = app_datastore.get_entity(table_name, key, \
    [columns[rand],columns[rand2]])
  if ret[0] not in ERROR_CODES or ret[1] != data[rand] \
    or ret[2] != data[rand2]:
    err(hf.lineno(),ret) 
#####################################
# Get and a delete on invalid row key
#####################################
invalid_key = hf.randomString(10)
ret = app_datastore.get_entity(table_name, invalid_key, \
  columns)
if ret[0] in ERROR_CODES:
  err(hf.lineno(),ret)

ret = app_datastore.delete_row(table_name, invalid_key)
if ret[0] not in ERROR_CODES:
  err(hf.lineno(),ret)
###########################
# Get just the first column
###########################
ret = app_datastore.get_entity(table_name, key, [columns[0]])
if ret[0] not in ERROR_CODES or ret[1] != data[0]:
  print ret
  err(hf.lineno(),ret)
###########################
# Put on new row
###########################
data2 = createRandomList(NUM_COLUMNS, 100)
key2 = hf.randomString(10)
ret = app_datastore.put_entity(table_name, key2, columns, data2)
if ret[0] not in ERROR_CODES or ret[1] != "0":
  err(hf.lineno(),ret)
############################
# Get on just added row
############################
ret = app_datastore.get_entity(table_name, key2, columns)
if ret[0] not in ERROR_CODES or ret[1:] != data2 or ret[1:] == data:
  err(hf.lineno(),ret)
#########################################
# Delete the new row once, and then again
#########################################
ret = app_datastore.delete_row(table_name, key2)
if ret[0] not in ERROR_CODES:
  err(hf.lineno(),ret)
ret = app_datastore.delete_row(table_name, key2)
if ret[0] not in ERROR_CODES:
  err(hf.lineno(),ret)
#################################################
# Get and a delete on a table that does not exist
#################################################
# There is too much overhead in checking to see if the table exists
# for cassandra
invalid_table = hf.randomString(10)
#ret = app_datastore.delete_row(invalid_table, key)
#if ret[0] in ERROR_CODES:
#  err(hf.lineno(), ret)
ret = app_datastore.get_entity(invalid_table, key, columns)
if ret[0] in ERROR_CODES:
  err(hf.lineno(), ret)

######################
# Delete a table twice
######################
ret = app_datastore.delete_table(table_name)
if ret[0] not in ERROR_CODES:
  err(hf.lineno(), ret)
ret = app_datastore.delete_table(table_name)
if ret[0] in ERROR_CODES:
  err(hf.lineno(), ret)
#####################
# Put on a new table
#####################
ret = app_datastore.put_entity(table_name, key, columns, data)
if ret[0] not in ERROR_CODES or ret[1] != "0":
  err(hf.lineno(),ret)
####################
# Get on all columns
####################
ret = app_datastore.get_entity(table_name, key, columns)
if ret[0] not in ERROR_CODES or ret[1:] != data:
  err(hf.lineno(),ret)
##########################
# Put on same row new data 
##########################
data = createRandomList(NUM_COLUMNS, 10000)
ret = app_datastore.put_entity(table_name, key, columns, data)
if ret[0] not in ERROR_CODES or ret[1] != "0":
  err(hf.lineno(),ret)
####################
# Get on all columns
####################
ret = app_datastore.get_entity(table_name, key, columns)
if ret[0] not in ERROR_CODES or ret[1:] != data:
  err(hf.lineno(),ret)
####################################
# Do a put on first and last columns
####################################
data1 = hf.randomString(10)
data2 = hf.randomString(10)
ret = app_datastore.put_entity(table_name, key, [columns[0], \
columns[NUM_COLUMNS - 1]], [data1, data2])
if ret[0] not in ERROR_CODES or ret[1] != "0":
  err(hf.lineno(), ret)
ret = app_datastore.get_entity(table_name, key, [columns[0], \
columns[NUM_COLUMNS - 1]])
if ret[0] not in ERROR_CODES or ret[1] != data1 or ret[2] != data2:
  err(hf.lineno(), ret)
#######################################################
# Get schema on a table that exist, and one that doesnt
#######################################################
ret = app_datastore.get_schema(table_name)
if ret[0] not in ERROR_CODES or (ret[1:]).sort() != columns.sort():
  print "ret[1:]:",ret[1:].sort
  print "columns:",columns.sort
  err(hf.lineno(), ret)
ret = app_datastore.get_schema(invalid_table)
if ret[0] in ERROR_CODES:
  err(hf.lineno(), ret)
################################################
# Get data from a table that does not exist
# Should return an empty list
################################################
ret = app_datastore.get_table(invalid_table, columns)
if ret[0] not in ERROR_CODES and len(ret) != 1:
  err(hf.lineno(), ret)

###############################################
# Store two keys with keys lexigraphically built from the table name
# Use get_table to retrieve them
###############################################
key1 = table_name + "1"
key2 = table_name + "2"
ret = app_datastore.put_entity(table_name, key1, columns, data)
if ret[0] not in ERROR_CODES or ret[1] != "0":
  err(hf.lineno(),ret)
ret = app_datastore.put_entity(table_name, key2, columns, data)
if ret[0] not in ERROR_CODES or ret[1] != "0":
  err(hf.lineno(),ret)
ret = app_datastore.get_table(table_name, columns)
if ret[0] not in ERROR_CODES or len(ret) < (2 * len(columns)):
  err(hf.lineno(), ret)

print "SUCCESS for single threaded tests"
stop =time.time()
print "Time Taken:",
print stop - start
print "Running concurrent test..."
############################################
# Multithreaded test
# Make sure the db can handle concurrent puts
###########################################
from threading import Thread
class putThread(Thread):
  def __init__(self, table, key, columns, data):
    Thread.__init__(self)
    self.table = table
    self.key = key
    self.columns = columns
    self.data = data
    self.status = "Bad"
  def run(self):
    ret = app_datastore.put_entity(self.table, self.key, self.columns, self.data)
    if ret[0] not in ERROR_CODES or ret[1] != "0":
      self.status = "Bad"
    else:
      self.status = "Good"

data = [10000*"x",10000*"zzz"]
columns = ["1","2"]
table = "concurrent_test"
allThreads = []
for ii in range(0, 1000):
  allThreads.append(putThread(table, str(ii), columns, data))

import time
start = time.time()
for ii in allThreads:
  ii.start() 

good = 0
bad = 0
for ii in allThreads:
  ii.join()
  if ii.status == "Good":
    good += 1
  if ii.status == "Bad":
    bad += 1
stop = time.time()
if good != len(allThreads):
  print "Concurrent thread test experienced failures:"
  print "Successful threads: %d"%good
  print "Failed threads: %d"%bad
else:
  print "SUCCESS"
print "Time taken:",
print stop - start  
