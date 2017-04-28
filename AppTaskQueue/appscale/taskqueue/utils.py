import logging

from appscale.common.constants import LOG_FORMAT


logging.basicConfig(format=LOG_FORMAT)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
