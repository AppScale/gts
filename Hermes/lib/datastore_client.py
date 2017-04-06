#!/usr/bin/env python


# General-purpose Python library imports.
import logging
import os
import re
import subprocess
import sys

import json
from tornado import httpclient, gen

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
    return self.get_datastore_stats_async().result()

  @gen.coroutine
  def get_datastore_stats_async(self):
    async_client = httpclient.AsyncHTTPClient()
    servers = self.get_datastore_servers()

    @gen.coroutine
    def get_node_stats_async(server_ip):
      url = "http://{ip}".format(ip=server_ip)
      request = helper.create_request(url, method='GET')

      try:
        response = yield async_client.fetch(request)
      except httpclient.HTTPError as err:
        logging.error("Error while trying to fetch {}: {}".format(url, err))
        # Return nothing but not raise an error
        raise gen.Return()

      logging.debug(response.body)
      db_info = json.loads(response.body)
      # Return node stats (e.g.:{'GET': {'Success': [235, 12.53], ..}, ...})
      raise gen.Return({
        method: {
          db_error_name(error_code): (total_req, total_time)
          for error_code, (total_req, total_time) in stats.iteritems()
        }
        for method, stats in db_info.iteritems()
      })

    # Do multiple requests asynchronously and wait for all results
    nodes_stats_dict = yield {
      ip: get_node_stats_async(ip) for ip in servers
    }
    raise gen.Return(nodes_stats_dict)

def db_error_name(error_code):
  return datastore_pb.Error.ErrorCode_Name(error_code) or 'Success'
