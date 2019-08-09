""" Utility functions """

import hashlib
import subprocess

from .constants import KEY_DIRECTORY


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


def ssh(ip_address, keyname, cmd, method=subprocess.check_call):
  """ Runs a command on a given machine.

  Args:
    ip_address: A string containing the IP address of the remote machine.
    keyname: A string containing the deployment's keyname.
    cmd: The command to run on the remote machine.
    method: The function to run the command with.
  Returns:
    The output of the function defined by method.
  """
  key_file = '{}/{}.key'.format(KEY_DIRECTORY, keyname)
  ssh_cmd = ['ssh', '-i', key_file, '-o', 'StrictHostKeyChecking=no',
             ip_address, cmd]
  return method(ssh_cmd)
