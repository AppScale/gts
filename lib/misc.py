# Programmer: Navraj Chohan <nlake44@gmail.com>

import re

# These are invalid characters for an application name
VALID_APP_NAME_CHARS_REGEX = "^[A-Za-z0-9_-]*$"

# These characters are flagged as possible security threats
VALID_CHARS_REGEX = "^[/.A-Za-z0-9_-]*$"

def is_app_name_valid(app_name):
  """ Validates an application by checking if it contains certain 
      characters.

  Args:   
    app_name: The name of the application
  Returns: 
    True if valid, False if invalid
  """
  if re.match(VALID_APP_NAME_CHARS_REGEX, app_name):
    return True
  else:
    return False
   
def is_string_secure(string):
  """ Validates that this string does not contain any possible characters
      that are indicative of a security breach.

  Args:
    string: The string to validate
  Returns: 
    True if the string is valid, False otherwise
  """
  if re.match(VALID_CHARS_REGEX, string):
    return True
  else:
    return False
