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


  # The file that the AppController writes the login node's public IP address
  # to.
  LOGIN_IP_FILENAME = "/etc/appscale/login_ip"


  # The file that the AppController writes this machine's public IP address to.
  MY_PUBLIC_IP_FILENAME = "/etc/appscale/my_public_ip"


  @classmethod
  def send_logs(cls, base64_logs):
    """Sends the given logs to the AppDashboard for later viewing.

    Args:
      base64_logs: A base64-encoded str that contains a JSON-dumped
        dict, indicating what the log message is, when it occurred, and what
        it's severity is. It does not need to indicate the public IP address
        of this machine, as we add that in.
    """
    incomplete_payload = base64.b64decode(base64_logs)
    log = json.loads(incomplete_payload)
    log['host'] = cls.get_my_public_hostname()
    complete_payload = json.dumps(log)

    conn = httplib.HTTPSConnection('{0}:1443'.format(cls.get_login_host()))
    headers = {'Content-Type' : 'application/json'}
    conn.request('POST', '/logs/upload', complete_payload, headers)
    response = conn.getresponse()


  @classmethod
  def get_my_public_hostname(cls):
    """Reads local filesystem state to find out what this machine's public
    hostname (IP or FQDN) is.

    Returns:
      A str that indicates what IP or FQDN this machine can be accessed via.
    """
    return cls.read_file(cls.MY_PUBLIC_IP_FILENAME)


  @classmethod
  def get_login_host(cls):
    """Reads local filesystem state to find out what machine runs the
    AppDashboard service, and the hostname that it runs at.

    Returns:
      A str that indicates what IP or FQDN the machine running the AppDashboard
        can be accessed via.
    """
    return cls.read_file(cls.LOGIN_IP_FILENAME)


  @classmethod
  def read_file(cls, filename):
    """A helper function that reads a file on the local filesystem, stripping
    a trailing newline (if present).

    Removing that newline is useful because when the AppController writes these
    files, it sometimes places a newline after the IP or FQDN of the machine in
    question.

    Args:
      filename: A str indicating which file should be read.
    Returns:
      A str containing the contents of the file, without a trailing newline.
    """
    with open(filename, 'r') as file_handle:
      host = file_handle.read()
      if host[-1] == "\n":
        return host[:-1]
      else:
        return host


if __name__ == '__main__':
  LogSender.send_logs(sys.argv[1])
