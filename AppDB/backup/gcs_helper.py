""" Google Cloud Storage helper functions. """

import json
import logging
import re
import requests
import subprocess
import urllib

import backup_recovery_helper
from backup_recovery_constants import HTTP_OK

# The upload request timeout in seconds (12 hours).
REQUEST_TIMEOUT = 12*60*60

def upload_to_bucket(full_object_name, local_path):
  """ Uploads a file to GCS.

  Args:
    full_object_name: A str, a full GCS object name.
    local_path: A str, the path to a local backup file.

  Returns:
    True on success, False otherwise.
  """
  # Ensure local file is accessible.
  if not backup_recovery_helper.does_file_exist(local_path):
    logging.error("Local file '{0}' doesn't exist. Aborting upload to "
      "GCS.".format(local_path))
    return False

  # Extract bucket and object name for GCS.
  bucket_name, object_name = extract_gcs_tokens(full_object_name)
  if bucket_name == '' or object_name == '':
    logging.error("Full GCS object name is invalid. Aborting upload to "
      "GCS.".format(local_path))
    return False

  # First HTTP request that initiates the upload.
  url = 'https://www.googleapis.com/upload/storage/v1/b/{0}' \
        '/o?uploadType=resumable&name={1}'.format(bucket_name, object_name)
  try:
    response = gcs_post_request(url)
    location = response.headers['Location']
    logging.debug("Response Header Location (aka /upload URL): {0}".
      format(location))
  except requests.HTTPError as error:
    logging.error("HTTPError on getting GCS session ID. Error: {0}".
      format(error))
    return False
  except KeyError as key_error:
    logging.error("KeyError on getting GCS session ID. Error: {0}.".
      format(key_error))
    return False

  # Actual file upload.
  new_url = location
  try:
    response = gcs_put_request(new_url, local_path)
    logging.debug("Final GCS response: {0}".format(str(response)))
  except requests.HTTPError as error:
    logging.error("Error on initial GCS upload".format(error))
    return False

  logging.info("Successfully uploaded '{0}' to GCS. "
    "GCS object name is '{1}'.".format(local_path, full_object_name))
  return True

def download_from_bucket(full_object_name, local_path):
  """ Downloads a file from GCS.

  Args:
    full_object_name: A str, a full GCS object name.
    local_path: A str, the path to a local backup file.
  Returns:
    True on success, False otherwise.
  """
  # Extract bucket and object name for GCS.
  bucket_name, object_name = extract_gcs_tokens(full_object_name)
  if bucket_name == '' or object_name == '':
    logging.error("Full GCS object name is invalid. Aborting download from "
      "GCS.".format(local_path))
    return False

  # First send HTTP request to retrieve file metadata.
  url = "https://www.googleapis.com/storage/v1/b/{0}/o/{1}".format(
    bucket_name, urllib.quote_plus(object_name))
  try:
    response = gcs_get_request(url)
    if response.status_code != HTTP_OK:
      logging.error("Error on retrieving GCS file metadata. Status code: {0}".
        format(response.status_code))
      return False

    content = json.loads(response.content)
    logging.debug("GCS object metadata received: {0}".format(str(response)))
  except requests.HTTPError as error:
    logging.error("Error on retrieving GCS file metadata. Error: {0}".
      format(error))
    return False

  # Check if there is enough disk space available.
  try:
    available_space = re.sub('\s\s+', ' ', subprocess.check_output(['df',
      '/opt/appscale/backups']).split('\n')[1]).split(' ')[3]
  except subprocess.CalledProcessError as called_process_error:
    logging.error("Error while determining available disk space. Error: {0}".
      format(called_process_error))
    return False

  # Compare to GCS file size.
  if not content['size'] < available_space:
    logging.error('Not enough space on the VM to download a backup.')
    return False

  # Invoke 'wget' to retrieve the resource and store to local_path.
  try:
    logging.debug("Downloading GCS object: wget -O {0} {1}".format(
      local_path, content['mediaLink']))
    subprocess.check_output(['wget', '-O', local_path, content['mediaLink']])
  except subprocess.CalledProcessError as called_process_error:
    logging.error("Error while downloading file from GCS. Error: {0}".
      format(called_process_error))
    return False

  logging.info("Successfully downloaded '{0}' from GCS. "
    "Local file name is '{1}'.".format(full_object_name, local_path))
  return True

def extract_gcs_tokens(full_object_name):
  """ Extracts the bucket and object name from a full GCS path.

  Args:
    full_object_name: A str, a full GCS object name.
  Returns:
    A tuple of the form (bucket_name, object_name).
  """
  bucket_name = None
  object_name = None

  tokens = full_object_name.split('/')
  if len(tokens) < 3:
    logging.error("Malformed GCS path '{0}'. Aborting GCS operation.".format(
      full_object_name))
    return bucket_name, object_name

  bucket_name = tokens[2]
  object_name = ''
  for token in tokens[3:-1]:
    object_name += token + '/'
  object_name += tokens[-1]

  return bucket_name, object_name

def gcs_get_request(url):
  """ Performs a GET request to the given url.

  Args:
    url: A str, the URL to POST to.
  Raises:
    HTTPError if the resource cannot be reached.
  """
  return requests.request('GET', url, verify=False)

def gcs_post_request(url):
  """ Performs a POST request to the given url.

  Args:
    url: A str, the URL to POST to.
  Raises:
    HTTPError if the resource cannot be reached.
  """
  return requests.request('POST', url, verify=False)

def gcs_put_request(url, local_path):
  """ Performs a PUT request to the given url.

  Args:
    url: A str, the URL to send data to.
  Raises:
    HTTPError if the resource cannot be reached.
  """
  return requests.request('PUT', url, data=open(local_path, 'rb'),
    headers={'content-type': 'application/x-gzip'},
    timeout=REQUEST_TIMEOUT, verify=False)

def list_bucket(bucket_name):
  """ Lists all the files that are in the designated GCS bucket.

  Args:
    bucket_name: A str, the name of the GCS bucket to look up.
  Returns:
    A list of str, the names of the files in the bucket.
  """
  url = "https://www.googleapis.com/storage/v1/b/{0}/o".\
    format(bucket_name)
  try:
    response = gcs_get_request(url)
    if response.status_code != HTTP_OK:
      logging.error("Error on listing objects in GCS bucket: {0}. "
        "Error: {1}".format(bucket_name, response.status_code))
      return []

    content = json.loads(response.content)
  except requests.HTTPError as error:
    logging.error("Error on listing objects in GCS bucket: {0}. Error: {1}".
      format(bucket_name, error))
    return []

  if 'items' not in content.keys():
    return []

  objects = []
  for item in content['items']:
    objects.append(item['name'])

  logging.debug("Bucket contents: {0}".format(objects))
  return objects
