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


