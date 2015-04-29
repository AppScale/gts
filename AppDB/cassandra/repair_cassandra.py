""" A test script to repair cassandra. """
import logging

from cassandra_interface import NODE_TOOL
from subprocess import call

def run(): 
  """ Starts up cassandra. """ 
  logging.warning("Repairing Cassandra") 
  call([NODE_TOOL, 'repair'])   
  logging.warning("Done!") 

if __name__ == '__main__':
  run()
