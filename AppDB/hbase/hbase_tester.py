#!/usr/bin/env python
import sys
import random
from thrift import Thrift
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from hbase import Hbase
from hbase.ttypes import *
from datetime import datetime
# You may have to put in the IP instead of localhost
transport = TSocket.TSocket('localhost', 9090)
 
# Buffering is critical. Raw sockets are very slow
transport = TTransport.TBufferedTransport(transport)
 
# Wrap in a protocol
protocol = TBinaryProtocol.TBinaryProtocol(transport)
client = Hbase.Client(protocol)
 
transport.open()
 
try: #Try to create the table if it doesn't exist
    client.createTable('test_table', [ColumnDescriptor(name='meta')])
except AlreadyExists, tx:
    print "Thrift exception"
    print '%s' % (tx.message)
 
for benchmark in range(4): #range(8) goes up to 10,000,000 rows, takes about 3hrs on my 2GB linode
    num = 10**benchmark
    print "Benchmark #%d: %d rows" %(benchmark, num)
    start = datetime.now()
    for i in range(num):
        client.deleteAllRow('test_table', "%d"%i)
    print '  Rows deleted: %s' % (datetime.now() - start)
    create_start = datetime.now()
    for i in range(num):
        client.mutateRow('test_table', "%d"%i,
                [Mutation(column="meta:%s"%random.choice(['a', 'b', 'c']),
                    value = "x"*10000)])
                    #value="%d"%random.randrange(100))])
    print '  Rows created: %s' % (datetime.now() - create_start)
    get_start = datetime.now()
    r = client.getRow('test_table', "%s"%random.randrange(num))
    print '  Row lookup: %s' % (datetime.now() - get_start)
    scan_start = datetime.now()
    s = client.scannerOpen('test_table', '', ['meta:a'])
    r = client.scannerGet(s)
    count = 0
    r = client.scannerGet(s)
    while r:
        count += 1
        r = client.scannerGet(s)
    print '  Fetched %s rows with meta:A: %s' %(count, datetime.now() - scan_start)
    print '  Total Benchmark Time: %s' % (datetime.now() - start)
 
