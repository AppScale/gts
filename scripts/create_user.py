""" This script creates a new user. Fails if the user already exists. """

import hashlib
import M2Crypto
import os
import SOAPpy
import string
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib"))
import appscale_info
import constants

def random_password(length=10):
  """ Generates a random password.

  Args:
    lenght: An int, the number of characters in the password.
  Returns:
    A str of random characters.
  """
  chars = string.ascii_uppercase + string.digits + string.ascii_lowercase
  password = ''
  for i in range(length):
    password += chars[ord(M2Crypto.m2.rand_bytes(1)) % len(chars)]
  return password

def get_soap_accessor():
  """ Returns the SOAP server accessor to deal with application and users.

  Returns:
    A soap server accessor.
  """
  db_ip = appscale_info.get_db_master_ip()
  bindport = constants.UA_SERVER_PORT
  return SOAPpy.SOAPProxy("https://{0}:{1}".format(db_ip, bindport))

def create_new_user(server, email, password):
  """ Creates a new user.

  Args:
    server: A SOAP server accessor.
    email: A str, the user email.
    password: A str, the user password. 
  Returns:
    True on success, False otherwise.
  """
  secret = appscale_info.get_secret()
  ret = server.commit_new_user(email, password, "user", secret)
  return not ret.startswith("Error:")

def does_user_exist(email, server):
  """ Checks to see if a user already exists. 

  Args:
    email: A str, an email address to check.
    server: A SOAP server accessor.
  Returns:
    True if the user exists, False otherwise.
  """
  secret = appscale_info.get_secret()
  return server.does_user_exist(email, secret) == "true"

def usage():
  print ""
  print "Creates a new user in AppScale."
  print "Args: email address"
  print ""
  print "Examples:"
  print "  python create_user.py bob@appscale.com"
  print ""

def is_valid_email(email):
  """ Very simple validation of an email address. 

  Args:
    email: A str, the email address to validate.
  Returns:
    True if the email is valid, False otherwise.
  """
  return "@" in email and "." in email

if __name__ == "__main__":
  total = len(sys.argv)
  if total != 2:
    usage() 
    exit(1)

  email = sys.argv[1]

  if not is_valid_email(email):
    print "Email address is invalid. Please try again."
    exit(1)
 
  new_password = random_password()

  server = get_soap_accessor()
  if does_user_exist(email, server):
    print "User already exists."
    exit(1)

  print "Creating user..."
  hash_password = hashlib.sha1(email + new_password).hexdigest()
  create_new_user(server, email, hash_password)

  print "The new password for {0} is: {1}".format(email, new_password)
  print "Store this password in a safe place."
