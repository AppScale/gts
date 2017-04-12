""" This script deletes a user. """

import sys

from appscale.common import appscale_info
from appscale.common.ua_client import UAClient


def usage():
  print ""
  print "Deletes a user in AppScale."
  print "Args: email address"
  print ""
  print "Examples:"
  print "  python delete_user.py bob@appscale.com"
  print ""

if __name__ == "__main__":
  total = len(sys.argv)
  if total != 2:
    usage() 
    sys.exit(1)

  email = sys.argv[1]

  secret = appscale_info.get_secret()
  ua_client = UAClient(appscale_info.get_db_master_ip(), secret)

  if not ua_client.does_user_exist(email):
    print "User does not exist."
    sys.exit(1)

  print "Deleting user...",
  ua_client.disable_user(email)
  ua_client.delete_user(email)
  print "Done."
