#!/usr/bin/env python
import sys
import SOAPpy

if len(sys.argv) != 4:
  print "argv was not 4"
  exit(1)

ip = "https://" + sys.argv[1] + ":4343"
app_name = sys.argv[2]
secret = sys.argv[3]

server = SOAPpy.SOAPProxy(ip)
print server.get_tar(app_name, secret)