""" Grants admin access to a user. """

import sys

from appscale.common.ua_client import UAClient


def usage():
  """ Prints the usage of this script. """
  print ""
  print "Grants admin access to user for a given application."
  print "Args: email address"
  print "      an application ID."
  print ""
  print "Example:"
  print "  python add_admin_to_app.py bob@appscale.com guestbook"
  print ""

if __name__ == "__main__":
  total = len(sys.argv)
  if total < 3:
    usage() 
    sys.exit(1)

  email = sys.argv[1]
  app_id = sys.argv[2]

  ua_client = UAClient()

  if not ua_client.does_user_exist(email):
    print "User does not exist."
    sys.exit(1)

  ua_client.add_admin_for_app(email, app_id)
  print('{} granted admin access to {}'.format(email, app_id))
