#!/usr/bin/env python
# Programmer: Chris Bunch, Brian Drawert


# First-party Python imports
import hashlib


class LocalState():
  """LocalState handles all interactions necessary to read and write AppScale
  configuration files on the machine that executes the AppScale Tools.
  """


  @classmethod
  def encrypt_password(cls, username, password):
    """Salts the given password with the provided username and encrypts it.

    Args:
      username: A str representing the username whose password we wish to
        encrypt.
      password: A str representing the password to encrypt.
    Returns:
      The SHA1-encrypted password.
    """
    return hashlib.sha1(username + password).hexdigest()
