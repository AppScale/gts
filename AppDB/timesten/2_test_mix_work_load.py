from py_timesten import *
import pyodbc
import string
import MySQLdb
import _mysql
import base64
import time

'''
	This example runs a mixed workloads
	In the main method it runs a few workloads and prints
	the time taken for each workload
        
	We basically use the mix_work_load method that runs 
	the following operations in serial order
		num_puts number of put_entity
		num_gets number of get_entity
		num_deletes number of delete_row
'''
def mix_work_load(table_name, num_puts, num_gets, num_deletes):
	
   start = time.time()
 
   for ii in range (0, num_puts):
	put_entity (table_name, str(ii) , ["a", "b", "c"], [str(ii), "11", "22"])
   for ii in range (0, num_gets):
	get_entity (table_name, str(ii) , ["a", "b", "c"])

   ret = get_row_count (table_name)
   print "Number of rows in the table before deletes " + str(ret [0])

   for ii in range (0, num_deletes):
        ret = delete_row (table_name, str(ii))
	if (ret): print ret

   ret = get_row_count (table_name)
   print "Number of rows in the table after deletes " + str(ret [0])
   
   elapsed = time.time() - start

   print "Time spent : " + str (elapsed*1000) + " milliseconds"


   

def main():

   print "----------------------------------------------"
  
   print MySQLdb.escape_string ('1. Mix workload : 10 puts 10 gets 5 deletes ') 
   mix_work_load ("hello3", 10, 10, 5)
  
   print ""
   print MySQLdb.escape_string ('2. Mix workload : 10 puts 10 gets 12 deletes -> error ') 
   mix_work_load ("hello3", 10, 10, 12)

   print ""
   print MySQLdb.escape_string ('3. Mix workload : 100 puts 100 gets 50 deletes ') 
   mix_work_load ("hello3", 100, 100, 50)

   print "----------------------------------------------"



if __name__ == '__main__':
    main()
    


