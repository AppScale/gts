""" Stores push task metadta. """
import sys

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.ext import db

class TaskName(db.Model):
  """ A datastore model for tracking task names in order to prevent
  tasks with the same name from being enqueued repeatedly.

  Attributes:
    timestamp: The time the task was enqueued.
  """
  STORED_KIND_NAME = "__task_name__"
  timestamp = db.DateTimeProperty(auto_now_add=True)
  queue = db.StringProperty(required=True)
  state = db.StringProperty(required=True)
  endtime = db.DateTimeProperty()
  app_id = db.StringProperty(required=True)

  @classmethod
  def kind(cls):
    """ Kind name override. """
    return cls.STORED_KIND_NAME
