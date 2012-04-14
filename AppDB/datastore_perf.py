#Navraj Chohan
import sys
import math
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
NUM_COLUMNS = 1
def err(test_num, code):
  print "Failed for test at " + sys.argv[0] + ":" + str(test_num) \
  + " with a return of: " + str(code)
  exit(1)

def getTotal(points):
  total = 0
  for ii in points:
    total += float(ii)
  return total

def getAverage(points, total = None):
  if total == None:
    total = getTotal(points)
  if len(points) == 0:
    return 0
  return total/len(points)

def getStDev(points, average=None):
  total = 0;
  if average == None:
    average = getAverage(points)
  for ii in points:
    total += (float(ii) - average) * (float(ii) - average)
  if len(points) == 0:
    return 0
  return math.sqrt(total/len(points))


def createRandomList(number_of_columns, column_name_len):
  columns = [] 
  for ii in range(0, number_of_columns):
    columns += [hf.randomString(column_name_len)]
  return columns
columns = createRandomList(NUM_COLUMNS, 10)
data = createRandomList(NUM_COLUMNS, 100)
table_name = hf.randomString(10)
NUM_ACC = 10001
print "table= " + table_name
#print "columns= " + str(columns)
#print "data= " + str(data)
app_datastore = appscale_datastore.DatastoreFactory.getDatastore(datastore_type)
ERROR_CODES = appscale_datastore.DatastoreFactory.error_codes()
VALID_DATASTORES = appscale_datastore.DatastoreFactory.valid_datastores()
if datastore_type not in VALID_DATASTORES:
  print "Bad selection for datastore. Valid selections are:"
  print app_datastore.valid_datastores()
  exit(1)

# Prime datastore
ret = app_datastore.put_entity(table_name, "000", columns, data)
if ret[0] not in ERROR_CODES or ret[1] != "0":
  err(hf.lineno(),ret)

putArray = []
for ii in range(1, NUM_ACC):
  start = time.time()
  app_datastore.put_entity(table_name, str(ii), columns, data)
  end = time.time()
  putArray.append(end - start)
print getAverage(putArray),"\t",getStDev(putArray)
getArray = []
for ii in range(1, NUM_ACC):
  start = time.time()
  app_datastore.get_entity(table_name, str(ii), columns)
  end = time.time()
  getArray.append(end - start)
print getAverage(getArray),"\t",getStDev(getArray)
exit(0)

