# Programmer: Navraj Chohan

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
 
