# Programmer: Chris Bunch


import os
import random
import sys


from django.utils import simplejson as json
from google.appengine.api import users


"""
  Babel API: Enables users to submit Babel jobs, a simplified version of running
    Neptune jobs, making it easier to poll for the standard output/error
    produced by running arbitrary code.
"""


def can_run_jobs():
  """
    Determines if jobs can be run from this machine. Since babel is installed
    everywhere and is called locally, it's available from everywhere.
  """
  return True


def run_job(params):
  """
    Runs a babel job with the given parameters.

    Arguments:
      params: A dict that will be used as the parameters to this babel job.

    Returns:
      A dict that indicates if the babel job was started successfully. If the
        job was started successfully, it also includes keys that indicate the
        standard output, error, and metadata for this job. If the job was not
        started started successfully, the reason why the job failed to start is
        also included.
  """
  if not isinstance(params, dict):
    return {'success': False, 'reason':'params not a dict'}

  contents = "require 'rubygems'\n"
  contents += "require 'babel'\n"
  contents += "require 'json'\n\n"
  contents += "task = babel({\n"

  for k, v in params.iteritems():
    if isinstance(v, str):
      contents += "  %s => '%s',\n" % (k, v)
    elif isinstance(v, list):
      contents += "  %s => [" % k
      for item in v:
        contents += "'%s', " % str(item)
      contents += "],\n"
    else:
      raise Exception("v was not a str or list")
  
  contents += "  :run_local => true,\n"
  contents += "  :engine => 'appengine-push-q',\n"
  contents += "  :is_remote => false})\n\n"
  contents += "puts task.to_json()\n"

  file_location = "/tmp/babel-job-%s.rb" % str(random.randint(0, 100000))
  f = open(file_location, "w+")
  f.write(contents)
  f.close()

  sys.stderr.write("write file at %s" % file_location)
  encoded_result = os.popen("/root/neptune/bin/neptune %s" % file_location).read()
  sys.stderr.write("job result was [%s]" % encoded_result)
  result = json.loads(encoded_result)
  result['success'] = True

  #os.remove(file_location)
  return result


def get_output(params):
  contents = "require 'rubygems'\n"
  contents += "require 'json'\n"
  contents += "require 'neptune'\n\n"
  contents += "encoded_result = '%s'\n\n" % params
  contents += "task = TaskInfo.new(encoded_result)\n"
  contents += "puts task.stdout\n"

  file_location = "/tmp/babel-job-%s.rb" % str(random.randint(0, 100000))
  f = open(file_location, "w+")
  f.write(contents)
  f.close()

  sys.stderr.write("write file at %s" % file_location)
  output = os.popen("/root/neptune/bin/neptune %s" % file_location).read()
  sys.stderr.write("job result was [%s]" % output)
  return output
