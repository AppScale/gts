import py_cassandra

py_cassandra = py_cassandra.DatastoreProxy()

columns = ["a","b","c"]
data = ["1","2","3"]
table_name = "hello"
key = "1"
print "key= " + key
print "columns= " + str(columns)
print "data= " + str(data)
print "table= " + table_name
#print py_cassandra.put_entity("__hi__", key, columns, data)
#print py_cassandra.put_entity("__hah__", key, columns, data)
#exit(0)
print py_cassandra.put_entity(table_name, key, columns, data)
ret = py_cassandra.get_entity(table_name, key, columns)
print "doing a put then get"
print ret
if ret[1:] != data:
  print "ERROR doing a put then get. Data does not match"
  print "returned: " + str(ret)
  print "expected: " + str(data)
  exit(1)
else: 
  print "Success"

ret = py_cassandra.get_schema("hello")
print ret
print "checking schema:"
print ret
if ret[1:] != columns:
  print "ERROR in recieved schema"
  print "returned: " + str(ret)
  print "expected: " + str(columns)

ret = py_cassandra.delete_row(table_name, key)
print "Deleting the key %s"%key
print ret

ret = py_cassandra.get_entity(table_name, key, columns)
print "Trying to get deleted key:"
print ret
print "doing a put with key %s"%key
print py_cassandra.put_entity("hello", "1", ["a","b","c"], ["1","2","3"])
print "doing a get table" 
print py_cassandra.get_table("hello", ["a","b","c"])
py_cassandra.put_entity("hello", "2", ["a","b","c"], ["4","5","6"])
print "doing get table:"
print py_cassandra.get_table("hello", ["a","b","c"])
py_cassandra.put_entity("hello", "3", ["a","b","c"], ["1","2","3"])
py_cassandra.get_table("hello", ["a","b","c"])

print "TRYING TO REPLACE KEY 3"
py_cassandra.put_entity("hello", "3", ["a","b","c"], ["1","2","3"])
print "TRYING TO REPLACE KEY 3"
py_cassandra.get_table("hello", ["a","b","c"])
print "TRYING TO REPLACE KEY 3"
ret = py_cassandra.delete_row("hello", "1")
print "TRYING TO REPLACE KEY 3"
ret = py_cassandra.delete_row("hello", "2")
print "TRYING TO REPLACE KEY 3"
ret = py_cassandra.delete_row("hello", "3")
print "TRYING TO REPLACE KEY 3"
py_cassandra.get_table("hello", ["a","b","c"])
print "Deleting table:"
print py_cassandra.delete_table("hello")
print "deleting twice:"
print py_cassandra.delete_table("hello")

table_name = u"testing_query"
print py_cassandra.delete_table(table_name)
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
  print py_cassandra.put_entity(table_name, key, column_names, [data + key])
inclusive = 1
notJustKeys = 0
print "SUCCESS"

