""" Google Cloud Storage helper functions. """

import json
import logging
import re
import requests
import subprocess

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
  try:
    fd = open(local_path)
    fd.close()
  except (OSError, IOError) as error:
    logging.error("Error while opening file '{0}' for uploading to GCS. "
      "Error: {1}". format(local_path, str(error)))
    return False

  # Extract bucket and object name for GCS.
  bucket_name, object_name = extract_gcs_tokens(full_object_name)

  # First HTTP request that initiates the upload.
  url = 'https://www.googleapis.com/upload/storage/v1/b/{0}' \
        '/o?uploadType=resumable&name={1}'.format(bucket_name, object_name)
  try:
    response = requests.post(url, verify=False)
    location = response.headers['Location']
    logging.debug("Response Header Location (aka /upload URL): {0}".
      format(location))
  except requests.HTTPError as error:
    logging.error("Error on initial GCS upload".format(error))
    return False

  # Actual file upload.
  new_url = location
  try:
    response = requests.request('PUT', new_url, data=open(local_path, 'rb'),
      headers={'content-type': 'application/x-gzip'},
      timeout=REQUEST_TIMEOUT, verify=False)
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

  # First send HTTP request to retrieve file metadata.
  url = "https://www.googleapis.com/storage/v1/b/{0}/o/{1}".format(
    bucket_name, object_name)
  try:
    response = requests.request('GET', url, verify=False)
    if response.status_code != 200:
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
    logging.error("Malformed GCS path '{0}'. Aborting upload to GCS.".format(
      full_object_name))
    return bucket_name, object_name

  bucket_name = tokens[2]
  object_name = ''
  for token in tokens[3:-1]:
    object_name += token + '/'
  object_name += tokens[-1]

  return bucket_name, object_name
