# See AppScale License

import os
import re
from google.appengine.api import SOAPpy
import sys
import time
import urllib
from google.appengine.api import users

APPSCALE_HOME = os.environ.get("APPSCALE_HOME")
HADOOP_VER = "0.20.2"
HADOOP_HOME = APPSCALE_HOME + "/AppDB/hadoop-"+HADOOP_VER + "/"
HADOOP_BIN = APPSCALE_HOME + "/AppDB/hadoop-"+HADOOP_VER + "/bin/hadoop"
HADOOP_STREAMING = HADOOP_HOME + "/contrib/streaming/hadoop-"+HADOOP_VER+"-streaming.jar"

"""
  AppScale MapReduce API: Offers App Engine users the ability to call
  Hadoop MapReduce Streaming to run MR jobs written in any supported language.
  We should expand the supported languages at some point - right now the list
  is short but many languages should be able to run with minimal effort.
"""
#TODO make this into a class like the other APIs
def getLang(file):
  supportedExtensions = {
    "rb" : "ruby",
    "py" : "python",
    "pl" : "perl",
  }

  # return None if file is None
  extension = file.split(".")[-1]

  try:
    lang = supportedExtensions[extension]
    return lang
  except:
    sys.stderr.write("extension " + extension + " not recognized\n")
    return "none"

def writeTempFile(suffix, data):
  if users.is_current_user_capable("mr_api") == False:
    return "this user cannot call the mapreduce api"

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
  if users.is_current_user_capable("mr_api") == False:
    return "this user cannot call the mapreduce api"

  all_ips = []
  fileLoc = APPSCALE_HOME + "/.appscale/all_ips"
  if os.path.exists(fileLoc):
    f = open(fileLoc)
    text = f.read()
  all_ips = text.split("\n")
  return all_ips

def getNumOfNodes():
  if users.is_current_user_capable("mr_api") == False:
    return "this user cannot call the mapreduce api"

  num_of_nodes = 0
  fileLoc = APPSCALE_HOME + "/.appscale/num_of_nodes"
  if os.path.exists(fileLoc):
    f = open(fileLoc)
    num_of_nodes = int(f.read())

  return num_of_nodes

def putMRInput(data, inputLoc):
  if users.is_current_user_capable("mr_api") == False:
    return "this user cannot call the mapreduce api"

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

  return

def runMRJob(mapper, reducer, inputLoc, outputLoc, config={}):
  if users.is_current_user_capable("mr_api") == False:
    return "this user cannot call the mapreduce api"

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
  if users.is_current_user_capable("mr_api") == False:
    return "this user cannot call the mapreduce api"

  outputLoc = urllib.unquote(outputLoc)
  regex = r"[^\w\d/\.-]"
  pattern = re.compile(regex)
  outputLoc = pattern.sub('', outputLoc)

  fileLoc = "/tmp/" + outputLoc

  rmr = "rm -rf " + fileLoc
  os.system(rmr)
  get = APPSCALE_HOME + "/AppDB/hadoop-0.20.2/bin/hadoop fs -get " + outputLoc + " " + fileLoc
  os.system(get)

  contents = "no output"
  if os.path.exists(fileLoc):
    cmd = "cat " + fileLoc + "/part*"
    contents = os.popen(cmd).read()


  sys.stderr.write(contents)
  return contents

def getMRLogs(outputLoc):
  if users.is_current_user_capable("mr_api") == False:
    return "this user cannot call the mapreduce api"

  outputLoc = urllib.unquote(outputLoc)
  regex = r"[^\w\d/\.-]"
  pattern = re.compile(regex)
  outputLoc = pattern.sub('', outputLoc)

  fileLoc = "/tmp/" + outputLoc
  rmr = "rm -rf " + fileLoc
  os.system(rmr)

  get = APPSCALE_HOME + "/AppDB/hadoop-0.20.2/bin/hadoop fs -get " + outputLoc + " " + fileLoc
  os.system(get)

  contents = "no logs"
  if os.path.exists(fileLoc):
    cmd = "cat " + fileLoc + "/_logs/history/*"
    contents = os.popen(cmd).read()

  sys.stderr.write(contents)
  return contents


