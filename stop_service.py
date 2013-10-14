#!/usr/bin/env python
import subprocess
import sys

process = sys.argv[1]
identifier = sys.argv[2]

print "/bin/ps ax | grep '" + process + "' | grep -v grep | " \
  "grep '" + identifier + "' | awk '{print $1}' | xargs kill -9"
subprocess.call("/bin/ps ax | grep '" + process + "' | grep -v grep | " \
  "grep '" + identifier + "' | awk '{print $1}' | xargs kill -9", shell=True)
