# See AppScale License
# Programmer: Chris Bunch


import os
import re
import sys
import time
import urllib


from google.appengine.api import users


EC2_CREDS_PATH = "/tmp/ec2/"


class EC2Exception(Exception):
  """
    EC2Exception is a custom exception type that is thrown whenever method calls
      in the EC2 API are called incorrectly or experience unexpected behaviors.
  """
  pass


"""
  AppScale EC2 API: Gives App Engine users the ability to control Amazon EC2
  nodes. Right now just makes shell calls to the much faster euca2ools, but
  this likely should be refactored to use boto at a later time, which offers
  a much cleaner interface than what we use now.
"""


def can_run_jobs():
  """
    Determines if jobs can be run from this machine, and is primarily used by
      the AppLoadBalancer's status page. Since the euca2ools are installed 
      everywhere and is called locally, it's available from everywhere.
  """
  return True


def ensure_user_is_ec2_authorized():
  """
    Uses the Users API to check the currently logged in user's authorizations,
      raising an exception if they are not authorized to use the EC2 API.

    Raises:
      EC2Exception: If the currently logged in user is not authorized to use the
        EC2 API.

    Returns:
      None: If the currently logged in user is authorized to use the EC2 API.
  """
  if not users.is_current_user_capable("ec2_api"):
    raise EC2Exception("this user cannot call the ec2 api")


def sanitize(options):
  """
    Iterates through the given dict and removes any character that could be
      potentially dangerous to include when exec'ing a shell call. The safest
      way to go for now is just to exclude any non-alphanumeric characters
      (except for dots and dashes, which are acceptable).

    Arguments:
      options: A dict that maps command-line flags to their associated values.

    Returns:
      A dict whose keys and values have had all unacceptable characters removed.
  """
  regex = r"[^\w\d/\.-]"
  pattern = re.compile(regex)
  for k, v in options.iteritems():
    if isinstance(k, str):
      k = pattern.sub('', k)
    if isinstance(v, str):
      v = pattern.sub('', v)
    if v == "-": # need this, as dash means read from stdin
      v = " "
  return options


def ec2_set_environment():
  """
    Validates the given environment for use with the euca2ools.

    Raises:
      EC2Exception: If any required environment variable was not set.

    Returns:
      None, if all required environment variables are set.
  """
  required_vars = ["EC2_HOME", "JAVA_HOME"]
  for var in required_vars:
    if var not in os.environ:
      raise EC2Exception("%s was not set. Please set it and try again." % var)

  return None


def ec2_describe_instances(options = {}):
  """
    A wrapper to euca-describe-instances.

    Arguments:
      options: A dict whose keys are flags to euca-describe-instances, and whose
        values are the values associated with each flag given.

    Raises:
      EC2Exception: If the currently logged in user is not authorized to call
        the EC2 API.

    Returns:
      A string containing the result of the euca-describe-instances call.
  """
  ensure_user_is_ec2_authorized()
  ec2_set_environment()
  options = sanitize(options)
  cert, pk, ec2_url, s3_url, ec2_access_key, ec2_secret_key = get_credentials()
  command = "EC2_CERT=" + cert + " EC2_PRIVATE_KEY=" + pk + " EC2_URL=" + ec2_url + " S3_URL=" + s3_url + " EC2_ACCESS_KEY=" + ec2_access_key + " EC2_SECRET_KEY=" + ec2_secret_key + " /usr/local/bin/euca-describe-instances "
  for k, v in options.iteritems():
    command = command + " -" + k + " " + v
  command = command + " 2>&1"

  result = os.popen(command).read()
  return result


def ec2_run_instances(options = {}):
  """
    A wrapper to euca-run-instances.

    Arguments:
      options: A dict whose keys are flags to euca-run-instances, and whose
        values are the values associated with each flag given.

    Raises:
      EC2Exception: If the currently logged in user is not authorized to call
        the EC2 API, or if the options given do not contain the machine ID to
        start.

    Returns:
      A string containing the result of the euca-run-instances call.
  """
  ensure_user_is_ec2_authorized()
  ec2_set_environment()
  options = sanitize(options)
  if "machine" not in options:
    raise EC2Exception("Options must have a 'machine' field with the AMI to \
      spawn")
  cert, pk, ec2_url, s3_url, ec2_access_key, ec2_secret_key = get_credentials()
  command = "EC2_CERT=" + cert + " EC2_PRIVATE_KEY=" + pk + " EC2_URL=" + ec2_url + " S3_URL=" + s3_url + " EC2_ACCESS_KEY=" + ec2_access_key + " EC2_SECRET_KEY=" + ec2_secret_key + " /usr/local/bin/euca-run-instances " + options['machine']
  for k, v in options.iteritems():
    if k != "machine":
      command = command + " -" + k + " " + v
  command = command + " 2>&1"

  result = os.popen(command).read()
  return result


def ec2_terminate_instances(options = {}):
  """
    A wrapper to euca-terminate-instances.

    Arguments:
      options: A dict whose keys are flags to euca-terminate-instances, and 
        whose values are the values associated with each flag given.

    Raises:
      EC2Exception: If the currently logged in user is not authorized to call
        the EC2 API, or if options does not contain the list of instance ids to
        terminate.

    Returns:
      A string containing the result of the euca-terminate-instances call.
  """
  ensure_user_is_ec2_authorized()
  ec2_set_environment()
  options = sanitize(options)
  if "ids" not in options:
    raise EC2Exception("Options must have a 'ids' field with the IDs to kill")

  ids = options['ids']
  # later, make sure that ids is an array
  cert, pk, ec2_url, s3_url, ec2_access_key, ec2_secret_key = get_credentials()
  command = "EC2_CERT=" + cert + " EC2_PRIVATE_KEY=" + pk + " EC2_URL=" + ec2_url + " S3_URL=" + s3_url + " EC2_ACCESS_KEY=" + ec2_access_key + " EC2_SECRET_KEY=" + ec2_secret_key + " /usr/local/bin/euca-terminate-instances " + " ".join(ids)
  for k, v in options.iteritems():
    if k != "ids":
      command = command + " -" + k + " " + v
  command = command + " 2>&1"
  result = os.popen(command).read()
  return result


def ec2_add_keypair(options = {}):
  """
    A wrapper to euca-add-keypair.

    Arguments:
      options: A dict whose keys are flags to euca-add-keypair, and whose values
        are the values associated with each flag given.

    Raises:
      EC2Exception: If the currently logged in user is not authorized to call
        the EC2 API, or if the given options do not indicate the name of the key
        to create.

    Returns:
      A string containing the result of the euca-add-keypair call.
  """
  ensure_user_is_ec2_authorized()
  ec2_set_environment()
  options = sanitize(options)
  if "key" not in options:
    raise EC2Exception("Options must have a 'key' field with the key to add")
  key = options["key"]
  if not isinstance(key, str):
    raise EC2Exception("'key' must be a string")

  cert, pk, ec2_url, s3_url, ec2_access_key, ec2_secret_key = get_credentials()
  command = "EC2_CERT=" + cert + " EC2_PRIVATE_KEY=" + pk + " EC2_URL=" + ec2_url + " S3_URL=" + s3_url + " EC2_ACCESS_KEY=" + ec2_access_key + " EC2_SECRET_KEY=" + ec2_secret_key +  " /usr/local/bin/euca-add-keypair "
  for k, v in options.iteritems():
    if k != "key":
      command = command + " -" + k + " " + v
  command = command + " " + key + " 2>&1"

  result = os.popen(command).read()
  return result


def ec2_delete_keypair(options = {}):
  """
    A wrapper to euca-delete-keypair.

    Arguments:
      options: A dict whose keys are flags to euca-delete-keypair, and whose
        values are the values associated with each flag given.

    Raises:
      EC2Exception: If the currently logged in user is not authorized to call
        the EC2 API, or if the given options fail to indicate the name of the
        keypair to delete.

    Returns:
      A string containing the result of the euca-delete-keypair call.
  """
  ensure_user_is_ec2_authorized()
  ec2_set_environment()
  options = sanitize(options)
  if "key" not in options:
    raise EC2Exception("Options must have a 'key' field with the keys to \
      remove")

  key = options["key"]
  if not isinstance(key, str):
    raise EC2Exception("'key' must be a string")

  cert, pk, ec2_url, s3_url, ec2_access_key, ec2_secret_key = get_credentials()
  command = "EC2_CERT=" + cert + " EC2_PRIVATE_KEY=" + pk + " EC2_URL=" + ec2_url + " S3_URL=" + s3_url + " EC2_ACCESS_KEY=" + ec2_access_key + " EC2_SECRET_KEY=" + ec2_secret_key + " /usr/local/bin/euca-delete-keypair "
  for k, v in options.iteritems():
    if k != "key":
      command = command + " -" + k + " " + v
  command = command + " " + key + " 2>&1"

  result = os.popen(command).read()
  return result


def ec2_describe_availability_zones(options = {}):
  """
    A wrapper to euca-describe-availability-zones.

    Arguments:
      options: A dict whose keys are flags to euca-describe-availability-zones,
        and whose values are the values associated with each flag given.

    Raises:
      EC2Exception: If the currently logged in user is not authorized to call
        the EC2 API.

    Returns:
      A string containing the result of the euca-describe-availability-zones
        call.
  """
  ensure_user_is_ec2_authorized()
  ec2_set_environment()
  options = sanitize(options)

  euca = ""
  if "euca" in options:
    euca = "verbose"
  cert, pk, ec2_url, s3_url, ec2_access_key, ec2_secret_key = get_credentials()
  command = "EC2_CERT=" + cert + " EC2_PRIVATE_KEY=" + pk + " EC2_URL=" + ec2_url + " S3_URL=" + s3_url + " EC2_ACCESS_KEY=" + ec2_access_key + " EC2_SECRET_KEY=" + ec2_secret_key + " /usr/local/bin/euca-describe-availability-zones " + euca
  for k, v in options.iteritems():
    if k != "euca":
      command = command + " -" + k + " " + v
  command = command + " 2>&1"

  result = os.popen(command).read()
  return result


def ec2_describe_images(options = {}):
  """
    A wrapper to euca-describe-images.

    Arguments:
      options: A dict whose keys are flags to euca-describe-images, and whose
        values are the values associated with each flag given.

    Raises:
      EC2Exception: If the currently logged in user is not authorized to call
        the EC2 API.

    Returns:
      A string containing the result of the euca-describe-images call.
  """
  ensure_user_is_ec2_authorized()
  ec2_set_environment()
  options = sanitize(options)
  cert, pk, ec2_url, s3_url, ec2_access_key, ec2_secret_key = get_credentials()
  command = "EC2_CERT=" + cert + " EC2_PRIVATE_KEY=" + pk + " EC2_URL=" + ec2_url + " S3_URL=" + s3_url + " EC2_ACCESS_KEY=" + ec2_access_key + " EC2_SECRET_KEY=" + ec2_secret_key + " /usr/local/bin/euca-describe-images "
  for k, v in options.iteritems():
    command = command + " -" + k + " " + v
  command = command + " 2>&1"

  result = os.popen(command).read()
  return result


def ec2_reboot_instances(options = {}):
  """
    A wrapper to euca-reboot-instances.

    Arguments:
      options: A dict whose keys are flags to euca-reboot-instances, and whose
        values are the values associated with each flag given.

    Raises:
      EC2Exception: If the currently logged in user is not authorized to call
        the EC2 API, or if the given options fails to include the list of
        instance ids that should be rebooted.

    Returns:
      A string containing the result of the euca-reboot-instances call.
  """
  ensure_user_is_ec2_authorized()
  ec2_set_environment()
  options = sanitize(options)
  if "ids" not in options:
    raise EC2Exception("Options must have a 'ids' field with the IDs to reboot")
  ids = options['ids']
  # later, make sure that ids is an array
  cert, pk, ec2_url, s3_url, ec2_access_key, ec2_secret_key = get_credentials()
  command = "EC2_CERT=" + cert + " EC2_PRIVATE_KEY=" + pk + " EC2_URL=" + ec2_url + " S3_URL=" + s3_url + " EC2_ACCESS_KEY=" + ec2_access_key + " EC2_SECRET_KEY=" + ec2_secret_key + " /usr/local/bin/euca-reboot-instances " + " ".join(ids)
  for k, v in options.iteritems():
    if k != "ids":
      command = command + " -" + k + " " + v
  command = command + " 2>&1"

  result = os.popen(command).read()
  return result


def write_ec2_creds(cert, pk, ec2_url, s3_url, ec2_access_key, ec2_secret_key):
  """
    Writes the given EC2 credentials to a temporary directory on this
      AppServer's local filesystem.

    Arguments:
      cert: A string whose contents are a X509 certificate.
      pk: A string whose contents are a private key.
      ec2_url: A string that corresponds to the EC2_URL to use.
      s3_url: A string that corresponds to the S3_URL to use.
      ec2_access_key: A string that corresponds to the EC2_ACCESS_KEY.
      ec2_secret_key: A string that corresponds to the EC2_SECRET_KEY.

    Raises:
      EC2Exception: If the currently logged in user is not authorized to call
        the EC2 API.

    Returns:
      None: If the currently logged in user is authorized to call the EC2 API.
  """
  ensure_user_is_ec2_authorized()
  user = get_current_user()
  if not user:
    raise NameError('Cannot call write_ec2_creds while not logged in.')
  cred_dir = EC2_CREDS_PATH + user.nickname()
  os.system("mkdir -p " + cred_dir)

  ec2_cert_loc = cred_dir + "/cert.pem"
  f = open(ec2_cert_loc, "w+")
  f.write(cert)
  f.close()

  ec2_pk_loc = cred_dir + "/pk.pem"
  f = open(ec2_pk_loc, "w+")
  f.write(pk)
  f.close()

  ec2_url_loc = cred_dir + "/ec2url"
  f = open(ec2_url_loc, "w+")
  f.write(ec2_url)
  f.close()

  s3_url_loc = cred_dir + "/s3url"
  f = open(s3_url_loc, "w+")
  f.write(s3_url)
  f.close()
  ec2_access_key_loc = cred_dir + "/ec2accesskey"
  f = open(ec2_access_key_loc, "w+")
  f.write(ec2_access_key)
  f.close()

  ec2_secret_key_loc = cred_dir + "/ec2secretkey"
  f = open(ec2_secret_key_loc, "w+")
  f.write(ec2_secret_key)
  f.close()


def get_credentials():
  """
    Reads the local filesystem and returns the currently logged in user's EC2
      credentials.

    Raises:
      EC2Exception: If the currently logged in user is not authorized to call
        the EC2 API.

    Returns:
      A tuple whose values correspond to the currently logged in user's EC2
        credentials.
  """
  ensure_user_is_ec2_authorized()
  user = get_current_user()
  cred_dir = EC2_CREDS_PATH + user.nickname()
  cert = cred_dir + "/cert.pem"
  pk = cred_dir + "/pk.pem"
  ec2_url = get_ec2_url()
  s3_url = get_s3_url()
  ec2_access_key = get_ec2_access_key()
  ec2_secret_key = get_ec2_secret_key()
  return (cert, pk, ec2_url, s3_url, ec2_access_key, ec2_secret_key)


def get_ec2_cert():
  """
    Reads the local filesystem and returns the currently logged in user's EC2
      certificate.

    Raises:
      EC2Exception: If the currently logged in user is not authorized to call
        the EC2 API.

    Returns:
      A string corresponding to the currently logged in user's EC2 certificate.
  """
  ensure_user_is_ec2_authorized()
  user = get_current_user()
  cert_loc = EC2_CREDS_PATH + user.nickname() + "/cert.pem"

  contents = None
  if os.path.exists(cert_loc):
    f = open(cert_loc, "r")
    contents = f.read()
    f.close()
  return contents


def get_ec2_pk():
  """
    Reads the local filesystem and returns the currently logged in user's EC2
      private key.

    Raises:
      EC2Exception: If the currently logged in user is not authorized to call
        the EC2 API.

    Returns:
      A string corresponding to the currently logged in user's EC2 private key.
  """
  ensure_user_is_ec2_authorized()
  user = get_current_user()
  pk_loc = EC2_CREDS_PATH + user.nickname() + "/pk.pem"

  contents = None
  if os.path.exists(pk_loc):
    f = open(pk_loc, "r")
    contents = f.read()
    f.close()
  return contents


def get_ec2_url():
  """
    Reads the local filesystem and returns the currently logged in user's 
      EC2_URL.

    Raises:
      EC2Exception: If the currently logged in user is not authorized to call
        the EC2 API.

    Returns:
      A string corresponding to the currently logged in user's EC2_URL.
  """
  ensure_user_is_ec2_authorized()
  user = get_current_user()
  ec2_url_loc = EC2_CREDS_PATH + user.nickname() + "/ec2url"

  contents = None
  if os.path.exists(ec2_url_loc):
    f = open(ec2_url_loc, "r")
    contents = f.read()
    f.close()
  return contents


def get_s3_url():
  """
    Reads the local filesystem and returns the currently logged in user's 
      S3_URL.

    Raises:
      EC2Exception: If the currently logged in user is not authorized to call
        the EC2 API.

    Returns:
      A string corresponding to the currently logged in user's S3_URL.
  """
  ensure_user_is_ec2_authorized()
  user = get_current_user()
  s3_url_loc = EC2_CREDS_PATH + user.nickname() + "/s3url"

  contents = None
  if os.path.exists(s3_url_loc):
    f = open(s3_url_loc, "r")
    contents = f.read()
    f.close()
  return contents


def get_ec2_access_key():
  """
    Reads the local filesystem and returns the currently logged in user's EC2
      access key.

    Raises:
      EC2Exception: If the currently logged in user is not authorized to call
        the EC2 API.

    Returns:
      A string corresponding to the currently logged in user's EC2 access key.
  """
  ensure_user_is_ec2_authorized()
  user = get_current_user()
  ec2_access_key_loc = EC2_CREDS_PATH + user.nickname() + "/ec2accesskey"

  contents = None
  if os.path.exists(ec2_access_key_loc):
    f = open(ec2_access_key_loc, "r")
    contents = f.read()
    f.close()
  return contents


def get_ec2_secret_key():
  """
    Reads the local filesystem and returns the currently logged in user's EC2
      secret key.

    Raises:
      EC2Exception: If the currently logged in user is not authorized to call
        the EC2 API.

    Returns:
      A string corresponding to the currently logged in user's EC2 secret key.
  """
  ensure_user_is_ec2_authorized()
  user = get_current_user()
  ec2_secret_key_loc = EC2_CREDS_PATH + user.nickname() + "/ec2secretkey"

  contents = None
  if os.path.exists(ec2_secret_key_loc):
    f = open(ec2_secret_key_loc, "r")
    contents = f.read()
    f.close()
  return contents


def remove_ec2_creds():
  """
    Reads the local filesystem and removes the currently logged in user's EC2
      credentials.

    Raises:
      EC2Exception: If the currently logged in user is not authorized to call
        the EC2 API.

    Returns:
      None: If the currently logged in user is authorized to call the EC2 API.
  """
  ensure_user_is_ec2_authorized()
  user = get_current_user()
  cred_dir = EC2_CREDS_PATH + user.nickname()
  os.system("rm -rf " + cred_dir)
