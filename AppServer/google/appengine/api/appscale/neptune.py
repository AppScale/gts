# See AppScale License

import os
import random
import re
import sys
import time
import urllib

from google.appengine.api import users
"""
  Neptune API: Enables users to submit Neptune jobs to run HPC apps
  over their currently running AppScale deployment. 
"""

# like ec2 api, the neptune service is just called locally
# so for now, it's available from anywhere
def can_run_jobs():
  return True

def run_neptune_job(file_location):
  file_location = urllib.unquote(file_location)
  regex = r"[^\w\d/\.-]"
  pattern = re.compile(regex)
  file_location = pattern.sub('', file_location)

  result = "file not found"
  if os.path.exists(file_location):
    cmd = "neptune " + file_location
    result = os.popen(cmd).read()

  sys.stderr.write(result)
  return result

def write_neptune_job_params(params):
  neptune_code = "puts neptune(:boo => 2, \n"

  for k, v in params.iteritems():
    neptune_code += "  " + str(k) + " => " + str(v) + ",\n"

  neptune_code += "  :baz => 2).inspect"
 
  return write_neptune_job_code(neptune_code)

def write_neptune_job_code(code):
  neptune_dir = "/tmp/neptune/%d/" % random.randint(0,1000000)
  mkdir_p = "mkdir -p " + neptune_dir
  os.system(mkdir_p)

  file_location = neptune_dir + "job-" + str(random.randint(0,1000000))
  f = open(file_location, "w+")
  f.write(code)
  f.close()

  sys.stderr.write("Wrote Neptune code to " + file_location)
  return file_location
