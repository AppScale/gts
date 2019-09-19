""" This script creates a new user. Fails if the user already exists. """

import hashlib
import random
import string
import sys

from appscale.common.ua_client import UAClient


def random_password(length=10):
  """ Generates a random password.

  Args:
    length: An int, the number of characters in the password.
  Returns:
    A str of random characters.
  """
  sysrand = random.SystemRandom()
  chars = string.ascii_uppercase + string.digits + string.ascii_lowercase
  return ''.join(sysrand.choice(chars) for _ in range(length))

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
    sys.exit(1)

  email = sys.argv[1]

  if not is_valid_email(email):
    print "Email address is invalid. Please try again."
    sys.exit(1)
 
  new_password = random_password()

  ua_client = UAClient()

  if ua_client.does_user_exist(email):
    print "User already exists."
    sys.exit(1)

  print "Creating user..."
  hash_password = hashlib.sha1(email + new_password).hexdigest()
  ua_client.commit_new_user(email, hash_password, 'user')

  print "The new password for {0} is: {1}".format(email, new_password)
  print "Store this password in a safe place."
