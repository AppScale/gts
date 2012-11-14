# Programmer: Navraj Chohan
import logging
import os

from flexmock import flexmock

""" 
This file contains functions for doing file IO and logging operations. Many 
of the functions serve as wrapper for easy mocking.
"""

def read(file_name):
  """ Opens and reads a file, returning the contents of the file.
  
  Args:
    file_name: The full path or relative path of the file to read
  Returns:
    String containing the contents
  """

  FILE = open(file_name, "r")
  contents = FILE.read()  
  FILE.close()
  return contents 

def write(file_name, contents):
  """ Opens and writes a file. Will truncate over existing files.
   
  Args:
    file_name: The full path or relative path of the file to write to
  """

  FILE = open(file_name, "w")
  FILE.write(contents)
  FILE.close()

def delete(file_name):
  """ Deletes a given file. 
  
  Args:
    file_name: The name of the file to delete
  """

  os.remove(file_name) 

def exists(file_name):
  """ Checks to see if a file exists.
  
  Args:
    file_name: The file to check if it exists. 
  """

  return os.path.exists(file_path)

def disable_logging():
  """ Mocks out logging for testing output.
  """
  flexmock(logging)\
    .should_receive('error')\
    .and_return() 

  flexmock(logging)\
    .should_receive('warning')\
    .and_return() 

  flexmock(logging)\
    .should_receive('info')\
    .and_return() 

def set_logging_format():
  """ Sets the logging format to have a unified format.
  """

  logging.basicConfig(format=('%(asctime)s %(levelname)s %(filename)s:'\
                              '%(lineno)s %(message)s '))
