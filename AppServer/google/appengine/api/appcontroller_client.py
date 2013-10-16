#!/usr/bin/env python
# Programmer: Chris Bunch (chris@appscale.com)
# Adapted from Hiranya's version


# General-purpose Python library imports
import json
import logging
import re
import socket
import ssl
import sys
import time


# Third-party imports
import SOAPpy


# AppScale-specific imports
from custom_exceptions import AppControllerException
from custom_exceptions import TimeoutException


class AppControllerClient():
  """AppControllerClient provides callers with an interface to AppScale's
  AppController daemon.

  The AppController is a dispatching service that is responsible for starting
  API services on each node in an AppScale deployment. Callers may talk to
  the AppController to get information about the number of nodes in the
  deployment as well as what services each node runs.
  """


  # The port that the AppController runs on by default.
  PORT = 17443


  # The number of seconds we should wait for when waiting for the UserAppServer
  # to start up.
  WAIT_TIME = 10


  # The message that an AppController can return if callers do not authenticate
  # themselves correctly.
  BAD_SECRET_MESSAGE = 'false: bad secret'


  # The number of times we should retry SOAP calls in case of failures.
  DEFAULT_NUM_RETRIES = 0


  # The number of seconds we should wait when executing SOAP calls with a
  # timeout.
  DEFAULT_TIMEOUT_TIME = 10


  def __init__(self, host, secret):
    """Creates a new AppControllerClient.

    Args:
      host: The location where an AppController can be found.
      secret: A str containing the secret key, used to authenticate this client
        when talking to remote AppControllers.
    """
    self.host = host
    self.server = SOAPpy.SOAPProxy('https://{0}:{1}'.format(host, self.PORT))
    self.secret = secret


  def run_with_timeout(self, timeout_time, default, num_retries, function,
    *args):
    """Runs the given function, aborting it if it runs too long.

    Args:
      timeout_time: The number of seconds that we should allow function to
        execute for.
      default: The value that should be returned if the timeout is exceeded.
      num_retries: The number of times we should retry the SOAP call if we see
        an unexpected exception.
      function: The function that should be executed.
      *args: The arguments that will be passed to function.
    Returns:
      Whatever function(*args) returns if it runs within the timeout window, and
        default otherwise.
    Raises:
      AppControllerException: If the AppController we're trying to connect to is
        not running at the given IP address, or if it rejects the SOAP request.
    """
    def timeout_handler(_, __):
      """Raises a TimeoutException if the function we want to execute takes
      too long to run.

      Raises:
        TimeoutException: If a SIGALRM is raised.
      """
      raise TimeoutException()

    try:
      retval = function(*args)
    except TimeoutException:
      return default
    except socket.error as exception:
      if num_retries > 0:
        sys.stderr.write("Saw socket exception {0} when communicating with the " \
          "AppController, retrying momentarily. Message is {1}".format(exception, exception.msg))
        return self.run_with_timeout(timeout_time, default, num_retries - 1,
          function, *args)
      else:
        raise exception
    except ssl.SSLError:
      sys.stderr.write("Saw SSL exception when communicating with the " \
        "AppController, retrying momentarily.")
      return self.run_with_timeout(timeout_time, default, num_retries, function,
        *args)
    except Exception as exception:
      sys.stderr.write("Saw exception {0} when communicating with the " \
        "AppController.".format(str(exception)))
      return default

    if retval == self.BAD_SECRET_MESSAGE:
      raise AppControllerException("Could not authenticate successfully" + \
        " to the AppController. You may need to change the keyname in use.")

    return retval


  def set_parameters(self, locations, credentials, app=None):
    """Passes the given parameters to an AppController, allowing it to start
    configuring API services in this AppScale deployment.

    Args:
      locations: A list that contains the first node's IP address.
      credentials: A list that contains API service-level configuration info,
        as well as a mapping of IPs to the API services they should host
        (excluding the first node).
      app: A list of the App Engine apps that should be started.
    Raises:
      AppControllerException: If the remote AppController indicates that there
        was a problem with the parameters passed to it.
    """
    if app is None:
      app = 'none'

    result = self.run_with_timeout(self.DEFAULT_TIMEOUT_TIME, "Error",
      self.DEFAULT_NUM_RETRIES, self.server.set_parameters,
      locations, credentials, [app], self.secret)
    if result.startswith('Error'):
      raise AppControllerException(result)


  def get_all_public_ips(self):
    """Queries the AppController for a list of all the machines running in this
    AppScale deployment, and returns their public IP addresses.

    Returns:
      A list of the public IP addresses of each machine in this AppScale
      deployment.
    """
    return json.loads(self.run_with_timeout(self.DEFAULT_TIMEOUT_TIME, "[]",
      self.DEFAULT_NUM_RETRIES, self.server.get_all_public_ips, self.secret))


  def get_role_info(self):
    """Queries the AppController to determine what each node in the deployment
    is doing and how it can be externally or internally reached.

    Returns:
      A dict that contains the public IP address, private IP address, and a list
      of the API services that each node runs in this AppScale deployment.
    """
    return json.loads(self.run_with_timeout(self.DEFAULT_TIMEOUT_TIME, "{}",
      self.DEFAULT_NUM_RETRIES, self.server.get_role_info, self.secret))


  def get_status(self):
    """Queries the AppController to learn information about the machine it runs
    on.

    This includes information about the CPU, memory, and disk of that machine,
    as well as what machine that AppController connects to for database access
    (via the UserAppServer).

    Returns:
      A str containing information about the CPU, memory, and disk usage of that
      machine, as well as where the UserAppServer is located.
    """
    return self.run_with_timeout(self.DEFAULT_TIMEOUT_TIME, "", 
      self.DEFAULT_NUM_RETRIES, self.server.status, self.secret)


  def get_api_status(self):
    """Queries the AppController to see what the status of Google App Engine
    APIs are in this AppScale deployment, reported to it by the API Checker.

    APIs can be either 'running', 'failed', or 'unknown' (which typically
    occurs when AppScale is first starting up).

    Returns:
      A dict that maps each API name (a str) to its status (also a str).
    """
    return json.loads(self.run_with_timeout(self.DEFAULT_TIMEOUT_TIME, "{}",
      self.DEFAULT_NUM_RETRIES, self.server.get_api_status, self.secret))


  def get_database_information(self):
    """Queries the AppController to see what database is being used to implement
    support for the Google App Engine Datastore API, and how many replicas are
    present for each piece of data.

    Returns:
      A dict that indicates both the name of the database in use (with the key
      'table', for historical reasons) and the replication factor (with the
      key 'replication').
    """
    return json.loads(self.run_with_timeout(self.DEFAULT_TIMEOUT_TIME, "{}",
      self.DEFAULT_NUM_RETRIES, self.server.get_database_information,
      self.secret))


  def upload_tgz(self, tgz_filename, email):
    """Tells the AppController to use the AppScale Tools to upload the Google
    App Engine application at the specified location.

    Args:
      tgz_filename: A str that points to a .tar.gz file on the local filesystem
        containing the user's Google App Engine application.
      email: A str containing an e-mail address that should be registered as the
        administrator of this application.
    Returns:
      A str that indicates either that the app was successfully uploaded, or the
      reason why the application upload failed.
    """
    timeout_upload_data = json.dumps({
      'status' : 'timed out'
    })

    return json.loads(self.run_with_timeout(self.DEFAULT_TIMEOUT_TIME,
      timeout_upload_data, self.DEFAULT_NUM_RETRIES,
      self.server.upload_tgz_file, tgz_filename, email, self.secret))


  def get_app_upload_status(self, reservation_id):
    """Queries the AppController to see if the App Engine app corresponding to
    the given reservation ID has been successfully uploaded.

    Args:
      reservation_id: A str that corresponds to the App Engine app being
        uploaded, likely given to the caller from the initial upload SOAP call.
    Returns:
      A str with the status of the application being uploaded.
    """
    return self.run_with_timeout(self.DEFAULT_TIMEOUT_TIME, "timed out",
      self.DEFAULT_NUM_RETRIES, self.server.get_app_upload_status,
      reservation_id, self.secret)


  def get_stats(self):
    """Queries the AppController to get server-level statistics and a list of
    App Engine apps running in this cloud deployment across all machines.

    Returns:
      A list of dicts, where each dict contains server-level statistics (e.g.,
        CPU, memory, disk usage) about one machine.
    """
    return json.loads(self.run_with_timeout(self.DEFAULT_TIMEOUT_TIME, "[]",
      self.DEFAULT_NUM_RETRIES, self.server.get_stats_json, self.secret))


  def is_initialized(self):
    """Queries the AppController to see if it has started up all of the API
    services it is responsible for on its machine.

    Returns:
      A bool that indicates if all API services have finished starting up on
      this machine.
    """
    return self.run_with_timeout(self.DEFAULT_TIMEOUT_TIME, False,
      self.DEFAULT_NUM_RETRIES, self.server.is_done_initializing, self.secret)


  def start_roles_on_nodes(self, roles_to_nodes):
    """Dynamically adds the given machines to an AppScale deployment, with the
    specified roles.

    Args:
      A JSON-dumped dict that maps roles to IP addresses.
    Returns:
      The result of executing the SOAP call on the remote AppController.
    """
    return self.run_with_timeout(self.DEFAULT_TIMEOUT_TIME, "Error",
      self.DEFAULT_NUM_RETRIES, self.server.start_roles_on_nodes,
      roles_to_nodes, self.secret)


  def stop_app(self, app_id):
    """Tells the AppController to no longer host the named application.

    Args:
      app_id: A str that indicates which application should be stopped.
    Returns:
      The result of telling the AppController to no longer host the app.
    """
    return self.run_with_timeout(self.DEFAULT_TIMEOUT_TIME, "Error",
      self.DEFAULT_NUM_RETRIES, self.server.stop_app, app_id, self.secret)


  def is_app_running(self, app_id):
    """Queries the AppController to see if the named application is running.

    Args:
      app_id: A str that indicates which application we should be checking
        for.
    Returns:
      True if the application is running, False otherwise.
    """
    return self.run_with_timeout(self.DEFAULT_TIMEOUT_TIME, "Error",
      self.DEFAULT_NUM_RETRIES, self.server.is_app_running, app_id, self.secret)


  def done_uploading(self, app_id, remote_app_location):
    """Tells the AppController that an application has been uploaded to its
    machine, and where to find it.

    Args:
      app_id: A str that indicates which application we have copied over.
      remote_app_location: A str that indicates the location on the remote
        machine where the App Engine application can be found.
    """
    return self.run_with_timeout(self.DEFAULT_TIMEOUT_TIME, "Error",
      self.DEFAULT_NUM_RETRIES, self.server.done_uploading, app_id,
      remote_app_location, self.secret)


  def update(self, apps_to_run):
    """Tells the AppController which applications to run, which we assume have
    already been uploaded to that machine.

    Args:
      apps_to_run: A list of apps to start running on nodes running the App
        Engine service.
    """
    return self.run_with_timeout(self.DEFAULT_TIMEOUT_TIME, "Error",
      self.DEFAULT_NUM_RETRIES, self.server.update, apps_to_run, self.secret)


  def gather_logs(self):
    """ Tells the AppController to copy logs from all machines to a tar.gz file
    stored in the AppDashboard's static file directory, so that users can
    download it.
    """
    return self.run_with_timeout(self.DEFAULT_TIMEOUT_TIME, (False, ""),
      self.DEFAULT_NUM_RETRIES, self.server.gather_logs, self.secret)


  def run_groomer(self):
    """ Tells the AppController to clean up entities in the Datastore that have
    been soft deleted, and to generate statistics about the entities still in
    the Datastore (which can be viewed in the AppDashboard).
    """
    return self.run_with_timeout(self.DEFAULT_TIMEOUT_TIME, "Error",
      self.DEFAULT_NUM_RETRIES, self.server.run_groomer, self.secret)
