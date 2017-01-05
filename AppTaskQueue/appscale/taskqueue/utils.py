import logging
import sys

from .unpackaged import APPSCALE_LIB_DIR

sys.path.append(APPSCALE_LIB_DIR)
from constants import LOG_FORMAT


logging.basicConfig(format=LOG_FORMAT)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
