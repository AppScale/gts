import json
import logging
import psutil
import subprocess

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

  def get_cpu_usage(self):
    """ Discovers CPU usage on this node.

    Returns:
      A dictionary containing the idle, system and user percentages.
    """
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

  def get_disk_usage(self):
    """ Discovers disk usage per mount point on this node.

    Returns:
      A dictionary containing free bytes and bytes used per disk
      partition.
    """
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

  def get_memory_usage(self):
    """ Discovers memory usage on this node.

    Returns:
      A dictionary containing memory bytes available and used.
    """
    mem_stats = psutil.virtual_memory()
    mem_stats_dict = { JSONTags.MEMORY :
      {
        JSONTags.AVAILABLE : mem_stats.available,
        JSONTags.USED : mem_stats.used
      }
    }
    logging.debug("Memory stats: {}".format(mem_stats_dict))

    return json.dumps(mem_stats_dict)

  def get_service_summary(self):
    """ Retrieves Monit's summary on this node.

    Returns:
      A dictionary containing Monit's summary as a string.
    """
    monit_stats = subprocess.check_output(["monit", "summary"])

    monit_stats_dict = {}
    for line in monit_stats.split("\n"):
      tokens = " ".join(line.split()).split(" ")
      if 'Process' in tokens:
        process_name = tokens[1][1:tokens[1].rfind("-")]
        process_status = tokens[2].lower()
        monit_stats_dict[process_name] = process_status
    logging.debug("Monit stats: {}".format(monit_stats_dict))

    return json.dumps(monit_stats_dict)

  def get_swap_usage(self):
    """ Discovers swap usage on this node.

    Returns:
      A dictionary containing free bytes and bytes used for swap.
    """
    swap_stats = psutil.swap_memory()
    swap_stats_dict = { JSONTags.SWAP :
      {
        JSONTags.FREE : swap_stats.free,
        JSONTags.USED : swap_stats.used
      }
    }
    logging.debug("Swap stats: {}".format(swap_stats_dict))

    return json.dumps(swap_stats_dict)
