# Programmer: Navraj Chohan <nlake44@gmail.com>
"""
Helpful functions and classes which are used by AppDB
"""
import hashlib
import logging
import logging.handlers
import inspect
import os
import os.path
import random
import time

def read_file(file_name):
  """ Opens and reads a file. Helpful for mocking out builtin
      functions.
  Args:
    file_name: path to file to read
  Returns:
    Contents of file 
  """
  fp = open(file_name, 'r')
  contents = fp.read()
  fp.close()
  return contents

def reverse_lex(ustring):
  """ Strings must be in unicode to reverse the string
    strings are returned in unicode and may not able 
    able to be converted to a regular string

  Args: 
    ustring: String to reverse
  """
  newstr = ""
  for ii in ustring:
    ordinance = ord(ii)
    new_byte = 255 - ordinance
    char = chr(new_byte)
    newstr += char
  return newstr

def reverse_lex_128(ustring):
  """ Certain datastores are unable to store keys with unichars of 
      128 or more this function reflects on 127 and less.

  Args:
    ustring: String to reverse
  """
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
    directory = split_path[0]
    if not os.path.exists(directory): os.mkdir(directory, 0777)
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

def random_string(length):
  """ Returns a string of a given length. 

  Args:
    length: The length of the random string which is returned.
  Returns:
    A random string.
  """
  s = hashlib.sha256()
  ret = "a"
  while len(ret) < length:
    s.update(str(random.random()))
    ret += s.hexdigest()
  return ret[0:length]

def lineno():
  """ Returns the current line number in our program.

  Returns:
    The current line number in our program.
  """
  return inspect.currentframe().f_back.f_lineno


