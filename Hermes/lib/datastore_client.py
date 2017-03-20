#!/usr/bin/env python


# General-purpose Python library imports.
import logging
import os
import re
import subprocess
import sys
import yaml

# Hermes imports.
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))
import helper

# AppServer imports.
sys.path.append(os.path.join(os.path.dirname(__file__), '../AppServer'))
from google.appengine.api.datastore import datastore_pb


class DatastoreClient:

  DATASTORE_SERVER_NAME = "appscale-datastore_server"

  HAPROXY_PATH = "/etc/haproxy/stats"

  def get_datastore_servers(self):
    """ Queries HAProxy for Datastore servers.

    Returns:
      A list of strings containing the ip:port of each Datastore server running.
    """
    servers = subprocess.check_output("echo \"show stat\" | socat stdio "
                                      "unix-connect:{} | grep {}"
                                      .format(self.HAPROXY_PATH,
                                              self.DATASTORE_SERVER_NAME),
                                      shell=True)
    if servers == 1:
      return []
    datastore_servers = []
    for server in servers.split("\n"):
      parsed_server = server.split(',')
      logging.info("server: {}\nparsed server:{}".format(server, parsed_server))
      if parsed_server[0] == self.DATASTORE_SERVER_NAME and parsed_server[1] \
          != "FRONTEND" and parsed_server[1] != "BACKEND":
        logging.info("len parsed {}".format(len(parsed_server)))
        logging.info(parsed_server[1])
        ip = re.sub('^{}-'.format(
          self.DATASTORE_SERVER_NAME), '', parsed_server[1])
        logging.info(ip)
        datastore_servers.append(ip)
    return datastore_servers

  def get_datastore_stats(self):
    """Makes a request to each Datastore server retrieved by
    get_datastore_servers to get their stats.

      Returns:
         A list of dicts containing statistics about datastore performance of
         the format:
           { Datastore IP: { method: (Success/ErrorCode, Time Taken) } }
    """
    servers = self.get_datastore_servers()
    datastore_stats = {}
    for server in servers:
      request = helper.create_request("http://{ds_server}".format(
        ds_server=server), method='GET')
      response = helper.urlfetch(request)
      if response.get(helper.JSONTags.SUCCESS):
        json_body = response.get(helper.JSONTags.BODY)
        logging.info(json_body)
        db_info = yaml.safe_load(json_body)
        logging.info(db_info)
        for method, stats in db_info.items():
          for k, v in stats.items():
            error_code = 'Success' if k == '0' else \
              datastore_pb.Error.ErrorCode_Name(k)
            datastore_stats[server] = {method: {error_code: v}}
    return datastore_stats
