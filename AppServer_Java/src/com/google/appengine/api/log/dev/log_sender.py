#!/usr/bin/env python
# Programmer: Chris Bunch (chris@appscale.com)
"""LogSender will forward a log message to the Admin Console, so that it can be
stored for later retrieval.
"""

import base64
import httplib
import json
import sys

class LogSender():


  @classmethod
  def send_logs(cls, base64_logs):
    incomplete_payload = base64.b64decode(base64_logs)
    log = json.loads(incomplete_payload)
    log['host'] = cls.get_my_public_hostname()
    complete_payload = json.dumps(log)

    conn = httplib.HTTPSConnection('{0}:443'.format(cls.get_login_host()))
    headers = {'Content-Type' : 'application/json'}
    conn.request('POST', '/logs/upload', complete_payload, headers)
    response = conn.getresponse()


  @classmethod
  def get_my_public_hostname(cls):
    return cls.read_file("/etc/appscale/my_public_ip")


  @classmethod
  def get_login_host(cls):
    return cls.read_file("/etc/appscale/login_ip")


  @classmethod
  def read_file(cls, filename):
    with open(filename, 'r') as file_handle:
      host = file_handle.read()
      if host[-1] == "\n":
        return host[:-1]
      else:
        return host


if __name__ == '__main__':
  LogSender.send_logs(sys.argv[1])
