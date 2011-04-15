import py_hypertable
import string
import random
def GenPasswd2(length=8, chars=string.letters + string.digits):
  return ''.join([random.choice(chars) for i in range(length)])

print py_hypertable.get_schema("APPS__")
print py_hypertable.get_schema("USERS__")
print "does apps table exist: (should)"
print py_hypertable.__table_exist("APPS__")
print "does qwert table exist: (should not)"
print py_hypertable.__table_exist("qwerty")

table = "test_"+ GenPasswd2(10) 
print "creating table " + table + " result and adding 2 rows:"
print py_hypertable.put_entity(table, "1", ["c1","c2", "c3"], ["a1","b2","c3"])
print py_hypertable.put_entity(table, "2", ["c1","c2", "c3"], ["d4","e5","f6"])
print "does this newly table exist:"
print py_hypertable.__table_exist(table)

print "doing a get entity for row key 1:"
print py_hypertable.get_entity(table, "1", ["c1", "c2", "c3"])
print "doing a get entity for row key 2:"
print py_hypertable.get_entity(table, "2", ["c1", "c2", "c3"])
print "how many rows are in this table?"
print py_hypertable.get_row_count(table)
print "getting entire table:"
print py_hypertable.get_table(table, ["c1","c2","c3"])

print "what happens when trying to do a get on a table that doesnt exist:"
print py_hypertable.get_entity("qwerty", "1", ["a","b","c"])

print "query that table"
print py_hypertable.__query_table(table)

print "delete row from table ",table
print py_hypertable.delete_row(table, "1")

print "Doing a get on that which was deleted"
print py_hypertable.get_entity(table, "1", ["c1", "c2", "c3"])
print "query the table"
print py_hypertable.__query_table(table)
print "doing a get entity:"
print py_hypertable.get_entity(table, "1", ["c1", "c2", "c3"])
print "getting entire table:"
print py_hypertable.get_table(table, ["c1","c2","c3"])

