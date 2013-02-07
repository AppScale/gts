#!/usr/bin/env python
# Programmer: Navraj Chohan <raj@appscale.com>
import json
import os
import socket
import sys
import unittest

FILE_LOC = "/tmp/queue.yaml"
def create_test_yaml():
  file_loc = FILE_LOC
  config = \
"""
queue:
- name: default
  rate: 5/s
- name: foo
  rate: 10/m
"""
  FILE = file_io.write(config, file_loc)

values = {'app_id':'test_app', 
          'load_type': 'update',
          'queue_yaml': FILE_LOC
         }
#host = 'appscale-image0'
host = 'localhost'
host = '127.0.0.1'
import urllib2
req = urllib2.Request('http://' + host + ':64839/queues')
req.add_header('Content-Type', 'application/json')
response = urllib2.urlopen(req, json.dumps(values))
print response
exit(0)
connection = httplib.HTTPConnection('http://' + host + ':64839')
connection.putrequest("POST", "/queues")
connection.putheader("Content-Length", "%d" % len(values))
connection.endheaders()
connection.send(values)
conn_response = connection.getresponse()
self.assertEquals(conn_reponse.status, 200)
json_response = conn_response.read()
json_response = json.loads(json_response)
print json_response
