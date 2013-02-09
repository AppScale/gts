""" 
    AppScale TaskQueue configuration class. It deals with the configuration
    file given with an application 'queue.yaml' and also, when a previous
    version was deployed, the older configuration from the database
"""

import json
import os
import re
import sys 

sys.path.append(os.path.join(os.path.dirname(__file__), "../AppServer"))
from google.appengine.api import queueinfo
from google.appengine.api import datastore
from google.appengine.api import datastore_types

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib"))
import file_io

class TaskQueueConfig():
  """ Contains configuration of the TaskQueue system. """

  # The kind name for storing Queue info.
  QUEUE_KIND = "__queue__"

  # Enum code for broker to use
  RABBITMQ = 0

  # The default YAML used if a queue.yaml is not supplied.
  DEFAULT_QUEUE_YAML = \
"""
queue:
- name: default
  rate: 5/s
"""
  
  # The application id used for storing queue info.
  APPSCALE_QUEUES = "__appscale_queues__"

  # The property index for which we store the queue info.
  QUEUE_INFO = "queueinfo"

  # The property index for which we store app name.
  APP_NAME = "appname"

  # Queue info location codes
  QUEUE_INFO_DB = 0
  QUEUE_INFO_FILE = 1 

  # Location of all celery configuration files
  CELERY_CONFIG_DIR = '/etc/appscale/celery/configuration/'

  # Location of all celery workers scripts
  CELERY_WORKER_DIR = '/etc/appscale/celery/workers/'

  # Directory with the task templates
  TEMPLATE_DIR = './templates/'

  # The location of a header of a queue worker script
  HEADER_LOC = TEMPLATE_DIR + 'header.py'
  
  # The location of the task template code
  TASK_LOC = TEMPLATE_DIR + 'task.py'

  MAX_QUEUE_NAME_LENGTH = 100

  QUEUE_NAME_PATTERN = r'^[a-zA-Z0-9_]{1,%s}$' % MAX_QUEUE_NAME_LENGTH

  QUEUE_NAME_RE = re.compile(QUEUE_NAME_PATTERN)


  def __init__(self, broker, app_id):
    """ Configuration constructor. 

    Args:
      broker: The broker to use.
      app_id: Application id.
    """
    self._broker = broker
    self._broker_location = self.__broker_location(broker)
    self._app_id = app_id
    self._queue_info_db = None
    self._queue_info_file = None
    file_io.mkdir(self.CELERY_CONFIG_DIR)
    file_io.mkdir(self.CELERY_WORKER_DIR)

  def load_queues_from_file(self, queue_file):
    """ Parses the queue.yaml file of an application
        and loads it into the class.
   
    Args:
      queue_file: Full path of a queue file.
    Returns:
      A dictionary of the queue settings.
    """
    info = ""
    try:
      info = file_io.read(queue_file)
    except IOError:
      info = self.DEFAULT_QUEUE_YAML

    queue_info = queueinfo.LoadSingleQueue(info).ToDict()

    # We add in the default queue if its not already in there.
    has_default = False
    for queue in queue_info['queue']:
      if queue['name'] == 'default':
        has_default = True
    if not has_default:
      queue_info['queue'].append({'rate':'5/s', 'name': 'default'})

    self._queue_info_file = queue_info
    return queue_info 

  def get_file_queue_info(self):
    """ Retrives the queues declared in the queue.yaml 
        configuration. 
   
    Returns:
      A dictionary representing the queues for this application.
    """
    return self._queue_info_file

  def get_db_queue_info(self):
    """ Retrives the queues for this application configuration. 
   
    Returns:
      A dictionary representing the  
    """
    return self._queue_info_db

  def __get_queues_from_db(self):
    """ Retrives queue info from the database. 

    Returns:
      A dictionary representation of queues. 
    """
    queues_key = datastore.Key.from_path(self.QUEUE_KIND, 
                                         self._app_id,
                                         _app=self.APPSCALE_QUEUES)
    queues = datastore.Get(queues_key) 
    return json.loads(queues[self.QUEUE_INFO])

  def load_queues_from_db(self):
    """ Gets the current queues stored in the datastore for 
        the current application and loads them into this class. 
 
    Returns:
      A dictionary of queues. 
    """
    self._queue_info_db = self.__get_queues_from_db()
    return self._queue_info_db

  def save_queues_to_db(self):
    """ Stores file queue information into the datastore. 
     
    Raises:
      ValueError: If queue info has not been set. 
    """
    if not self._queue_info_file:
      raise ValueError("Queue info must be set before saving the queues")
    json_queues = json.dumps(self._queue_info_file)
    entity = datastore.Entity(self.QUEUE_KIND, 
                              name=self._app_id,
                              _app=self.APPSCALE_QUEUES)
    entity.update({self.QUEUE_INFO: datastore_types.Blob(json_queues),
                   self.APP_NAME: datastore_types.ByteString(self._app_id)})
    datastore.Put(entity)

  def create_celery_worker_scripts(self, input_type):
    """ Creates the task worker python script. It uses
        a configuration file for setup.

    Args:
      input_type: Whether to use the yaml file or the 
                  database queue info. Default: yaml file.
    Returns: 
      The full path of the worker script.
    """
    queue_info = self._queue_info_file
    if input_type == self.QUEUE_INFO_DB:
      queue_info = self._queue_info_db 

    header_template = file_io.read(self.HEADER_LOC)
    task_template = file_io.read(self.TASK_LOC)
    header_template = header_template.replace("APP_ID", self._app_id)
    script = header_template.replace("CELERY_CONFIGURATION", 
                                     self._app_id) + '\n'
    for queue in queue_info['queue']:
      queue_name = queue['name']  
      # The queue name is used as a function name so replace invalid chars
      queue_name = queue_name.replace('-', '_')
      self.validate_queue_name(queue_name)
      new_task = task_template.replace("QUEUE_NAME", 
                     self.get_queue_function_name(queue_name))
      script += new_task + '\n'

    worker_file = self.get_celery_worker_script_path(self._app_id)
    file_io.write(worker_file, script)
    return worker_file
  
  @staticmethod
  def remove_config_files(app_id):
    """ Removed celery worker and config files.
   
    Args:
      app_id: The application identifer.
    """
    worker_file = TaskQueueConfig.get_celery_worker_script_path(app_id)
    config_file = TaskQueueConfig.get_celery_configuration_path(app_id)
    file_io.delete(worker_file)
    file_io.delete(config_file)

  @staticmethod
  def get_queue_function_name(queue_name):
    """ Returns the function name of a queue which is not the queue name 
        for namespacing and collision reasons.
    Args:
      queue_name: The name of a queue.
    Returns:
      The string representing the function name.
    """
    return "queue___%s" % queue_name 

  @staticmethod
  def get_celery_worker_script_path(app_id):
    """ Returns the full path of the worker script used for celery.
   
    Args:
      app_id: The application identifier.
    Returns:
      A string of the full file name of the worker script.
    """
    return TaskQueueConfig.CELERY_WORKER_DIR + "app__" + app_id + ".py"

  @staticmethod
  def get_celery_worker_module_name(app_id):
    """ Returns the module name of the queue worker script.
   
    Args:
      app_id: The application identifier.
    Returns:
      A string of the module name.
    """
    return "app__" + app_id 


  @staticmethod
  def get_celery_configuration_path(app_id):
    """ Returns the full path of the configuration used for celery.
   
    Args:
      app_id: The application identifier.
    Returns:
      A string of the full file name of the configuration file.
    """
    return TaskQueueConfig.CELERY_CONFIG_DIR + app_id + ".py"


  def create_celery_file(self, input_type):
    """ Creates the Celery configuration file describing 
        queues and exchanges for an application. Uses either
        the queue.yaml input or what was stored in the 
        datastore to create the celery file. 

    Args:
      input_type: Whether to use the yaml file or the 
                  database queue info. Default: yaml file.
    Returns:
      A string representing the full path location of the 
      configuration file.
    """
    queue_info = self._queue_info_file
    if input_type == self.QUEUE_INFO_DB:
      queue_info = self._queue_info_db 
 
    celery_queues = []
    celery_annotations = []
    for queue in queue_info['queue']:
      if 'mode' in queue and queue['mode'] == "pull":
        continue # celery does not handle pull queues
      
      celery_queues.append("Queue('"+ queue['name'] + \
         "', Exchange('" + self._app_id + \
         "'), routing_key='" + queue['name'] + "'),")

      rate_limit = queue['rate']
      celery_annotations.append("'" + self._app_id + "." +\
         queue['name'] + "': {'rate_limit': '" + rate_limit + "'},")

    celery_queues = '\n'.join(celery_queues)
    celery_annotations = '\n'.join(celery_annotations)
    config = \
"""
from kombu import Exchange
from kombu import Queue
CELERY_QUEUES = (
"""
    config += celery_queues
    config += \
"""
)
CELERY_ANNOTATIONS = {
"""
    config += celery_annotations
    config += \
"""
}
# 30 days in seconds
CELERY_TASK_RESULT_EXPIRES = 29592000
"""
    config_file = self._app_id + ".py" 
    file_io.write(self.CELERY_CONFIG_DIR + config_file, config)
    return self.CELERY_CONFIG_DIR + config_file

  def __broker_location(self, broker):
    """ Gets the broker location connection string.
    
    Args:
      broker: The broker enum value.
    Returns:
      A broker connection string.
    Raises:
      NotImplementedError: If the broker is not implemented
    """ 
    if broker == self.RABBITMQ:
      from brokers import rabbitmq
      return rabbitmq.get_connection_string()
    else:
      raise NotImplementedError(
              "The given broker of code %d is not implemented" % broker)

  def get_broker_string(self):
    """ Gets the broker connection string.

    Returns:
      A string which tells of the location of the configured broker.
    """
    return self._broker_location

  def validate_queue_name(self, queue_name):
    """ Validates the queue name to make sure it can be used as a function name.
    
    Args:
      queue_name: A string representing a queue name.
    Raises:
      NameError if the name is invalid.
    """
    if not self.QUEUE_NAME_RE.match(queue_name):
      raise NameError("Queue name %s did not match the regex %s" %\
           (queue_name, self.QUEUE_NAME_PATTERN))
