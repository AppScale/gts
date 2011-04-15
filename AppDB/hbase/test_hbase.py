import py_hbase

py_hbase = py_hbase.DatastoreProxy()

columns = ["a","b","c"]
data = ["1","2","3"]
table_name = "hello"
key = "1"
print "key= " + key
print "columns= " + str(columns)
print "data= " + str(data)
print "table= " + table_name

print py_hbase.put_entity(table_name, key, columns, data)
ret = py_hbase.get_entity(table_name, key, columns)
print "doing a put then get"
print ret
if ret[1:] != data:
  print "ERROR doing a put then get. Data does not match"
  print "returned: " + str(ret)
  print "expected: " + str(data)
  exit(1)
else: 
  print "Success"

ret = py_hbase.get_schema("hello")
print ret
print "checking schema:"
print ret
if ret[1:] != columns:
  print "ERROR in recieved schema"
  print "returned: " + str(ret)
  print "expected: " + str(columns)

ret = py_hbase.delete_row(table_name, key)
print "Deleting the key %s"%key
print ret

ret = py_hbase.get_entity(table_name, key, columns)
print "Trying to get deleted key:"
print ret
print "doing a put with key %s"%key
print py_hbase.put_entity("hello", "1", ["a","b","c"], ["1","2","3"])
print "doing a get table" 
print py_hbase.get_table("hello", ["a","b","c"])
py_hbase.put_entity("hello", "2", ["a","b","c"], ["4","5","6"])
print "doing get table:"
print py_hbase.get_table("hello", ["a","b","c"])
py_hbase.put_entity("hello", "3", ["a","b","c"], ["1","2","3"])
py_hbase.get_table("hello", ["a","b","c"])

print "TRYING TO REPLACE KEY 3"
py_hbase.put_entity("hello", "3", ["a","b","c"], ["1","2","3"])
print "TRYING TO REPLACE KEY 3"
py_hbase.get_table("hello", ["a","b","c"])
print "TRYING TO REPLACE KEY 3"
py_hbase.get_row_count("hello")
print "TRYING TO REPLACE KEY 3"
ret = py_hbase.delete_row("hello", "1")
print "TRYING TO REPLACE KEY 3"
ret = py_hbase.delete_row("hello", "2")
print "TRYING TO REPLACE KEY 3"
ret = py_hbase.delete_row("hello", "3")
print "TRYING TO REPLACE KEY 3"
py_hbase.get_table("hello", ["a","b","c"])
print "Deleting table:"
print py_hbase.delete_table("hello")
print "deleting twice:"
print py_hbase.delete_table("hello")

table_name = u"testing_query"
print py_hbase.delete_table(table_name)
column_names = [u"c1"]
limit = 1000
offset = 0
key = 0
startrow = u"000"
endrow = u"100"
data = u"xxx"
for ii in range(0, 101):
  key = str(ii)
  key = ("0" * (3 - len(key))) + key
  key = unicode(key)
  print "Adding key " + key
  print py_hbase.put_entity(table_name, key, column_names, [data + key])
inclusive = 1
notJustKeys = 0
print "from table %s get columns %s with limits %s and offset %s, with start row %s and endrow %s"%(table_name, column_names, limit, offset, startrow, endrow)

results = py_hbase.run_query(table_name, column_names, limit, offset, startrow, endrow, notJustKeys, inclusive, inclusive)
results = results[1:]
if len(results) != 101:
  print "ERORR: AAA Bad number of cells returned with no limit query. 101 versus %d"%len(results)

limit = 50
results = py_hbase.run_query(table_name, column_names, limit, offset, startrow, endrow, notJustKeys, inclusive, inclusive)
results = results[1:]
if len(results) != 50:
  print "ERORR: BBB Bad number of cells returned with 50 limit query. 50 versus %d"%len(results)
limit = 25
offset = 25
results = py_hbase.run_query(table_name, column_names, limit, offset, startrow, endrow, notJustKeys, inclusive, inclusive)
results = results[1:]
if len(results) != 25:
  print "ERORR: CCC Bad number of cells returned with 50 limit query. 50 versus %d"%len(results)
first_key = u"xxx049"
print "Number of results:"
print len(results)
if results[24] != first_key:
  print "ERORR: DDD Bad first key returned for 25 limit query with 25 offset. %s vs %s"%(first_key, results[24])

getOnlyKeys = 1
results = py_hbase.run_query(table_name, column_names, limit, offset, startrow, endrow, getOnlyKeys, inclusive, inclusive)

#print results
startrow = "001"
endrow = "003"
limit = 1000
offset = 0
exclusive = 0
results = py_hbase.run_query(table_name, column_names, limit, offset, startrow, endrow, getOnlyKeys, exclusive, exclusive)
results = results[1:]
if len(results) != 1:
  print "ERORR: EEE Bad number of cells returned with 0 limit query. 1 versus %d"%len(results)
last_key = u"002"
print "Number of results:"
print len(results)
if results[len(results) - 1] != last_key:
  print "ERORR: FFF Bad first key returned for 0 limit query with 0 offset. %s vs %s"%(last_key, results[len(results) - 1])

