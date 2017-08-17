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
  """Salts the given password with the provided username and encrypts it.

    Args:
      username: A str representing the username whose password we wish to
        encrypt.
      password: A str representing the password to encrypt.
    Returns:
      The SHA1-encrypted password.
    """
  return hashlib.sha1(username + password).hexdigest()


def get_md5(location):
  """ Get a file's MD5 checksum.

  Args:
    location: A string specifying the location of the file to check.
  Returns:
    A string containing the checksum with hexidecimal encoding.
  """
  md5 = hashlib.md5()
  chunk_size = 64 * 1024
  with open(location, 'rb') as source:
    chunk = source.read(chunk_size)
    while len(chunk) > 0:
      md5.update(chunk)
      chunk = source.read(chunk_size)

  return md5.hexdigest()
