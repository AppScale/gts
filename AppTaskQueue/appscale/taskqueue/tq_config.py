""" AppScale TaskQueue configuration class. It deals with the configuration
file given with an application 'queue.yaml' or 'queue.xml'. """

import json
import os
import sys

from .queue import (
  InvalidQueueConfiguration,
  PullQueue,
  PushQueue
)
from .utils import (
  CELERY_CONFIG_DIR,
  CELERY_WORKER_DIR,
  create_celery_for_app,
  get_celery_configuration_path,
  logger
)
from appscale.common import appscale_info
from appscale.common import file_io
from appscale.common import xmltodict
from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api import queueinfo
from google.appengine.runtime import apiproxy_errors


class TaskQueueConfig():
  """ Contains configuration of the TaskQueue system. """

  # Min concurrency per worker.
  MIN_CELERY_CONCURRENCY = 2

  # Max concurrency per worker.
  MAX_CELERY_CONCURRENCY = 20

  # The default YAML used if a queue.yaml or queue.xml is not supplied.
  DEFAULT_QUEUE_YAML = """
queue:
- name: default
  rate: 5/s
"""

  # Location where celery workers back up state to.
  CELERY_STATE_DIR = '/opt/appscale/celery/'

  # Directory with the task templates.
  TEMPLATE_DIR = os.path.join(
    os.path.dirname(sys.modules['appscale.taskqueue'].__file__), 'templates')

  # The worker script for Celery to use.
  WORKER_MODULE = 'appscale.taskqueue.push_worker'

  # XML configs use "-" while yaml uses "_". These are the tags which
  # need to be converted to match the yaml tags.
  YAML_TO_XML_TAGS_TO_CONVERT = ['bucket-size', 'max-concurrent-request', 
                                 'retry-parameters', 'task-age-limit', 
                                 'total-storage-limit', 'user-email',
                                 'write-email', 'min-backoff-seconds',
                                 'max-backoff-seconds', 'max-doublings',
                                 'task-retry-limit', 'max-concurrent-requests']

  # Tags from queue.xml that are ignored.
  TAGS_TO_IGNORE = ['#text']

  def __init__(self, app_id, db_access=None):
    """ Configuration constructor. 

    Args:
      app_id: The application ID.
      db_access: A DatastoreProxy object.
    """
    self._app_id = app_id
    file_io.mkdir(CELERY_CONFIG_DIR)
    file_io.mkdir(CELERY_WORKER_DIR)
    self.db_access = db_access
    self.queues = self.load_queues_from_file()

  def get_queue_file_location(self, app_id):
    """ Gets the location of the queue.yaml or queue.xml file of a given
    application.

    Args:
      app_id: The application ID.
    Returns:
      The location of the queue.yaml or queue.xml file, and 
      an empty string if it could not be found.
    Raises:
      apiproxy_errors.ApplicationError if multiple invalid files are found.
    """
    app_dir = appscale_info.get_app_path(app_id)

    queue_yaml = 'queue.yaml'
    queue_xml = 'queue.xml'
    
    paths = []
    queue_yaml_detected = False
    queue_xml_detected = False
    for root, sub_dirs, files in os.walk(app_dir):
      for file in files:
        if file == queue_yaml:
          queue_yaml_detected = True
          paths.append(os.path.abspath(os.path.join(root, file)))
        if file == queue_xml:
          queue_xml_detected = True
          paths.append(os.path.abspath(os.path.join(root, file)))

    if not paths:
      return ""

    paths = sorted(paths, key = lambda k : len(k.split(os.sep)))
    if len(paths) == 1:
      return paths[0]

    # If multiple files were detected and it's Python, return
    # the shortest path.
    if queue_yaml_detected:
      return paths[0]
    
    # If multiple files were detected and it's Java, return
    # the first path that contains WEB-INF.
    for path in paths:
      if queue_xml in path and "WEB-INF" in path and queue_xml_detected:
        return path
    
    raise apiproxy_errors.\
      ApplicationError("Multiple unusable queue configuration files detected")

  def load_queues_from_file(self):
    """ Translates an application's queue configuration file to queue objects.
   
    Returns:
      A dictionary mapping queue names to Queue objects.
    Raises:
      ValueError: If queue_file is unable to get loaded.
    """
    using_default = False
    queue_file = ''

    try:
      queue_file = self.get_queue_file_location(self._app_id)
      try:
        info = file_io.read(queue_file)
        logger.info('Found queue file for {} in: {}'.
          format(self._app_id, queue_file))
      except IOError:
        logger.error(
          'No queue file found for {}, using default queue'.format(self._app_id))
        info = self.DEFAULT_QUEUE_YAML
        using_default = True
    except apiproxy_errors.ApplicationError as application_error:
      logger.error(application_error.message)
      info = self.DEFAULT_QUEUE_YAML
      using_default = True

    #TODO handle bad xml/yaml files.
    if queue_file.endswith('yaml') or using_default:
      queue_info = queueinfo.LoadSingleQueue(info).ToDict()
    elif queue_file.endswith('xml'):
      queue_info = self.parse_queue_xml(info)
    else:
      raise ValueError("Unable to load queue information with %s" % queue_file)

    if not queue_info:
      raise ValueError("Queue information with %s not set" % queue_file)

    # We add in the default queue if its not already in there.
    has_default = False
    if 'queue' not in queue_info or len(queue_info['queue']) == 0:
      queue_info = {'queue' : [{'rate':'5/s', 'name': 'default'}]}

    for queue in queue_info['queue']:
      if queue['name'] == 'default':
        has_default = True
    if not has_default:
      queue_info['queue'].append({'rate':'5/s', 'name': 'default'})

    logger.info('Queue for {}:\n{}'.format(self._app_id, queue_info))

    # Discard the invalid queues.
    queues = {}
    for queue in queue_info['queue']:
      if 'mode' in queue and queue['mode'] == 'pull':
        try:
          queues[queue['name']] = PullQueue(queue, self._app_id,
                                            self.db_access)
        except InvalidQueueConfiguration:
          logger.exception('Invalid queue configuration')
      else:
        try:
          queues[queue['name']] = PushQueue(queue, self._app_id)
        except InvalidQueueConfiguration:
          logger.exception('Invalid queue configuration')

    push_queues = [queue for queue in queues.values()
                   if isinstance(queue, PushQueue)]

    # Give PushQueues a Celery interface.
    rates = {queue.name: queue.rate for queue in queues.values()
             if isinstance(queue, PushQueue)}
    celery = create_celery_for_app(self._app_id, rates)
    for queue in push_queues:
      queue.celery = celery

    return queues

  def parse_queue_xml(self, xml_string):
    """ Turns an xml string into a dictionary tree using the same format at
    the yaml conversion.

    Args:
      xml: A string contents in XML format.
    Returns:
      A dictionary tree of the xml.
    """
    xml_dict = xmltodict.parse(xml_string)
    # Now we convert it to look the same as the yaml dictionary.
    converted = {'queue':[]}
    if isinstance(xml_dict['queue-entries']['queue'], list):
      all_queues = xml_dict['queue-entries']['queue']
    else:
      all_queues = [xml_dict['queue-entries']['queue']]

    for queue in all_queues:
      single_queue = {}
      for tag, value in queue.iteritems():
        if tag in self.YAML_TO_XML_TAGS_TO_CONVERT:
          tag = tag.replace('-','_')
        if tag == "retry_parameters":
          retry_dict = {}
          for retry_tag in queue['retry-parameters']:
            value = queue['retry-parameters'][retry_tag]
            if retry_tag in self.YAML_TO_XML_TAGS_TO_CONVERT:
              retry_tag = retry_tag.replace('-','_')
            if retry_tag not in self.TAGS_TO_IGNORE:
              retry_dict[str(retry_tag)] = str(value).strip('\n ')
          single_queue['retry_parameters'] = retry_dict
        elif tag not in self.TAGS_TO_IGNORE:
          single_queue[str(tag)] = str(value).strip('\n ')

      converted['queue'].append(single_queue)

    logger.debug("XML queue info is {0}".format(converted))
    return converted
  
  @staticmethod
  def remove_config_files(app_id):
    """ Removes Celery worker and config files.
   
    Args:
      app_id: The application ID.
    """
    config_file = get_celery_configuration_path(app_id)
    file_io.delete(config_file)

  def create_celery_file(self):
    """ Creates the Celery configuration file describing queues and rates. """
    rates = {queue.name: queue.rate for queue in self.queues.values()
             if isinstance(queue, PushQueue)}
    with open(get_celery_configuration_path(self._app_id), 'w') as config_file:
      json.dump(rates, config_file)

  def get_public_ip(self):
    """ Gets the public IP to which the task calls are routed.

    Returns:
      The primary loadbalancer IP/hostname.
    """
    return appscale_info.get_login_ip()
