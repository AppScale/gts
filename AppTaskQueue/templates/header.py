""" Implements a the task queue worker and routing. This is just
    a template and not the actual script which is run. Actual scripts 
    can be found in /etc/appscale/celery/scripts.

    Find and replace the following:
    APP_ID: Set this to the current application ID.
    CELERY_CONFIGURATION: The name of the celery configuration file.
"""
import datetime
import httplib
import os
import sys
import yaml

def setup_environment():
  ENVIRONMENT_FILE = "/etc/appscale/environment.yaml"
  FILE = open(ENVIRONMENT_FILE)
  env = yaml.load(FILE.read())
  APPSCALE_HOME = env["APPSCALE_HOME"]
  sys.path.append(APPSCALE_HOME + "/AppTaskQueue")
  sys.path.append(APPSCALE_HOME + "/AppServer")
  sys.path.append(APPSCALE_HOME + "/lib")

setup_environment()
from celery import Celery
from celery.utils.log import get_task_logger

from urlparse import urlparse

from tq_config import TaskQueueConfig
from tq_lib import TASK_STATES
from distributed_tq import TaskName

import appscale_info
import constants

from google.appengine.runtime import apiproxy_errors
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import datastore_errors
from google.appengine.api import datastore_distributed
from google.appengine.api import datastore
from google.appengine.ext import db


sys.path.append(TaskQueueConfig.CELERY_CONFIG_DIR)
sys.path.append(TaskQueueConfig.CELERY_WORKER_DIR)

app_id = 'APP_ID'

config = TaskQueueConfig(TaskQueueConfig.RABBITMQ, app_id)
module_name = TaskQueueConfig.get_celery_worker_module_name(app_id)
celery = Celery(module_name, broker=config.get_broker_string(),
  backend='amqp://')

celery.config_from_object('CELERY_CONFIGURATION')

logger = get_task_logger(__name__)

master_db_ip = appscale_info.get_db_master_ip()
connection_str = master_db_ip + ":" + str(constants.DB_SERVER_PORT)
ds_distrib = datastore_distributed.DatastoreDistributed(
  "appscaledashboard", connection_str, require_indexes=False)
apiproxy_stub_map.apiproxy.RegisterStub('datastore_v3', ds_distrib)
os.environ['APPLICATION_ID'] = "appscaledashboard"

# This template header and tasks can be found in appscale/AppTaskQueue/templates
