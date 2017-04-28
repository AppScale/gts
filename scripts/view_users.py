""" This script dumps all users. """

from appscale.common import appscale_info
from appscale.common.ua_client import UAClient


if __name__ == "__main__":

  secret = appscale_info.get_secret()
  ua_client = UAClient(appscale_info.get_db_master_ip(), secret)

  for user in ua_client.get_all_users():
    print(user)
