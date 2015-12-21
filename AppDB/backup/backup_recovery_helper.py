""" Backup & Recovery helper functions. """

import logging
import os
import re
import shutil
import SOAPpy
import statvfs
import sys
import tarfile
import time
from os.path import getsize

import backup_exceptions
import backup_recovery_constants
import gcs_helper

from backup_recovery_constants import APP_BACKUP_DIR_LOCATION
from backup_recovery_constants import APP_DIR_LOCATION
from backup_recovery_constants import APP_UPLOAD_CHECK_INTERVAL
from backup_recovery_constants import BACKUP_DIR_LOCATION
from backup_recovery_constants import BACKUP_ROLLBACK_SUFFIX
from backup_recovery_constants import StorageTypes

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib"))
import appscale_info
from constants import APPSCALE_DATA_DIR

sys.path.append(os.path.join(os.path.dirname(__file__), "../../AppDB/AppDashboard/lib"))
from app_dashboard_helper import AppUploadStatuses

from google.appengine.api.appcontroller_client import AppControllerClient

# The port that the SOAP server listens to.
UA_SERVER_PORT = 4343

def delete_local_backup_file(local_file):
  """ Removes the local backup file.

  Args:
    local_file: A str, the path to the backup file to delete.
  """
  if not remove(local_file):
    logging.warning("No local backup file '{0}' to delete. "
      "Skipping...".format(local_file))

def delete_secondary_backup(base_path):
  """ Deletes the secondary backup if it exists, upon successful backup.

  Args:
    base_path: A str, the full path of the backup file without the secondary
      suffix.
  """
  if not remove("{0}{1}".format(base_path, BACKUP_ROLLBACK_SUFFIX)):
    logging.warning("No secondary backup to remove. Skipping...")

def does_file_exist(path):
  """ Checks if the given file is in the local filesystem.

  Args:
    path: A str, the path to the file.
  Returns:
    True on success, False otherwise.
  """
  return os.path.isfile(path)

def enough_disk_space(service):
  """ Checks if there's enough available disk space for a new backup.

  Returns:
    True on success, False otherwise.
  """
  available_space = get_available_disk_space()
  logging.debug("Available space: {0}".format(available_space))

  backup_size = get_backup_size(service)
  logging.debug("Backup size: {0}".format(backup_size))

  if backup_size > available_space * \
    backup_recovery_constants.PADDING_PERCENTAGE:
    logging.warning("Not enough space for a backup.")
    return False
  return True

def get_available_disk_space():
  """ Returns the amount of available disk space under /opt/appscale.

  Returns:
    An int, the available disk space in bytes.
  """
  stat_struct = os.statvfs(os.path.dirname(BACKUP_DIR_LOCATION))
  return stat_struct[statvfs.F_BAVAIL] * stat_struct[statvfs.F_BSIZE]

def get_backup_size(service):
  """ Sums up the size of the snapshot files that consist the backup for the
  given service.

  Args:
    service: A str, the service for which we'll calculate the backup size.
  Returns:
    An int, the total size of the files consisting the backup in bytes.
  """
  backup_files = get_snapshot_paths(service)
  total_size = sum(getsize(file) for file in backup_files)
  return total_size

def get_snapshot_paths(service):
  """ Returns a list of file names holding critical data for the given service.

  Args:
    service: A str, the service for which we're getting the data files.
    Currently there is support for Cassandra and Zookeeper.
  Returns:
    A list of full paths.
  """
  file_list = []
  if service != 'cassandra':
    return file_list

  look_for = 'snapshots'
  data_dir = "{0}{1}".format(APPSCALE_DATA_DIR, service)
  for full_path, _, file in os.walk(data_dir):
    if look_for in full_path:
      file_list.append(full_path)
  logging.debug("List of data paths for '{0}': {1}".format(
    service, file_list))
  return file_list

def move_secondary_backup(base_path):
  """ Moves the secondary backup back in place, if it exists, upon an un
  successful backup attempt.

  Args:
    base_path: A str, the final full path of the backup file after this move.
  """
  source = "{0}{1}".format(base_path, BACKUP_ROLLBACK_SUFFIX)
  target = base_path
  if not rename(source, target):
    logging.warning("No secondary backup to restore. Skipping...")

def mkdir(path):
  """ Creates a dir with the given path.

  Args:
    path: A str, the name of the dir to create.
  Returns:
    True on success, False otherwise.
  """
  try:
    os.mkdir(path)
  except OSError:
    logging.error("OSError while creating dir '{0}'".format(path))
    return False
  return True

def makedirs(path):
  """ Creates a dir with the given path and all directories in between.

  Args:
    path: A str, the name of the dir to create.
  Returns:
    True on success, False otherwise.
  """
  try:
    os.makedirs(path)
  except OSError:
    logging.error("OSError while creating dir '{0}'".format(path))
    return False
  return True

def rename(source, destination):
  """ Renames source file into destination.

  Args:
    source: A str, the path of the file to rename.
    destination: A str, the destination path.
  Returns:
    True on success, False otherwise.
  """
  try:
    os.rename(source, destination)
  except OSError:
    logging.error("OSError while renaming '{0}' to '{1}'".
      format(source, destination))
    return False
  return True

def remove(path):
  """ Deletes the given file from the filesystem.

  Args:
    path: A str, the path of the file to delete.
  Returns:
    True on success, False otherwise.
  """
  try:
    os.remove(path)
  except OSError:
    logging.error("OSError while deleting '{0}'".
      format(path))
    return False
  return True

def tar_backup_files(file_paths, target):
  """ Tars all snapshot files for a given snapshot name.

  Args:
    file_paths: A list of files to tar up.
    target: A str, the full path to the tar file to be created.
  Returns:
    The path to the tar file, None otherwise.
  """
  backup_file_location = target

  # Rename previous backup, if it exists.
  if not rename(backup_file_location, "{0}{1}".
      format(backup_file_location, BACKUP_ROLLBACK_SUFFIX)):
    logging.warning("'{0}' not found. Skipping file rename...".
      format(backup_file_location))

  # Tar up the backup files.
  tar = tarfile.open(backup_file_location, "w:gz")
  for name in file_paths:
    tar.add(name)
  tar.close()

  return backup_file_location

def untar_backup_files(source):
  """ Restores a previous backup into the Cassandra directory structure
  from a tar ball.

  Args:
    source: A str, the path to the backup tar.
  Raises:
    BRException: On untar issues.
  """
  logging.info("Untarring backup file '{0}'...".format(source))
  try:
    tar = tarfile.open(source, "r:gz")
    tar.extractall(path="/")
    tar.close()
  except tarfile.TarError, tar_error:
    logging.exception(tar_error)
    raise backup_exceptions.BRException(
      "Exception while untarring backup file '{0}'.".format(source))
  logging.info("Done untarring '{0}'.".format(source))

def app_backup(storage, full_bucket_name=None):
  """ Saves the app source code at the backups location on the filesystem.

  Args:
    storage: A str, one of the StorageTypes class members.
    full_bucket_name: A str, the name of the backup file to upload to remote
      storage.
  Returns:
    True on success, False otherwise.
  """
  # Create app backups dir if it doesn't exist.
  if not makedirs(APP_BACKUP_DIR_LOCATION):
    logging.warning("Dir '{0}' already exists. Skipping dir creation...".
      format(APP_BACKUP_DIR_LOCATION))

  for dir_path, _, filenames in os.walk(APP_DIR_LOCATION):
    for filename in filenames:
      # Copy source code tars to backups location.
      source = '{0}/{1}'.format(dir_path, filename)
      destination = '{0}/{1}'.format(APP_BACKUP_DIR_LOCATION, filename)
      try:
        shutil.copy(source, destination)
      except:
        logging.error("Error while backing up '{0}'. ".format(source))
        delete_app_tars(APP_BACKUP_DIR_LOCATION)
        return False

      # Upload to GCS.
      if storage == StorageTypes.GCS:
        source = '{0}/{1}'.format(APP_DIR_LOCATION, filename)
        destination = '{0}/apps/{1}'.format(full_bucket_name, filename)
        logging.debug("Destination: {0}".format(destination))
        if not gcs_helper.upload_to_bucket(destination, source):
          logging.error("Error while uploading '{0}' to GCS. ".format(source))
          delete_app_tars(APP_BACKUP_DIR_LOCATION)
          return False
  return True

def app_restore(storage, bucket_name=None):
  """ Restores the app source code from the backups location on the filesystem.

  Args:
    storage: A str, one of the StorageTypes class members.
    bucket_name: A str, the name of the bucket to restore apps from.
  Returns:
    True on success, False otherwise.
  """
  # Create app backups dir if it doesn't exist.
  if not makedirs(APP_BACKUP_DIR_LOCATION):
    logging.warning("Dir '{0}' already exists. Skipping dir creation...".
      format(APP_BACKUP_DIR_LOCATION))

  # Download from GCS to backups location.
  if storage == StorageTypes.GCS:
    objects = gcs_helper.list_bucket(bucket_name)
    for app_path in objects:
      if not app_path.startswith(gcs_helper.APPS_GCS_PREFIX):
        continue

      # Only keep the relative name of the app file.
      # E.g. myapp.tar.gz (app_file) out of apps/myapp.tar.gz (app_path)
      app_file = app_path[len(gcs_helper.APPS_GCS_PREFIX):]
      source = 'gs://{0}/{1}'.format(bucket_name, app_path)
      destination = '{0}/{1}'.format(APP_BACKUP_DIR_LOCATION, app_file)
      if not gcs_helper.download_from_bucket(source, destination):
        logging.error("Error while downloading '{0}' from GCS.".format(source))
        delete_app_tars(APP_BACKUP_DIR_LOCATION)
        return False

  # Deploy apps.
  apps_to_deploy = [os.path.join(APP_BACKUP_DIR_LOCATION, app) for app in
    os.listdir(APP_BACKUP_DIR_LOCATION)]
  if not deploy_apps(apps_to_deploy):
    logging.error("Failed to successfully deploy one or more of the "
      "following apps: {0}".format(apps_to_deploy))
    if storage == StorageTypes.GCS:
      delete_app_tars(APP_BACKUP_DIR_LOCATION)
    return False

  # Clean up downloaded backups for consistency.
  if storage == StorageTypes.GCS:
    delete_app_tars(APP_BACKUP_DIR_LOCATION)

  return True

def delete_app_tars(location):
  """ Deletes applications tars from the designated location.

  Args:
    location: A str, the path to the application tar(s) to be deleted.
  Returns:
    True on success, False otherwise.
  """
  for dir_path, _, filenames in os.walk(location):
    for filename in filenames:
      if not remove('{0}/{1}'.format(dir_path, filename)):
        return False
  return True

def deploy_apps(app_paths):
  """ Deploys all apps that reside in /opt/appscale/apps.

  Args:
    app_paths: A list of the full paths of the apps to be deployed.
  Returns:
    True on success, False otherwise.
  """
  uaserver = SOAPpy.SOAPProxy('https://{0}:{1}'.format(
    appscale_info.get_db_master_ip(), UA_SERVER_PORT))

  acc = AppControllerClient(appscale_info.get_login_ip(),
    appscale_info.get_secret())

  # Wait for Cassandra to come up after a restore.
  time.sleep(15)

  for app_path in app_paths:
    # Extract app ID.
    app_id = app_path[app_path.rfind('/')+1:app_path.find('.')]
    if not app_id:
      logging.error("Malformed source code archive. Cannot complete "
        "application recovery for '{}'. Aborting...".format(app_path))
      return False

    # Retrieve app admin via uaserver.
    app_data = uaserver.get_app_data(app_id, appscale_info.get_secret())

    app_admin_re = re.search("\napp_owner:(.+)\n", app_data)
    if app_admin_re:
      app_admin = app_admin_re.group(1)
    else:
      logging.error("Missing application data. Cannot complete application "
        "recovery for '{}'. Aborting...".format(app_id))
      return False

    file_suffix = re.search("\.(.*)\Z", app_path).group(1)

    logging.warning("Restoring app '{}', from '{}', with owner '{}'.".
      format(app_id, app_path, app_admin))

    upload_info = acc.upload_app(app_path, file_suffix, app_admin)
    status = upload_info['status']
    while status == AppUploadStatuses.STARTING:
      time.sleep(APP_UPLOAD_CHECK_INTERVAL)
      status = acc.get_app_upload_status(upload_info['reservation_id'])
      if status == AppUploadStatuses.ID_NOT_FOUND:
        logging.error('The AppController could not find the reservation ID '
          'for {}.'.format(app_id))
        return False
    if status != AppUploadStatuses.COMPLETE:
      logging.error('Saw status {} when trying to upload {}.'
        .format(status, app_id))
      return False

  return True
