#!/usr/bin/env python
#
# This script is used by AppScale with monit: it allows to stop services
# controlled by monit.
from os.path import basename
import subprocess
import sys

# Make sure we have the right number of arguments
if len(sys.argv) != 3:
  print sys.argv[0] + ": needs 2 arguments the process, and an identifier."
  sys.exit(1)

process = sys.argv[1]
identifier = sys.argv[2]

# Get all the lines matching the arguments. We print the group PID and the
# arguments, so that killing the group PID allow to terminate also the
# related processes.
ps_output = subprocess.check_output(["/bin/ps", "-eo", "pgid,args"]).split('\n')
for line in ps_output:
  if basename(sys.argv[0]) in line:
     continue
  if identifier in line and process in line:
    pgid = "-" + line.split()[0]
    print "Found a match: " + line
    subprocess.call(["/bin/kill", "-SIGKILL", pgid])
    sys.exit(0)

print "Didn't find a match."
sys.exit(2)
