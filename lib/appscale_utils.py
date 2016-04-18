""" Utility functions """

import constants
import hashlib
import random
import string

def random_password_generator():
  """ Generates a random six character password with letters and digits. """
  characters = string.letters + string.digits
  pwd_size = constants.PASSWORD_SIZE
  return ''.join((random.choice(characters)) for x in range(pwd_size))

def encrypt_password(username, password):
  """ Salts the given password with the provided username and encrypts it. """
  return hashlib.sha1(username + password).hexdigest()
