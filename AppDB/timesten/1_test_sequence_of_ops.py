from py_timesten import *
import pyodbc
import string
import MySQLdb
import _mysql
import base64

'''
  This test file runs a sequence of basic operations from py_timesten module
  and prints the results

'''

def main():

    print ""
    print "------------------------------------------------------------"
    print ""

 
    print MySQLdb.escape_string ('1. get_entity("hello2", "1", ["a","b","c"])')
    ret = get_entity("hello2", "1", ["a","b","c"])
    print_list ( ret )
    print ""

    print MySQLdb.escape_string ('2. delete_row("hello", "abc123")')
    ret = delete_row("hello", "abc123")
    print ret
    print ""

    print MySQLdb.escape_string ('3. put_entity("hello", "1", ["a","b","c"], ["12345","2","3"])')
    ret = put_entity("hello", "1", ["a","b","c"], ["12345","2","3"])
    print ""

    print MySQLdb.escape_string ('4. get_table("hello", ["a","b","c"])')
    ret = get_table("hello", ["a","b","c"])
    print_list ( ret )
    print ""

    print MySQLdb.escape_string ('5. delete_row("hello", "1")')
    ret = delete_row("hello", "1")
    print_list ( ret )
    print ""


    print MySQLdb.escape_string ('6. get_table("hello", ["a","b","c"]')
    ret = get_table("hello", ["a","b","c"])
    print_list ( ret )
    print ""

    print MySQLdb.escape_string ('7. put_entity("hello", "1", ["a","b","c"], ["1","2","3"])')
    put_entity("hello", "1", ["a","b","c"], ["1","2","3"])
    print ""


    print MySQLdb.escape_string ('8. put_entity("hello", "2", ["a","b","c"], ["4","5","6"])')
    put_entity("hello", "2", ["a","b","c"], ["4","5","6"])
    print ""
    
    print MySQLdb.escape_string ('9. put_entity("hello", "3", ["a","b","c"], ["1","2","3"])')
    put_entity("hello", "3", ["a","b","c"], ["1","2","3"])
    print ""

    print MySQLdb.escape_string ('10. get_table("hello", ["a","b","c"])')
    ret = get_table("hello", ["a","b","c"])
    print_list ( ret )
    print ""
	
    print MySQLdb.escape_string ('11. put_entity("hello", "3", ["a","b","c"], ["7","8","9"])')
    print "	TRYING TO REPLACE KEY 3 : testing update"
    put_entity("hello", "3", ["a","b","c"], ["7","8","9"])
    print ""

    print MySQLdb.escape_string ('12. get_table("hello", ["a","b","c"])')
    ret = get_table("hello", ["a","b","c"])
    print_list ( ret )
    print ""

    print MySQLdb.escape_string ('13. delete_row("hello", "1")')
    ret =  delete_row("hello", "1")
    print ""

    print MySQLdb.escape_string ('14. get_table("hello", ["a","b","c"]')
    ret = get_table("hello", ["a","b","c"])
    print_list ( ret )
    print ""

    print MySQLdb.escape_string ('15. delete_row("hello", "2")')
    ret =  delete_row("hello", "2")
    ret = get_table("hello", ["a","b","c"])
    print_list ( ret )
    print ""

    print MySQLdb.escape_string ('16. delete_row("hello", "3")')
    ret =     delete_row("hello", "3")
    ret = get_table("hello", ["a","b","c"])
    print_list ( ret )
    print ""

    print MySQLdb.escape_string ('17. get_row_count ("hello")')
    ret = get_row_count ("hello")
    print_list ( ret )
    print ""


    print ""
    print "------------------------------------------------------------"


if __name__ == '__main__':
    main()
    


