from py_timesten import *
import time
import pyodbc
import string
import MySQLdb
import _mysql
import base64

################################################################################
# This program runs a put_entity / get_entity / delete_row / get_table
# Usage : 
#	 python test_workload.py [--run_mode mode] [--num_ops N] [--table_name T]
#        Options:
# 	      --run_mode M 
#		  possible values for M are get_entity, put_entity 
#					    delete_row, get_table
#	      --num_ops N
#		  N is the number of operations
#	      -t, --table_name T
#		  T is the name of the table to run the workload on
##################################################################################

def main():

    from optparse import OptionParser

    parser = OptionParser(usage="usage: %prog [options] connection_string")
    parser.add_option("--run_mode", type="choice", action="store", dest="run_mode",default="put_entity",choices=["put_entity","get_entity","delete_row","get_table"])
    parser.add_option("--num_ops", type="int",dest="num_ops",help="number of operations. operation type depends on the run mode", default=100)
    parser.add_option("-t", "--table-name", type="string",dest="table_name",help="name of the table", default="TTTEST")

    (options, args) = parser.parse_args()

    start = time.time()

    print "----------------------------------------------"
    print "Operation chosen : " + options.run_mode
    print "Number of operations : " + str (options.num_ops)

    if (options.run_mode == "put_entity"):
	for ii in range (0, options.num_ops):
      	  put_entity(options.table_name, str(ii), ["a","b","c"], [str(ii),"2","3"])
	elapsed = (time.time() - start)
	print "Inserted " + str (options.num_ops) + " rows in " + str (elapsed) + " seconds wall clock time"
	
    elif options.run_mode == "get_entity": 
	for ii in range (0, options.num_ops):
      	  get_entity(options.table_name, str(ii), ["a","b","c"])
	elapsed = (time.time() - start)
	print "Looked up " + str (options.num_ops) + " rows in "  + str (elapsed) + " seconds wall clock time"
	
    elif options.run_mode == "delete_row":
	for ii in range (0, options.num_ops):
          delete_row(options.table_name, str (ii))
	elapsed = (time.time() - start)
	print "Deleted " + str (options.num_ops) + " rows in " + str (elapsed) + " seconds wall clock time"

    elif options.run_mode == "get_table":
  	get_table (options.table_name)
	elapsed = (time.time() - start)
	print "Retrieved all row from " + table_name + " in "  + str (elapsed) + " seconds wall clock time"
	 
 
    print "Time spent per operation : " + str (elapsed*1000/options.num_ops) + " milliseconds"
    
    print "----------------------------------------------"


if __name__ == '__main__':
    main()
    


