# Programmer: Navraj Chohan
import os

""" 
This file contains functions for doing file IO operations. Many 
of the functions serve as wrapper for easy mocking.
"""

def read(file_name):
  """ Opens and reads a file, returning the contents of the file
  
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
