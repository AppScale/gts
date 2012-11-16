# Programmer: Navraj Chohan <nlake44@gmail.com>

# These are invalid characters for an application name
BAD_APP_NAME_CHARS = '/\\!~?<>:{}@#$%^|&*()+=;'

# These characters are flagged as possible security threats
UNSECURE_CHARS = '!?<>:{}@#$%^|&*()+=;'

def is_app_name_valid(app_name):
  """ Validates an application by checking if it contains certain 
      characters.
  Args:   
    app_name: The name of the application
  Returns: 
    True if valid, false if invalid
  """

  for ii in BAD_APP_NAME_CHARS:
    if ii in app_name:
      return False
  return True  

def is_string_secure(string):
  """ Validates that this string does not contain any possible characters
      that are indicative of a security breach.
  Args:
    string: The string to validate
  Returns: 
    True if the string is valid, False otherwise
  """
  for ii in UNSECURE_CHARS:
    if ii in string:
      return False
  return True  

