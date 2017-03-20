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
from google.appengine.api.taskqueue import taskqueue_service_pb


class TaskQueueClient:

  TASKQUEUE_SERVER_NAME = "TaskQueue"

  HAPROXY_PATH = "/etc/haproxy/stats"

  def get_taskqueue_servers(self):
    """ Queries HAProxy for TaskQueue servers.

    Returns:
      A list of strings containing the ip:port of each TaskQueue server running.
    """
    servers = subprocess.check_output("echo \"show stat\" | socat stdio "
                                      "unix-connect:{} | grep {}"
                                      .format(self.HAPROXY_PATH,
                                              self.TASKQUEUE_SERVER_NAME),
                                      shell=True)
    if servers == 1:
      return []
    taskqueue_servers = []
    for server in servers.split("\n"):
      parsed_server = server.split(',')
      logging.info("server: {}\nparsed server:{}".format(server, parsed_server))
      if parsed_server[0] == self.TASKQUEUE_SERVER_NAME and parsed_server[1] \
          != "FRONTEND" and parsed_server[1] != "BACKEND":
        logging.info("len parsed {}".format(len(parsed_server)))
        logging.info(parsed_server[1])
        ip = re.sub('^{}-'.format(
          self.TASKQUEUE_SERVER_NAME), '', parsed_server[1])
        logging.info(ip)
        taskqueue_servers.append(ip)
    return taskqueue_servers

  def get_taskqueue_stats(self):
    """Makes a request to each TaskQueue server retrieved by
    get_taskqueue_servers to get their stats.

      Returns:
         A list of dicts containing statistics about taskqueue performance of
         the format:
           { TaskQueue IP: { method: (Success/ErrorCode, Time Taken) } }
    """
    servers = self.get_taskqueue_servers()
    taskqueue_stats = {}
    for server in servers:
      request = helper.create_request("http://{tq_server}".format(
        tq_server=server), method='GET')
      response = helper.urlfetch(request)
      if response.get(helper.JSONTags.SUCCESS):
        json_body = response.get(helper.JSONTags.BODY)
        logging.info(json_body)
        tq_info = yaml.safe_load(json_body)
        logging.info(tq_info)
        logging.info(type(tq_info.values()[0]))
        for method, stats in tq_info.get('details').items():
          for k, v in stats.items():
            error_code = 'Success' if k == '0' else \
              taskqueue_service_pb.Error.ErrorCode_Name(k)
            taskqueue_stats[server] = {method: {error_code: v}}
    return taskqueue_stats
