import py_mongodb
columns = ["a","b","c"]
data = ["1","2","3"]
table_name = "helloRaj"
key = "1"
print "key= " + key
print "columns= " + str(columns)
print "data= " + str(data)
print "table= " + table_name

print py_mongodb.put_entity(table_name, key, columns, data)
ret = py_mongodb.get_entity(table_name, key, columns)
print "doing a put then get"
print ret
if ret[1:] != data:
  print "ERROR doing a put then get. Data does not match"
  print "returned: " + str(ret)
  print "expected: " + str(data)
  exit(1)
else: 
  print "Success"

ret = py_mongodb.get_schema("helloRaj")
print ret
print "checking schema:"
print ret
if ret[1:] != columns:
  print "ERROR in recieved schema"
  print "returned: " + str(ret)
  print "expected: " + str(columns)


ret = py_mongodb.delete_row(table_name, key)
print "Deleting the key %s"%key
print ret

ret = py_mongodb.get_entity(table_name, key, columns)
print "Trying to get deleted key:"
print ret
print "doing a put with key %s"%key
print py_mongodb.put_entity("helloRaj", "1", ["a","b","c"], ["1","2","3"])
print "doing a get table" 
print py_mongodb.get_table("helloRaj", ["a","b","c"])
py_mongodb.put_entity("helloRaj", "2", ["a","b","c"], ["4","5","6"])
print "doing get table:"
print py_mongodb.get_table("helloRaj", ["a","b","c"])
py_mongodb.put_entity("helloRaj", "3", ["a","b","c"], ["1","2","3"])
py_mongodb.get_table("helloRaj", ["a","b","c"])

print "TRYING TO REPLACE KEY 3"
py_mongodb.put_entity("helloRaj", "3", ["a","b","c"], ["1","2","3"])
py_mongodb.get_table("helloRaj", ["a","b","c"])
ret = py_mongodb.delete_row("helloRaj", "1")
ret = py_mongodb.delete_row("helloRaj", "2")
ret = py_mongodb.delete_row("helloRaj", "3")
py_mongodb.get_table("helloRaj", ["a","b","c"])
print "Deleting table:"
print py_mongodb.delete_table("helloRaj")
print "deleting twice:"
print py_mongodb.delete_table("helloRaj")
