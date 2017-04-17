""" This script dumps AppScale attributes on a user. """

import sys

from appscale.common import appscale_info
from appscale.common.ua_client import UAClient


if __name__ == "__main__":

  email = sys.argv[1]
  secret = appscale_info.get_secret()
  ua_client = UAClient(appscale_info.get_db_master_ip(), secret)

  if not ua_client.does_user_exist(email):
    print "User does not exist."
    sys.exit(1)

  print(ua_client.get_user_data(email))
