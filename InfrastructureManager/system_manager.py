import json
import logging
import psutil
import subprocess

from infrastructure_manager import InfrastructureManager
from utils import utils

MOUNTPOINT_WHITELIST = ['/', '/opt/appscale', '/opt/appscale/backups',
  '/opt/appscale/cassandra', '/var/apps']

class JSONTags(object):
  # CPU related JSON tags.
  CPU = "cpu"
  IDLE = "idle"
  SYSTEM = "system"
  USER = "user"
  # Disk related JSON tags.
  DISK = "disk"
  FREE = "free"
  USED = "used"
  # Memory related JSON tags.
  MEMORY = "memory"
  AVAILABLE = "available"
  # SWAP related JSON tags.
  SWAP = "swap"

class SystemManager():
  """ SystemManager class is the entry point for queries regarding system stats.

  This service reports statistics about disk, memory and CPU usage,
  Monit summary, and number of running appservers, if any.
  """

  def __init__(self):
    self.secret = utils.get_secret()

  def get_cpu_usage(self, secret):
    """ Discovers CPU usage on this node.

    Args:
      secret: The secret of the deployment; used for authentication.
    Returns:
      A dictionary containing the idle, system and user percentages.
    """
    if self.secret != secret:
      return self.__generate_response(False,
        InfrastructureManager.REASON_BAD_SECRET)

    cpu_stats = psutil.cpu_times_percent(percpu=False)
    cpu_stats_dict = { JSONTags.CPU :
      {
        JSONTags.IDLE : cpu_stats.idle,
        JSONTags.SYSTEM : cpu_stats.system,
        JSONTags.USER : cpu_stats.user
      }
    }
    logging.debug("CPU stats: {}".format(cpu_stats_dict))

    return json.dumps(cpu_stats_dict)

  def get_disk_usage(self, secret):
    """ Discovers disk usage per mount point on this node.

    Args:
      secret: The secret of the deployment; used for authentication.
    Returns:
      A dictionary containing free bytes and bytes used per disk
      partition.
    """
    if self.secret != secret:
      return self.__generate_response(False,
        InfrastructureManager.REASON_BAD_SECRET)

    inner_disk_stats_dict = []
    for partition in psutil.disk_partitions(all=True):
      disk_stats = psutil.disk_usage(partition.mountpoint)
      if partition.mountpoint not in MOUNTPOINT_WHITELIST:
        continue
      inner_disk_stats_dict.append({ partition.mountpoint : {
        JSONTags.FREE : disk_stats.free,
        JSONTags.USED : disk_stats.used
      }})
    disk_stats_dict = { JSONTags.DISK : inner_disk_stats_dict }
    logging.debug("Disk stats: {}".format(disk_stats_dict))

    return json.dumps(disk_stats_dict)

  def get_memory_usage(self, secret):
    """ Discovers memory usage on this node.

    Args:
      secret: The secret of the deployment; used for authentication.
    Returns:
      A dictionary containing memory bytes available and used.
    """
    if self.secret != secret:
      return self.__generate_response(False,
        InfrastructureManager.REASON_BAD_SECRET)

    mem_stats = psutil.virtual_memory()
    mem_stats_dict = { JSONTags.MEMORY :
      {
        JSONTags.AVAILABLE : mem_stats.available,
        JSONTags.USED : mem_stats.used
      }
    }
    logging.debug("Memory stats: {}".format(mem_stats_dict))

    return json.dumps(mem_stats_dict)

  def get_service_summary(self, secret):
    """ Retrieves Monit's summary on this node.

    Args:
      secret: The secret of the deployment; used for authentication.
    Returns:
      A dictionary containing Monit's summary as a string.
    """
    if self.secret != secret:
      return self.__generate_response(False,
        InfrastructureManager.REASON_BAD_SECRET)

    monit_stats = subprocess.check_output(["monit", "summary"])

    monit_stats_dict = {}
    for line in monit_stats.split("\n"):
      tokens = " ".join(line.split()).split(" ")
      if 'Process' in tokens:
        process_name = tokens[1][1:-1] # Remove quotes.
        # Only keep the service port to identify distinct app servers.
        if not process_name.startswith("app___"):
          process_name = tokens[1][:process_name.rfind("-")+1]
        process_status = tokens[2].lower()
        monit_stats_dict[process_name] = process_status
    logging.debug("Monit stats: {}".format(monit_stats_dict))

    return json.dumps(monit_stats_dict)

  def get_swap_usage(self, secret):
    """ Discovers swap usage on this node.

    Args:
      secret: The secret of the deployment; used for authentication.
    Returns:
      A dictionary containing free bytes and bytes used for swap.
    """
    if self.secret != secret:
      return self.__generate_response(False,
        InfrastructureManager.REASON_BAD_SECRET)

    swap_stats = psutil.swap_memory()
    swap_stats_dict = { JSONTags.SWAP :
      {
        JSONTags.FREE : swap_stats.free,
        JSONTags.USED : swap_stats.used
      }
    }
    logging.debug("Swap stats: {}".format(swap_stats_dict))

    return json.dumps(swap_stats_dict)

  def __generate_response(self, status, message):
    """ Generate a system manager service response

    Args:
      status:  A boolean value indicating the status.
      message: A str, the reason or failure.

    Returns:
      A dictionary containing the operation response.
    """
    logging.warn("Sending success = {0}, reason = {1}".format(status, message))
    return {'success': status, 'reason': message}
