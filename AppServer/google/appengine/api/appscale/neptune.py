# See AppScale License
# Programmer: Chris Bunch


import os
import random
import re
import sys
import time
import urllib


from google.appengine.api import users


# The full path to the Neptune executable on this virtual machine.
NEPTUNE_PATH = "/usr/lib/ruby/gems/1.8/gems/neptune-0.2.2/bin/neptune"


class NeptuneException(Exception):
  """
    NeptuneException is a custom exception type that is raised whenever method
      calls in the Neptune API or Babel API are called incorrectly or experience
      unexpected behaviors.
  """
  pass


"""
  Neptune API: Enables users to submit Neptune jobs to run HPC apps
  over their currently running AppScale deployment. 
"""


def can_run_jobs():
  """
    Determines if jobs can be run from this machine, and is primarily used by
      the AppLoadBalancer's status page. Since neptune is installed
      everywhere and is called locally, it's available from everywhere.
  """  
  return True


def ensure_user_is_neptune_authorized():
  """
    Uses the Users API to check the currently logged in user's authorizations,
      raising an exception if they are not authorized to use the Neptune API.

    Raises:
      NeptuneException: If the currently logged in user is not authorized to 
        use the Neptune API.

    Returns:
      None: If the currently logged in user is authorized to use the Neptune
        API.
  """
  if not users.is_current_user_capable("neptune_api"):
    raise NeptuneException("this user cannot call the neptune api")


def run_neptune_job(file_location):
  """
    Executes a Neptune job via the neptune RubyGem.

    Arguments:
      file_location: The path on the local filesystem corresponding to the
        Neptune file to execute.

    Raises:
      NeptuneException: If the given user is not authorized to call the Neptune
        API, or if the neptune RubyGem could not be found.

    Returns:
      A string corresponding to the result of invoking the given Neptune job.
  """
  ensure_user_is_neptune_authorized()
  file_location = urllib.unquote(file_location)
  regex = r"[^\w\d/\.-]"
  pattern = re.compile(regex)
  file_location = pattern.sub('', file_location)

  if os.path.exists(file_location):
    cmd = "neptune " + file_location
    return os.popen(cmd).read()
  else:
    raise NeptuneException("neptune executable not found")


def write_neptune_job_params(params):
  """
    Creates a Neptune job from the given parameters and writes the job to the
      local filesystem.

    Arguments:
      params: A dict whose keys and values map to the parameters used in a
        Neptune job.
    
    Raises:
      NeptuneException: If the currently logged in user is not authorized to
        call the Neptune API.

    Returns:
      A string corresponding to the path on the local filesystem where the
        Neptune job was written to.
  """
  ensure_user_is_neptune_authorized()
  neptune_code = "puts neptune(:boo => 2, \n"

  for k, v in params.iteritems():
    neptune_code += "  " + str(k) + " => " + str(v) + ",\n"

  neptune_code += "  :baz => 2).inspect" 
  return write_neptune_job_code(neptune_code)


def write_neptune_job_code(code):
  """
    Writes the given Neptune job to the local filesystem in a randomly
      generated location.

    Arguments:
      code: A string corresponding to the Neptune code to write to the local 
        filesystem.

    Raises:
      NeptuneException: If the currently logged in user is not authorized to
        call the Neptune API.

    Returns:
      A string corresponding to the path on the local filesystem where the
        Neptune job was written to.
  """
  ensure_user_is_neptune_authorized()
  neptune_dir = "/tmp/neptune/%d/" % random.randint(0,1000000)
  mkdir_p = "mkdir -p " + neptune_dir
  os.system(mkdir_p)

  file_location = neptune_dir + "job-" + str(random.randint(0,1000000))
  f = open(file_location, "w+")
  f.write(code)
  f.close()

  sys.stderr.write("Wrote Neptune code to " + file_location)
  return file_location
