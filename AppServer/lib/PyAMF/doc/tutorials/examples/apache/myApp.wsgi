import logging
from logging.handlers import RotatingFileHandler

import application as app


# logging level
LEVEL = logging.DEBUG

# a filename to append log messages to
LOG_FILENAME = '/var/log/apache2/myApp.log'

# max size in bytes before a new log file is created
MAX_SIZE = 2000

# max amount of log files before it rotates
BACKUP_COUNT = 5

# Set up a specific logger with our desired output level
logger = logging.getLogger('MyLogger')
logger.setLevel(LEVEL)

# Add the log message handler to the logger
handler = RotatingFileHandler(LOG_FILENAME,
			      maxBytes=MAX_SIZE,
			      backupCount=BACKUP_COUNT)

# log message formatter
formatter = logging.Formatter("%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


# hook up logger to gateway
app.gateway.logger = logger

# hook up gateway to mod_wsgi
application = app.gateway

