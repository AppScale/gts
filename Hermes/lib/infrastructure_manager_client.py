#!/usr/bin/env python


# General-purpose Python library imports
import os
import socket
import signal
import ssl
import sys
import time
import yaml


# Third-party imports
import SOAPpy


# AppScale-specific imports
from custom_exceptions import InfrastructureManagerException


class InfrastructureManagerClient:
  """InfrastructureManagerClient provides callers with an interface to
  AppScale's InfrastructureManager daemon.

  """


  # The port that the InfrastructureManager runs on, by default.
  SERVER_PORT = 17444


  # The number of seconds we should wait for when waiting for the UserAppServer
  # to start up.
  WAIT_TIME = 10


  # The max number of seconds we should wait for when waiting for the
  # UserAppServer to start up. We'll give up after this.
  MAX_RETRIES = 100


  # The message that an AppController can return if callers do not authenticate
  # themselves correctly.
  BAD_SECRET_MESSAGE = {'success': False, 'reason': 'bad secret'}

  # The number of times we should retry SOAP calls in case of failures.
  DEFAULT_NUM_RETRIES = 5


  # The maximum amount of time we should wait before timing out the request.
  DEFAULT_TIMEOUT = 10


  # The maximum amount of time we should wait before timing out requests that take longer.
  LONGER_TIMEOUT = 20


  def __init__(self, host, secret):
    """Creates a new AppControllerClient.

    Args:
      host: The location where an InfrastructureManager can be found.
      secret: A str containing the secret key, used to authenticate this client
        when talking to remote InfrastructureManagers.
    """
    self.host = host
    self.server = SOAPpy.SOAPProxy('https://%s:%s' % (host,
      self.SERVER_PORT))
    self.secret = secret

    # Disable certificate verification for Python 2.7.9.
    if hasattr(ssl, '_create_unverified_context'):
      ssl._create_default_https_context = ssl._create_unverified_context


  def call(self, retries, function, *args):
    """Runs the given function, retrying it if a transient error is seen.

    Args:
      retries: The number of times to retry.
      function: The function that should be executed.
      *args: The arguments that will be passed to function.
    Returns:
      The return value of function(*args).
    Raises:
      AppControllerException: If the AppController we're trying to connect to is
        not running at the given IP address, or if it rejects the SOAP request.
    """
    if retries <= 0:
      raise InfrastructureManagerException(
        "Ran out of retries calling the AppController. ")

    try:
      result = function(*args)

      if result == self.BAD_SECRET_MESSAGE:
        raise InfrastructureManagerException(
          "Could not authenticate successfully" + \
           " to the AppController. You may need to change the keyname in use.")
      else:
        return result
    except (ssl.SSLError, socket.error):
      sys.stderr.write("Saw SSL exception when communicating with the " \
                       "AppController, retrying momentarily.")
      return self.call(retries - 1, function, *args)


  def get_cpu_usage(self):
    return yaml.safe_load(self.call(self.DEFAULT_NUM_RETRIES,
                                    self.server.get_cpu_usage,
                                    self.secret))

  def get_disk_usage(self):
    return yaml.safe_load(self.call(self.DEFAULT_NUM_RETRIES,
                                    self.server.get_disk_usage,
                                    self.secret))

  def get_memory_usage(self):
    return yaml.safe_load(self.call(self.DEFAULT_NUM_RETRIES,
                                    self.server.get_memory_usage,
                                    self.secret))

  def get_service_summary(self):
    return yaml.safe_load(self.call(self.DEFAULT_NUM_RETRIES,
                                    self.server.get_service_summary,
                                    self.secret))

  def get_swap_usage(self):
    return yaml.safe_load(self.call(self.DEFAULT_NUM_RETRIES,
                                    self.server.get_swap_usage,
                                    self.secret))

  def get_loadavg(self):
    return yaml.safe_load(self.call(self.DEFAULT_NUM_RETRIES,
                                    self.server.get_loadavg,
                                    self.secret))

  def get_system_stats(self):
    return yaml.safe_load(self.call(self.DEFAULT_NUM_RETRIES,
                                    self.server.get_system_stats,
                                    self.secret))
