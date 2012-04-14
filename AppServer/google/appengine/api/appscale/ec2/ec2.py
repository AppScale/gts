# See AppScale License
import os
import re
import sys
import time
import urllib

from google.appengine.api import users

"""
  AppScale EC2 API: Gives App Engine users the ability to control Amazon EC2
  nodes. Right now just makes shell calls to the much faster euca2ools, but
  this likely should be refactored to use boto at a later time, which offers
  a much cleaner interface than what we use now.
"""

# since we just shell out right now, the ec2 api is available everywhere
# so always return true 
def can_run_jobs():
  return True

def sanitize(options):
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
  required_vars = ["EC2_HOME", "JAVA_HOME"]
  for var in required_vars:
    if var not in os.environ:
      return var + " was not set. Please set it and try again."

  return None

def ec2_describe_instances(options = {}):
  if users.is_current_user_capable("ec2_api") == False:
    return "this user cannot call the ec2 api"

  errors = ec2_set_environment()
  if errors is not None:
    return errors
  options = sanitize(options)
  cert, pk, ec2_url, s3_url, ec2_access_key, ec2_secret_key = get_credentials()
  command = "EC2_CERT=" + cert + " EC2_PRIVATE_KEY=" + pk + " EC2_URL=" + ec2_url + " S3_URL=" + s3_url + " EC2_ACCESS_KEY=" + ec2_access_key + " EC2_SECRET_KEY=" + ec2_secret_key + " /usr/local/bin/euca-describe-instances "
  for k, v in options.iteritems():
    command = command + " -" + k + " " + v
  command = command + " 2>&1"

  result = os.popen(command).read()
  return result

def ec2_run_instances(options = {}):
  if users.is_current_user_capable("ec2_api") == False:
    return "this user cannot call the ec2 api"

  errors = ec2_set_environment()
  if errors is not None:
    return errors

  options = sanitize(options)
  if "machine" not in options:
    return "EC2_API Error: Options must have a 'machine' field with the AMI to spawn"
  cert, pk, ec2_url, s3_url, ec2_access_key, ec2_secret_key = get_credentials()
  command = "EC2_CERT=" + cert + " EC2_PRIVATE_KEY=" + pk + " EC2_URL=" + ec2_url + " S3_URL=" + s3_url + " EC2_ACCESS_KEY=" + ec2_access_key + " EC2_SECRET_KEY=" + ec2_secret_key + " /usr/local/bin/euca-run-instances " + options['machine']
  for k, v in options.iteritems():
    if k != "machine":
      command = command + " -" + k + " " + v
  command = command + " 2>&1"

  result = os.popen(command).read()
  return result

def ec2_terminate_instances(options = {}):
  if users.is_current_user_capable("ec2_api") == False:
    return "this user cannot call the ec2 api"

  errors = ec2_set_environment()
  if errors is not None:
    return errors

  options = sanitize(options)
  if "ids" not in options:
    return "EC2_API Error: Options must have a 'ids' field with the IDs to kill"

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
  if users.is_current_user_capable("ec2_api") == False:
    return "this user cannot call the ec2 api"

  errors = ec2_set_environment()
  if errors is not None:
    return errors

  options = sanitize(options)
  if "key" not in options:
    return "EC2_API Error: Options must have a 'key' field with the key to add"
  key = options["key"]
  if not isinstance(key, str):
    return "EC2_API Error: 'key' must be a string"

  cert, pk, ec2_url, s3_url, ec2_access_key, ec2_secret_key = get_credentials()
  command = "EC2_CERT=" + cert + " EC2_PRIVATE_KEY=" + pk + " EC2_URL=" + ec2_url + " S3_URL=" + s3_url + " EC2_ACCESS_KEY=" + ec2_access_key + " EC2_SECRET_KEY=" + ec2_secret_key +  " /usr/local/bin/euca-add-keypair "
  for k, v in options.iteritems():
    if k != "key":
      command = command + " -" + k + " " + v
  command = command + " " + key + " 2>&1"

  result = os.popen(command).read()
  return result

def ec2_delete_keypair(options = {}):
  if users.is_current_user_capable("ec2_api") == False:
    return "this user cannot call the ec2 api"

  errors = ec2_set_environment()
  if errors is not None:
    return errors

  options = sanitize(options)
  if "key" not in options:
    return "EC2_API Error: Options must have a 'key' field with the keys to remove"

  key = options["key"]
  if not isinstance(key, str):
    return "EC2_API Error: 'key' must be a string"

  cert, pk, ec2_url, s3_url, ec2_access_key, ec2_secret_key = get_credentials()
  command = "EC2_CERT=" + cert + " EC2_PRIVATE_KEY=" + pk + " EC2_URL=" + ec2_url + " S3_URL=" + s3_url + " EC2_ACCESS_KEY=" + ec2_access_key + " EC2_SECRET_KEY=" + ec2_secret_key + " /usr/local/bin/euca-delete-keypair "
  for k, v in options.iteritems():
    if k != "key":
      command = command + " -" + k + " " + v
  command = command + " " + key + " 2>&1"

  result = os.popen(command).read()
  return result

def ec2_describe_availability_zones(options = {}):
  if users.is_current_user_capable("ec2_api") == False:
    return "this user cannot call the ec2 api"

  errors = ec2_set_environment()
  if errors is not None:
    return errors
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
  if users.is_current_user_capable("ec2_api") == False:
    return "this user cannot call the ec2 api"

  errors = ec2_set_environment()
  if errors is not None:
    return errors

  options = sanitize(options)
  cert, pk, ec2_url, s3_url, ec2_access_key, ec2_secret_key = get_credentials()
  command = "EC2_CERT=" + cert + " EC2_PRIVATE_KEY=" + pk + " EC2_URL=" + ec2_url + " S3_URL=" + s3_url + " EC2_ACCESS_KEY=" + ec2_access_key + " EC2_SECRET_KEY=" + ec2_secret_key + " /usr/local/bin/euca-describe-images "
  for k, v in options.iteritems():
    command = command + " -" + k + " " + v
  command = command + " 2>&1"

  result = os.popen(command).read()
  return result

def ec2_reboot_instances(options = {}):
  if users.is_current_user_capable("ec2_api") == False:
    return "this user cannot call the ec2 api"

  errors = ec2_set_environment()
  if errors is not None:
    return errors

  options = sanitize(options)
  if "ids" not in options:
    return "EC2_API Error: Options must have a 'ids' field with the IDs to reboot"
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
  if users.is_current_user_capable("ec2_api") == False:
    return "this user cannot call the ec2 api"

  user = get_current_user()
  if not user:
    raise NameError('Cannot call write_ec2_creds while not logged in.')
  cred_dir = "/tmp/ec2/" + user.nickname()
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
  if users.is_current_user_capable("ec2_api") == False:
    return "this user cannot call the ec2 api"

  user = get_current_user()
  if not user:
    raise NameError("Cannot call get_credentials while not logged in")

  cred_dir = "/tmp/ec2/" + user.nickname()
  cert = cred_dir + "/cert.pem"
  pk = cred_dir + "/pk.pem"
  ec2_url = get_ec2_url()
  s3_url = get_s3_url()
  ec2_access_key = get_ec2_access_key()
  ec2_secret_key = get_ec2_secret_key()
  return (cert, pk, ec2_url, s3_url, ec2_access_key, ec2_secret_key)

def get_ec2_cert():
  if users.is_current_user_capable("ec2_api") == False:
    return "this user cannot call the ec2 api"

  user = get_current_user()
  if not user:
    raise NameError('Cannot call get_ec2_cert while not logged in.')

  cert_loc = "/tmp/ec2/" + user.nickname() + "/cert.pem"

  contents = None
  if os.path.exists(cert_loc):
    f = open(cert_loc, "r")
    contents = f.read()
    f.close()
  return contents

def get_ec2_pk():
  if users.is_current_user_capable("ec2_api") == False:
    return "this user cannot call the ec2 api"

  user = get_current_user()
  if not user:
    raise NameError('Cannot call get_ec2_pk while not logged in.')

  pk_loc = "/tmp/ec2/" + user.nickname() + "/pk.pem"

  contents = None
  if os.path.exists(pk_loc):
    f = open(pk_loc, "r")
    contents = f.read()
    f.close()
  return contents

def get_ec2_url():
  if users.is_current_user_capable("ec2_api") == False:
    return "this user cannot call the ec2 api"

  user = get_current_user()
  if not user:
    raise NameError('Cannot call get_ec2_url while not logged in.')

  ec2_url_loc = "/tmp/ec2/" + user.nickname() + "/ec2url"

  contents = None
  if os.path.exists(ec2_url_loc):
    f = open(ec2_url_loc, "r")
    contents = f.read()
    f.close()
  return contents

def get_s3_url():
  if users.is_current_user_capable("ec2_api") == False:
    return "this user cannot call the ec2 api"

  user = get_current_user()
  if not user:
    raise NameError('Cannot call get_s3_url while not logged in.')

  s3_url_loc = "/tmp/ec2/" + user.nickname() + "/s3url"

  contents = None
  if os.path.exists(s3_url_loc):
    f = open(s3_url_loc, "r")
    contents = f.read()
    f.close()
  return contents

def get_ec2_access_key():
  if users.is_current_user_capable("ec2_api") == False:
    return "this user cannot call the ec2 api"

  user = get_current_user()
  if not user:
    raise NameError('Cannot call get_ec2_access_key while not logged in.')

  ec2_access_key_loc = "/tmp/ec2/" + user.nickname() + "/ec2accesskey"

  contents = None
  if os.path.exists(ec2_access_key_loc):
    f = open(ec2_access_key_loc, "r")
    contents = f.read()
    f.close()
  return contents

def get_ec2_secret_key():
  if users.is_current_user_capable("ec2_api") == False:
    return "this user cannot call the ec2 api"

  user = get_current_user()
  if not user:
    raise NameError('Cannot call get_ec2_secret_key while not logged in.')

  ec2_secret_key_loc = "/tmp/ec2/" + user.nickname() + "/ec2secretkey"

  contents = None
  if os.path.exists(ec2_secret_key_loc):
    f = open(ec2_secret_key_loc, "r")
    contents = f.read()
    f.close()
  return contents

def remove_ec2_creds():
  if users.is_current_user_capable("ec2_api") == False:
    return "this user cannot call the ec2 api"

  user = get_current_user()
  if not user:
    raise NameError('Cannot call remove_ec2_creds while not logged in.')

  cred_dir = "/tmp/ec2/" + user.nickname()
  os.system("rm -rf " + cred_dir)

