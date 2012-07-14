"""
Author: Navraj Chohan
Random functions/classes which are used by datastores
"""
import logging
import logging.handlers
import os
import os.path
import random
import hashlib
"""
strings must be in unicode to reverse the string
strings are returned in unicode and may not able 
able to be converted to a regular string
"""
def reverseLex(ustring):
  newstr = ""
  for ii in ustring:
    ordinance = ord(ii)
    new_byte = 255 - ordinance
    char = chr(new_byte)
    newstr += char
  return newstr

""" 
Cetain datastores are unable to store keys with unichars of 128 or more
this function reflects on 127 and less.
"""
def reverseLex128(ustring):
  newstr = u""
  for ii in ustring:
    ordinance = ord(ii)
    new_byte = 127 - ordinance
    char = unichr(new_byte)
    newstr += char
  return newstr

class ThreadedLogger():
  def __init__(self, filename):
    split_path = os.path.split(filename)
    dir = split_path[0]
    if not os.path.exists(dir): os.mkdir(dir, 0777)
    self.log_logger = logging.getLogger(filename)
    self.log_logger.setLevel(logging.INFO)
    self.formatter = logging.Formatter("%(asctime)s %(module)s:%(lineno)-4d %(message)s")
    self.handler = logging.handlers.RotatingFileHandler(filename, maxBytes=10000000, backupCount=10)
    self.handler.setFormatter(self.formatter)
    self.log_logger.addHandler(self.handler)
    self.loggingOn = False

  def turnLoggingOn(self):
   self.loggingOn = True

  def debug(self, string):
    if self.loggingOn:
      self.log_logger.info(string)

def randomString(length):
  s = hashlib.sha256()
  ret = "a"
  while len(ret) < length:
    s.update(str(random.random()))
    ret += s.hexdigest()
  return ret[0:length]

import inspect
def lineno():
    """Returns the current line number in our program."""
    return inspect.currentframe().f_back.f_lineno
