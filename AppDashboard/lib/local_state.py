#!/usr/bin/env python
# Programmer: Chris Bunch, Brian Drawert


# First-party Python imports
import getpass
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import yaml


# AppScale-specific imports
from appcontroller_client import AppControllerClient
from custom_exceptions import AppScaleException
from custom_exceptions import BadConfigurationException
from custom_exceptions import ShellException


# The version of the AppScale Tools we're running on.
APPSCALE_VERSION = "1.6.9"


class LocalState():
  """LocalState handles all interactions necessary to read and write AppScale
  configuration files on the machine that executes the AppScale Tools.
  """


  # The path on the local filesystem where we can read and write
  # AppScale deployment metadata.
  LOCAL_APPSCALE_PATH = os.path.expanduser("~") + os.sep + ".appscale" + os.sep


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
