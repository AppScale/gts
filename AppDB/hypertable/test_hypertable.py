import py_hypertable
import sys
import helper_functions
hf = helper_functions
columns = ["a","b","c"]
data = ["1"*300,"2"*300,"3"*300]
print data
import time
table_name = "hello"
key = "1"
print "key= " + key
print "columns= " + str(columns)
print "data= " + str(data)
print "table= " + table_name

print py_hypertable.put_entity(table_name, key, columns, data)
ret = py_hypertable.get_entity(table_name, key, columns)
print "doing a put then get"
print ret
if ret[1:] != data:
  print "ERROR doing a put then get. Data does not match"
  print "returned: " + str(ret)
  print "expected: " + str(data)
  exit(1)
else: 
  print "Success"

ret = py_hypertable.get_schema("hello")
print ret
print "checking schema:"
print ret
if ret[1:] != columns:
  print "ERROR in recieved schema"
  print "returned: " + str(ret)
  print "expected: " + str(columns)

ret = py_hypertable.__table_exist(table_name)
print "Does table we just created exist?"
print ret

ret = py_hypertable.delete_row(table_name, key)
print "Deleting the key %s"%key
print ret

ret = py_hypertable.get_entity(table_name, key, columns)
print "Trying to get deleted key:"
print ret
print "doing a put with key %s"%key
print py_hypertable.put_entity("hello", "1", ["a","b","c"], ["1","2","3"])
print "doing a get table" 
print py_hypertable.get_table("hello", ["a","b","c"])
py_hypertable.put_entity("hello", "2", ["a","b","c"], ["4","5","6"])
print "doing get table:"
print py_hypertable.get_table("hello", ["a","b","c"])
py_hypertable.put_entity("hello", "3", ["a","b","c"], ["1","2","3"])
py_hypertable.get_table("hello", ["a","b","c"])

print "TRYING TO REPLACE KEY 3"
py_hypertable.put_entity("hello", "3", ["a","b","c"], ["1","2","3"])
py_hypertable.get_table("hello", ["a","b","c"])
py_hypertable.get_row_count("hello")
ret = py_hypertable.delete_row("hello", "1")
ret = py_hypertable.delete_row("hello", "2")
ret = py_hypertable.delete_row("hello", "3")
py_hypertable.get_table("hello", ["a","b","c"])
print "Deleting table:"
print py_hypertable.delete_table("hello")
print "deleting twice:"
print py_hypertable.delete_table("hello")

table_name = u"testing_query"
print py_hypertable.delete_table(table_name)
column_names = [u"c1"]
limit = 1000
offset = 0
key = 0
startrow = u"000"
endrow = u"100"
data = u"xxx"
totalstarttime = time.time()
for ii in range(0, 101):
  key = str(ii)
  key = ("0" * (3 - len(key))) + key
  key = unicode(key)
  print "Adding key " + key
  start = time.time()
  print py_hypertable.put_entity(table_name, key, column_names, [data + key])
  stop = time.time()
  
  print "For inserting 1 record: start time: %s, end time: %s, total time: %s"%(str(start), str(stop), str(stop - start))
totalstoptime = time.time()
print "For inserting 100 records: start time: %s, end time: %s, total time: %s"%(str(totalstarttime), str(totalstoptime), str(totalstoptime - totalstarttime))
inclusive = 1
notJustKeys = 0
print "from table %s get columns %s with limits %s and offset %s, with start row %s and endrow %s"%(table_name, column_names, limit, offset, startrow, endrow)

results = py_hypertable.run_query(table_name, column_names, limit, offset, startrow, endrow, notJustKeys, inclusive, inclusive)
results = results[1:]
if len(results) != 101:
  print "ERORR: AAA Bad number of cells returned with no limit query. 101 versus %d"%len(results)

limit = 50
results = py_hypertable.run_query(table_name, column_names, limit, offset, startrow, endrow, notJustKeys, inclusive, inclusive)
results = results[1:]
if len(results) != 50:
  print "ERORR: BBB Bad number of cells returned with 50 limit query. 50 versus %d"%len(results)
limit = 25
offset = 25
results = py_hypertable.run_query(table_name, column_names, limit, offset, startrow, endrow, notJustKeys, inclusive, inclusive)
results = results[1:]
if len(results) != 25:
  print "ERORR: CCC Bad number of cells returned with 50 limit query. 50 versus %d"%len(results)
first_key = u"xxx049"
print "Number of results:"
print len(results)
if results[24] != first_key:
  print "ERORR: DDD Bad first key returned for 25 limit query with 25 offset. %s vs %s"%(first_key, results[24])

getOnlyKeys = 1
results = py_hypertable.run_query(table_name, column_names, limit, offset, startrow, endrow, getOnlyKeys, inclusive, inclusive)

#print results
startrow = "001"
endrow = "003"
limit = 1000
offset = 0
exclusive = 0
results = py_hypertable.run_query(table_name, column_names, limit, offset, startrow, endrow, getOnlyKeys, exclusive, exclusive)
results = results[1:]
if len(results) != 1:
  print "ERORR: EEE Bad number of cells returned with 0 limit query. 1 versus %d"%len(results)
last_key = u"002"
print "Number of results:"
print len(results)
if results[len(results) - 1] != last_key:
  print "ERORR: FFF Bad first key returned for 0 limit query with 0 offset. %s vs %s"%(last_key, results[len(results) - 1])

NUM_COLUMNS = 10
def err(test_num, code):
  print "Failed for test at " + sys.argv[0] + ":" + str(test_num) \
  + " with a return of: " + str(code)
  exit(1)

def createRandomList(number_of_columns, column_name_len):
  columns = [] 
  for ii in range(0, number_of_columns):
    columns += [ "a" + hf.randomString(column_name_len)]
  return columns

columns = createRandomList(NUM_COLUMNS, 10)
data = createRandomList(NUM_COLUMNS, 100)
table_name = "a" + hf.randomString(10)
key = hf.randomString(10)
print "key= " + key
#print "columns= " + str(columns)
#print "data= " + str(data)
print "table= " + table_name
app_datastore = py_hypertable
#app_datastore = appscale_datastore.Datastore(datastore_type)
ERROR_CODES = ["HT_ERROR:"]
####################
# Put on a new table
####################
print columns
ret = app_datastore.put_entity(table_name, key, columns, data)
if ret[0] not in ERROR_CODES or ret[1] != "0":
  err(hf.lineno(),ret)
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
invalid_key = "a" + hf.randomString(10)
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
invalid_table = hf.randomString(10)
ret = app_datastore.delete_row(invalid_table, key)
if ret[0] in ERROR_CODES:
  err(hf.lineno(), ret)
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
# Put on a same table
#####################
ret = app_datastore.put_entity(table_name, key, columns, data)
if ret[0] not in ERROR_CODES or ret[1] != "0":
  err(hf.lineno(),ret, ret)
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
  err(hf.lineno(),ret, ret)
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
if ret[0] not in ERROR_CODES or ret[1:] != columns:
  err(hf.lineno(), ret)
ret = app_datastore.get_schema(invalid_table)
if ret[0] in ERROR_CODES:
  err(hf.lineno(), ret)
print "SUCCESS"
