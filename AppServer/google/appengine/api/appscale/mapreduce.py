# See AppScale License
# Programmer: Chris Bunch


import os
import re
import sys
import time
import urllib
import yaml


from google.appengine.api import users


# The full path to where AppScale is installed.
APPSCALE_HOME = os.environ.get("APPSCALE_HOME")


# The version of Hadoop currently used within AppScale.
HADOOP_VER = "0.20.2-cdh3u3"


# The full path on the local filesystem to where Hadoop is installed.
HADOOP_HOME = APPSCALE_HOME + "/AppDB/hadoop-" + HADOOP_VER + "/"


# The full path on the local filesystem to the Hadoop JAR.
HADOOP_BIN = APPSCALE_HOME + "/AppDB/hadoop-" + HADOOP_VER + "/bin/hadoop"


# The full path on the local filesystem to the Hadoop Streaming JAR.
HADOOP_STREAMING = HADOOP_HOME + "/contrib/streaming/hadoop-" + HADOOP_VER + \
  "-streaming.jar"


# A list of databases that we automatically configure/deploy Hadoop for.
DBS_W_HADOOP = ["hbase", "hypertable"]


class MapReduceException(Exception):
  """
    MapReduceException is a custom exception type that is raised whenever method
      calls in the AppScale MapReduce API are called incorrectly or experience
      unexpected behaviors.
  """
  pass


"""
  AppScale MapReduce API: Offers App Engine users the ability to call
  Hadoop MapReduce Streaming to run MR jobs written in any supported language.
  We should expand the supported languages at some point - right now the list
  is short but many languages should be able to run with minimal effort.
"""


def can_run_jobs():
  """
    Determines if MapReduce jobs can be run in the currently running AppScale
      deployment. Currently this is possible if we've started Hadoop up, so
      we see which database we've started and see if that also required Hadoop
      to be started in the system.

    TODO(cgb): It could be the case that the JobTracker or HDFS itself has
    failed and we erroneously report this API as being available - look into how
    to detect these failures or just poll HDFS, the JobTracker, or parse the
    internal web pages that they host.

    Returns:
      True if MapReduce jobs can be deployed, False otherwise.
  """
  stream = file("/etc/appscale/database_info.yaml", 'r')
  contents = yaml.load(stream)
  try:
    database = contents[':table']
    if database in DBS_W_HADOOP:
      return True
    else:
      return False
  except KeyError:
    return False


def getLang(filename):
  """
    Parses the given filename to see what executable can be used to run that
      type of code in a MapReduce Streaming job.

    Arguments:
      filename: A string that corresponds to a UNIX filename, which should have
      a dot and some extension following it.

    Raises:
      MapReduceException: If the given filename did not have an extension that
        is not supported by our MapReduce Streaming support.

    Returns:
      A string corresponding to the executable that can be used to execute code
        matching the given filename.
  """
  supportedExtensions = {
    "rb" : "ruby",
    "py" : "python",
    "pl" : "perl",
  }

  try:
    extension = filename.split(".")[-1]
    lang = supportedExtensions[extension]
    return lang
  except:
    raise MapReduceException("extension %s not recognized\n" % extension)


def ensure_user_is_mapreduce_authorized():
  """
    Uses the Users API to check the currently logged in user's authorizations,
      raising an exception if they are not authorized to use the AppScale
      MapReduce API.

    Raises:
      MapReduceException: If the currently logged in user is not authorized to
      use the AppScale MapReduce API.

    Returns:
      None: If the currently logged in user is authorized to use the AppScale
        MapReduce API.
  """
  if not users.is_current_user_capable("mapreduce_api"):
    raise MapReduceException("this user cannot call the mapreduce api")


def writeTempFile(suffix, data):
  """
    Writes a file on the local filesystem with the given contents, to be used as
      input to a Hadoop MapReduce job.

    Arguments:
      suffix: The relative name of the file to write to the local filesystem.
      data: The contents of the file to write to the local filesystem.

    Raises:
      MapReduceException: If the currently logged in user is not authorized to
        call the MapReduce API.

    Returns:
      The location on the local filesystem where the file was written to.
  """
  ensure_user_is_mapreduce_authorized()
  suffix = urllib.unquote(suffix)
  regex = r"[^\w\d/\.-]"
  pattern = re.compile(regex)
  suffix = pattern.sub('', suffix)

  fileLoc = "/tmp/" + suffix
  f = open(fileLoc, "w+")
  f.write(data)
  f.close()
  return fileLoc


def getAllIPs():
  """
    Returns a list of all the IP addresses in the currently running AppScale
      deployment that can be used to run MapReduce jobs.

    Raises:
      MapReduceException: If the currently logged in user is not authorized to
        call the AppScale MapReduce API.

    Returns:
      A list of all the IP addresses in this AppScale deployment.
  """
  ensure_user_is_mapreduce_authorized()
  all_ips = []
  fileLoc = "/etc/appscale/all_ips"
  if os.path.exists(fileLoc):
    f = open(fileLoc)
    text = f.read()
  all_ips = text.split("\n")
  return all_ips


def getNumOfNodes():
  """
    Determines how many nodes are running in this AppScale deployment.

    Raises:
      MapReduceException: If the currently logged in user is not authorized to
        call the AppScale MapReduce API.

    Returns:
      An int corresponding to the number of nodes running in this AppScale
        deployment.
  """
  ensure_user_is_mapreduce_authorized()
  num_of_nodes = 0
  fileLoc = "/etc/appscale/num_of_nodes"
  if os.path.exists(fileLoc):
    f = open(fileLoc)
    num_of_nodes = int(f.read())
  return num_of_nodes


def putMRInput(data, inputLoc):
  """
    Stores the given string to a file in HDFS.

    Arguments:
      data: A string whose contents will be written to HDFS.
      inputLoc: The HDFS path that the given data should be written to.

    Raises:
      MapReduceException: If the currently logged in user is not authorized to
        call the AppScale MapReduce API.

    Returns:
      None.
  """
  ensure_user_is_mapreduce_authorized()
  inputLoc = urllib.unquote(inputLoc)
  regex = r"[^\w\d/\.-]"
  pattern = re.compile(regex)
  inputLoc = pattern.sub('', inputLoc)

  fileLoc = "/tmp/" + inputLoc
  f = open(fileLoc, "w+")
  f.write(data)
  f.close()

  removeInput = HADOOP_BIN + " fs -rmr " + inputLoc
  sys.stderr.write(removeInput + "\n")
  os.system(removeInput)

  put = HADOOP_BIN + " fs -put " + fileLoc + " " + inputLoc
  os.system(put)


def runMRJob(mapper, reducer, inputLoc, outputLoc, config={}):
  """
    Runs a Hadoop MapReduce Streaming job.
    
    Arguments:
      mapper: The path on the local filesystem to the Map file to use.
      reducer: The path on the local filesystem to the Reduce file to use.
      inputLoc: The path on HDFS to the input file to use.
      outputLoc: The path on HDFS to where the output should be stored.
      config: A dict corresponding to arguments to pass to Hadoop MapReduce
        Streaming (analogous to -D options).

    Raises:
      MapReduceException: If the currently logged in user is not authorized to
        call the AppScale MapReduce API.

    Returns:
      None.
  """
  ensure_user_is_mapreduce_authorized()
  mapper = urllib.unquote(mapper)
  reducer = urllib.unquote(reducer)
  inputLoc = urllib.unquote(inputLoc)
  outputLoc = urllib.unquote(outputLoc)

  regex = r"[^\w\d/\.-]"
  pattern = re.compile(regex)

  mydir = os.getcwd() + "/"
  mapper = "\"" + getLang(mapper) + " " + mydir + pattern.sub('', mapper) + "\""
  reducer = "\"" + getLang(reducer) + " " + mydir + pattern.sub('', reducer) + "\""
  inputLoc = pattern.sub('', inputLoc)
  outputLoc = pattern.sub('', outputLoc)

  removeOutput = HADOOP_BIN + " fs -rmr " + outputLoc
  sys.stderr.write(removeOutput + "\n")
  os.system(removeOutput)

  formattedConfig = ""
  for key in config:
    formattedConfig = formattedConfig + " -D " + key + "=" + config[key]
  command = HADOOP_BIN + " jar " + HADOOP_STREAMING +" " + formattedConfig + " -input " + inputLoc + " -output " + outputLoc + " -mapper " + mapper + " -reducer " + reducer
  sys.stderr.write("\n" + command + "\n")
  start = time.time()
  os.system(command)
  end = time.time()
  sys.stderr.write("\nTime elapsed = " + str(end - start) + "seconds\n")


def getMROutput(outputLoc):
  """
    Queries HDFS for the contents of the file at the named location.

    Arguments:
      outputLoc: The HDFS path to query for MapReduce job results.

    Raises:
      MapReduceException: If the currently logged in user is not authorized to
        call the AppScale MapReduce API, or if the given filename does not exist
        in HDFS.

    Returns:
      A string corresponding to the HDFS filename to read. 
  """
  ensure_user_is_mapreduce_authorized()
  outputLoc = urllib.unquote(outputLoc)
  regex = r"[^\w\d/\.-]"
  pattern = re.compile(regex)
  outputLoc = pattern.sub('', outputLoc)

  fileLoc = "/tmp/" + outputLoc

  rmr = "rm -rf " + fileLoc
  os.system(rmr)
  get = HADOOP_BIN + " fs -get " + outputLoc + " " + fileLoc
  os.system(get)

  if os.path.exists(fileLoc):
    cmd = "cat " + fileLoc + "/part*"
    return os.popen(cmd).read()
  else:
    raise MapReduceException("HDFS file not found.")


def getMRLogs(outputLoc):
  """
    Queries HDFS to see if any log files exist for the named MapReduce job.

    Arguments:
      outputLoc: A string corresponding to the HDFS location where logs can be
        found for a MapReduce job.

    Raises:
      MapReduceException: If the currently logged in user is not authorized to
        call the AppScale MapReduce API, or if no logs exist for the named
        MapReduce job.

    Returns:
      A string containing the logs of the given MapReduce job path.
  """
  ensure_user_is_mapreduce_authorized()
  outputLoc = urllib.unquote(outputLoc)
  regex = r"[^\w\d/\.-]"
  pattern = re.compile(regex)
  outputLoc = pattern.sub('', outputLoc)

  fileLoc = "/tmp/" + outputLoc
  rmr = "rm -rf " + fileLoc
  os.system(rmr)

  get = HADOOP_BIN + " fs -get " + outputLoc + " " + fileLoc
  os.system(get)

  if os.path.exists(fileLoc):
    cmd = "cat " + fileLoc + "/_logs/history/*"
    return os.popen(cmd).read()
  else:
    raise MapReduceException("No logs exist for %s" % outputLoc)
