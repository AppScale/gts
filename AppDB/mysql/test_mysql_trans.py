import py_mysql
import random
#over write the import
py_mysql = py_mysql.DatastoreProxy()
columns = ["a","b","c"]
data = ["1","2","3"]
invalid_data = ['y','y','y']
table_name = "hello"
key = "1"
print "key= " + key
print "columns= " + str(columns)
print "data= " + str(data)
print "table= " + table_name
txn = random.randint(0,100000000)
py_mysql.setupTransaction(txn)
print "Test: Transaction number:",txn
py_mysql.put_entity(table_name, key, columns, invalid_data, txn)
ret = py_mysql.get_entity(table_name, key, columns, txn)
print "Test: Invalid:"
print ret
ret = py_mysql.get_entity(table_name, key, columns)
print "Test: Outside transaction:"
print ret
print py_mysql.put_entity(table_name, key, columns, data, txn)
print "Test: GET"
ret = py_mysql.get_entity(table_name, key, columns, txn)
print "Test: Valid:"
print ret
print "Test: Committing:"
#print py_mysql.commit(txn)
print ret
if ret[1:] != data:
  print "ERROR doing a put then get. Data does not match"
  print "returned: " + str(ret)
  print "expected: " + str(data)
  exit(1)
else: 
  print "Success"
py_mysql.commit(txn)
print "After committed transaction:"
ret = py_mysql.get_entity(table_name, key, columns)
print ret
txn = random.randint(0,100000000)
py_mysql.setupTransaction(txn)
txn2 = random.randint(0,11000000000)
py_mysql.setupTransaction(txn2)
print "Transaction number:",txn
print "PUT:"
print py_mysql.put_entity(table_name, key, columns, invalid_data, txn)
print "outside transaction:"
ret = py_mysql.get_entity(table_name, key, columns,txn2)
print ret
print "inside transaction:"
ret = py_mysql.get_entity(table_name, key, columns, txn)
print ret
print py_mysql.put_entity(table_name, key, columns, invalid_data, txn)
print "Rollback:"
print py_mysql.rollback(txn)
print "doing a put, rollback, then get"
print "GET"
ret = py_mysql.get_entity(table_name, key, columns)
print "doing a put then get"
print ret
if ret[1:] != data:
  print "*" * 60
  print "FAILURE doing a put then get. Data does not match"
  print "returned: " + str(ret)
  print "expected: " + str(data)
  print "*" * 60
  exit(1)
else: 
  print "Success"

ret = py_mysql.get_schema("hello")
print ret
print "checking schema:"
print ret
if ret[1:] != columns:
  print "ERROR in recieved schema"
  print "returned: " + str(ret)
  print "expected: " + str(columns)

#ret = py_mysql.__table_exist(table_name)
#print "Does table we just created exist?"
#print ret

ret = py_mysql.delete_row(table_name, key)
print "Deleting the key %s"%key
print ret

ret = py_mysql.get_entity(table_name, key, columns)
print "Trying to get deleted key:"
print ret
print "doing a put with key %s"%key
print py_mysql.put_entity("hello", "1", ["a","b","c"], ["1","2","3"])
print "doing a get table" 
print py_mysql.get_table("hello", ["a","b","c"])
py_mysql.put_entity("hello", "2", ["a","b","c"], ["4","5","6"])
print "doing get table:"
print py_mysql.get_table("hello", ["a","b","c"])
py_mysql.put_entity("hello", "3", ["a","b","c"], ["1","2","3"])
py_mysql.get_table("hello", ["a","b","c"])

print "TRYING TO REPLACE KEY 3"
py_mysql.put_entity("hello", "3", ["a","b","c"], ["1","2","3"])
py_mysql.get_table("hello", ["a","b","c"])
py_mysql.get_row_count("hello")
ret = py_mysql.delete_row("hello", "1")
ret = py_mysql.delete_row("hello", "2")
ret = py_mysql.delete_row("hello", "3")
py_mysql.get_table("hello", ["a","b","c"])
print "Deleting table:"
print py_mysql.delete_table("hello")
print "deleting twice:"
print py_mysql.delete_table("hello")
