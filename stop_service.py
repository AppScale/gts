#!/usr/bin/env python
import subprocess
import sys
import time

process = sys.argv[1]
identifier = sys.argv[2]

print "/bin/ps ax | grep '" + process + "' | grep -v grep | " \
  "grep '" + identifier + "' | awk '{print $1}' | xargs kill -15"
subprocess.call("/bin/ps ax | grep '" + process + "' | grep -v grep | " \
  "grep '" + identifier + "' | awk '{print $1}' | xargs kill -15", shell=True)

time.sleep(1)

print "/bin/ps ax | grep '" + process + "' | grep -v grep | " \
  "grep '" + identifier + "' | awk '{print $1}' | xargs kill -9"
subprocess.call("/bin/ps ax | grep '" + process + "' | grep -v grep | " \
  "grep '" + identifier + "' | awk '{print $1}' | xargs kill -9", shell=True)
