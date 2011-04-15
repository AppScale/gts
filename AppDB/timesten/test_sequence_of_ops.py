from py_timesten import *
import pyodbc
import string
import MySQLdb
import _mysql
import base64


def main():

    put_entity("hello", "1", ["a","b","c"], ["1","2","3"])
    ret = delete_row("hello", "1")
    print ret
    ret = get_entity("hello", "1", ["a","b","c"])
    print ret

    put_entity("hello", "1", ["a","b","c"], ["1","2","3"])
    get_table("hello", ["a","b","c"])
    put_entity("hello", "2", ["a","b","c"], ["4","5","6"])
    get_table("hello", ["a","b","c"])
    put_entity("hello", "3", ["a","b","c"], ["1","2","3"])
    ret = get_table("hello", ["a","b","c"])
	
    print "TRYING TO REPLACE KEY 3"
    put_entity("hello", "3", ["a","b","c"], ["7","8","9"])
    ret = get_table("hello", ["a","b","c"])
    print ret
    get_row_count("hello")
    ret =     delete_row("hello", "1")
    ret = get_table("hello", ["a","b","c"])
    print ret
    ret =     delete_row("hello", "2")
    ret = get_table("hello", ["a","b","c"])
    print ret
    ret =     delete_row("hello", "3")
    ret = get_table("hello", ["a","b","c"])
    print ret

    ret = get_row_count ("hello")
    print ret

if __name__ == '__main__':
    main()
    


