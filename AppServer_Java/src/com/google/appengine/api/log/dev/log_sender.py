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
    payload = base64.b64decode(base64_logs)
    conn = httplib.HTTPSConnection('192.168.10.2:443')
    headers = {'Content-Type' : 'application/json'}
    conn.request('POST', '/logs/upload', payload, headers)
    response = conn.getresponse()


if __name__ == '__main__':
  LogSender.send_logs(sys.argv[1])
