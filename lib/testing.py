""" Functions for testing """
import logging 

from flexmock import flexmock 

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

