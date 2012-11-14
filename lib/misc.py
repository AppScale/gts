# Programmer: Navraj Chohan <nlake44@gmail.com>

# These are invalid characters for an application name
BAD_APP_NAME_CHARS = "!@#$%^&*()+=;"

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
