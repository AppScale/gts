""" This script dumps all users. """

from appscale.common.ua_client import UAClient


if __name__ == "__main__":

  ua_client = UAClient()

  for user in ua_client.get_all_users():
    print(user)
