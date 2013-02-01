#!/usr/bin/env python
"""
   Provides a simple interface to interact with 
   other machines (typically, AppScale virtual machines).
   This includes the ability to start services on remote machines 
   and copy files to them.
"""

import socket
import subprocess
import time

class ShellException(Exception):
  """ A special Exception class that should be thrown if a shell command is
      executed and has a non-zero return value.
  """
  pass

# The default port that the ssh daemon runs on.
SSH_PORT = 22


# The options that should be used when making ssh and scp calls.
SSH_OPTIONS = "-o LogLevel=quiet -o NumberOfPasswordPrompts=0 " + \
  "-o StrictHostkeyChecking=no -o UserKnownHostsFile=/dev/null"

def __init__(self):
  """ Constructor. """
  pass

def sleep_until_port_is_open(host, port):
  """Queries the given host to see if the named port is open, and if not,
  waits until it is.

  Args:
    host: A str representing the host whose port we should be querying.
    port: An int representing the port that should eventually be open.
  """
  while not is_port_open(host, port):
    print "Waiting for {0}:{1} to open".format(host, port)
    time.sleep(2)

def is_port_open(host, port):
  """Queries the given host to see if the named port is open.

  Args:
    host: A str representing the host whose port we should be querying.
    port: An int representing the port that should eventually be open.
  Returns:
    True if the port is open, False otherwise.
  """
  try:
    sock = socket.socket()
    sock.connect((host, port))
    return True
  except Exception as exception:
    print str(exception)
    return False

def ssh(host, command, user='root'):
  """Logs into the named host and executes the given command.

  Args:
    host: A str representing the machine that we should log into.
    command: A str representing what to execute on the remote host.
    user: A str representing the user to log in as.
  Returns:
    A str representing the standard output of the remote command and a str
      representing the standard error of the remote command.
  """
  return shell("ssh {0} {1}@{2} '{3}'".format(SSH_OPTIONS, 
                   user, host, command))

def scp(host, source, dest, user='root'):
  """Securely copies a file from this machine to the named machine.

  Args:
    host: A str representing the machine that we should log into.
    source: A str representing the path on the local machine where the
      file should be copied from.
    dest: A str representing the path on the remote machine where the file
      should be copied to.
    user: A str representing the user to log in as.
  Returns:
    A str representing the standard output of the secure copy and a str
      representing the standard error of the secure copy.
  """
  return shell("scp {0} {1} {2}@{3}:{4}".format(SSH_OPTIONS, 
                   source, user, host, dest))

def shell(command):
  """Executes a command on this machine, retrying it up to five times if it
  initially fails.

  Args:
    The command to execute.
  Returns:
    The standard output and standard error produced when the command executes.
  Raises:
    ShellException: If, after five attempts, executing the named command
    failed.
  """
  tries_left = 5
  while tries_left:
    print "shell> {0}".format(command)
    result = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE,
      stderr=subprocess.PIPE)
    result.wait()
    if result.returncode == 0:
      stdout = result.stdout.read()
      stderr = result.stderr.read()
      result.stdout.close()
      result.stderr.close()
      return stdout, stderr
    print "Command failed. Trying again momentarily.".format(command)
    tries_left -= 1
    time.sleep(1)
  raise ShellException('Could not execute command: {0}'.format(command))


