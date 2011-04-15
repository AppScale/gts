import py_hypertable
py_hypertable = py_hypertable.DatastoreProxy()
columns = ["a","b","c"]
data = ["1","2","3"]
table_name = "hello"
key = "1"
print "key= " + key
print "columns= " + str(columns)
print "data= " + str(data)
print "table= " + table_name
print "PUT"
print py_hypertable.put_entity(table_name, key, columns, data)
print "GET"
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

#ret = py_hypertable.__table_exist(table_name)
#print "Does table we just created exist?"
#print ret

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
