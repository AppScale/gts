import os
import SOAPpy
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib"))
import appscale_info
import constants
# soap server located at appscale/AppDB/soap_server.py


def get_soap_accessor():
  """ Returns the SOAP server accessor to deal with application and users.

  Returns:
    A soap server accessor.
  """
  db_ip = appscale_info.get_db_master_ip()
  bindport = constants.UA_SERVER_PORT
  return SOAPpy.SOAPProxy("https://{0}:{1}".format(db_ip, bindport))

if __name__ == "__main__":

  server = get_soap_accessor()
  apps = server.get_all_apps(appscale_info.get_secret())
  apps = apps.split(':')
  for app in apps:
    if server.is_app_enabled(app, appscale_info.get_secret()) and app != "____":
      app_data = server.get_app_data(app, appscale_info.get_secret())
      print app_data
