""" 
    AppScale TaskQueue configuration class. It deals with the configuration
    file given with an application 'queue.yaml' and also, when a previous
    version was deployed, the older configuration from the database
"""

import json
import os
import sys 

from kombu import Exchange
from kombu import Queue

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

  # The property index for which we store the queue name.
  APP_NAME = "appname"

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
       
  def create_celery_file(self):
    """ Creates the Celery configuration file describing 
        queues and exchanges for an application.  

    Returns:
      A string representing the full path location of the 
      configuration file.
    """
    # Parse the queue file
    # Compare it with the current queues (get from database)
    # Delete those that don't exist anymore
    # Always have the default queue 
    print self._queue_info_file
    print self._queue_info_db
    """
    for ii in self._queue_info:
      name = self._app_id + "___" + self.DEFAULT_QUEUE_NAME
      if 'name' in self._queue_info[ii]:
        name = self._app_id + "___" + self._queue_info[ii]['name']

      mode = DEFAULT_QUEUE_TYPE
      if 'mode' in self._queue_info[ii]:
        mode = self._queue_info[ii]['mode']

      rate = DEFAULT_PROCESS_RATE
      if 'rate' in self._queue_info[ii]:
        rate = self._queue_info[ii]['rate'] 
    """  
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
