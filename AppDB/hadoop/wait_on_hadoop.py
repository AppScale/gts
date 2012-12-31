#!/usr/bin/env python
# Author: Navraj Chohan
import logging
import logging.handlers
import os
import string
import sys
import time

from socket import *

APPSCALE_HOME = os.environ.get("APPSCALE_HOME")
if APPSCALE_HOME:
  pass
else:
  APPSCALE_HOME = "/root/appscale"
  print "APPSCALE_HOME env var not set. Using default " + APPSCALE_HOME

LOG_DIR = "/root/appscale/AppDB/logs"
LOG_FILENAME = LOG_DIR + "/wait_on_hadoop.log"
if not os.path.exists(LOG_DIR): os.mkdir(LOG_DIR,0777)

formatter = logging.Formatter("%(asctime)s %(module)s:%(lineno)-4d %(message)s")
handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=10000000, 
backupCount=10)
handler.setFormatter(formatter)

DEBUG = True

HADOOP_PORT = 9000

MAX_RETRIES = 100

SLAVE_FILE =  APPSCALE_HOME + "/.appscale/slaves"

MASTER_FILE = APPSCALE_HOME + "/.appscale/masters"

masters = []
slaves = []

# Read in the masters
FILE = open(SLAVE_FILE, "r")
line = FILE.readline()
while line:
  slaves.append(line)
  if DEBUG: print "Slave added: " + line
  line = FILE.readline()
FILE.close() 
total_slaves_up = 0

command = "lsof -i :9000 | grep java | grep 9000 | wc -l | grep "

command = command + str(len(slaves) + 1)

num_tries = 0
while num_tries < MAX_RETRIES:
  num_tries = num_tries + 1
  result = os.system(command)
  if result == 0:
    if DEBUG: print "Master ready" 
    exit(1)
  else:
    if DEBUG: print "Master not ready, sleeping"
    time.sleep(5)
  if num_tries == MAX_RETRIES:
    if DEBUG: print "Maxed out on attempts for master"
    exit(1)
