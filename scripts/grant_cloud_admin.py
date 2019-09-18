""" Grants cloud admin access to a user. """

import sys

from appscale.common.ua_client import UAClient


def usage():
  """ Prints the usage of this script. """
  print ""
  print "Grants cloud admin access to user for an AppScale cloud."
  print "Args: email address"
  print "      an application ID."
  print ""
  print "Example:"
  print "  python add_admin_to_app.py bob@appscale.com"
  print ""

if __name__ == "__main__":
  total = len(sys.argv)
  if total < 2:
    usage()
    sys.exit(1)

  email = sys.argv[1]

  ua_client = UAClient()

  if not ua_client.does_user_exist(email):
    print "User does not exist."
    sys.exit(1)

  ua_client.set_cloud_admin_status(email, True)
  print('{} granted cloud admin access.'.format(email))

  # Verify cloud admin status.
  assert ua_client.is_user_cloud_admin(email), 'Unable to verify admin status'
