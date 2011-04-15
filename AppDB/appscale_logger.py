# common logger getter

import os,sys
import logging
import logging.handlers
from dbconstants import *

def getLogger(name = "None"):
  logfile = "%s/%s.log" % (LOG_DIR, name)
  logger = logging.getLogger(name)
  logger.setLevel(logging.INFO)
  formatter = logging.Formatter("%(asctime)s %(module)s:%(lineno)-4d %(message)s")
  handler = logging.handlers.RotatingFileHandler(logfile, maxBytes=10000000, backupCount=10)
  handler.setFormatter(formatter)
  logger.addHandler(handler)
  return logger
