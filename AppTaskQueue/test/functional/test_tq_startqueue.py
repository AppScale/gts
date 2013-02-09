#!/usr/bin/env python
# Programmer: Navraj Chohan <raj@appscale.com>
import httplib
import json
import os
import socket
import sys
import unittest
import urllib2

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../lib"))
import file_io

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

# AppScale must already be running with RabbitMQ
class TestTaskQueueServer(unittest.TestCase):
  def test_master(self):
    values = {'app_id':'test_app', 
              'command': 'update',
              'queue_yaml': FILE_LOC
             }
    host = socket.gethostbyname(socket.gethostname())
    req = urllib2.Request('http://' + host + ':64839/queues')
    req.add_header('Content-Type', 'application/json')
    response = urllib2.urlopen(req, json.dumps(values))
    print response.read()
    self.assertEquals(response.getcode(), 200)
             
if __name__ == "__main__":
  unittest.main()
