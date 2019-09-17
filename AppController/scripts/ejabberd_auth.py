#!/usr/bin/env python2

import hashlib
import logging
import os
import re
import socket
import struct
import sys
import time

from appscale.common import appscale_info
from appscale.common.constants import LOG_FORMAT
from appscale.common.ua_client import UAClient

LOG_FILE = os.path.join('/', 'var', 'log', 'ejabberd', 'extauth.log')


class EjabberdInputError(Exception):
  def __init__(self, value):
    self.value = value
  def __str__(self):
    return repr(self.value)


def ejabberd_in():
  logging.debug("trying to read 2 bytes from ejabberd:")
  input_length = sys.stdin.read(2)

  if len(input_length) is not 2:
    logging.debug("ejabberd sent us wrong things!")
    raise EjabberdInputError('Wrong input from ejabberd!')

  logging.debug('got 2 bytes via stdin: %s'%input_length)
  (size,) = struct.unpack('>h', input_length)

  logging.debug('size of data: %i'%size)
  data = sys.stdin.read(size).split(':')

  logging.debug("incoming data: %s"%data)
  return data


def ejabberd_out(result):
  logging.debug("Ejabberd gets: %s" % result)
  token = genanswer(result)
  sys.stdout.write(token)
  sys.stdout.flush()


def genanswer(result):
  answer = 0
  if result:
    answer = 1

  token = struct.pack('>hh', 2, answer)
  return token


def isuser(in_user, in_host):
  return True


def auth(in_user, in_host, password):
  username = in_user + "@" + in_host

  logging.info("trying to authenticate user [%s]" % (username))

  if not isuser(in_user, in_host):
    return False

  while True:
    try:
      userdata = ua_client.get_user_data(username)
      break
    except socket.error:
      time.sleep(1)

  logging.info("userdata for [%s] is [%s]" % (username, str(userdata)))
  matchdata = re.search('password:(.*)', userdata)

  if matchdata is None:
    logging.info("matchdata for [%s] was none" % (username))
    return False

  remote_password = matchdata.group(1)

  salted = username + password
  local_password = hashlib.sha1(salted).hexdigest()

  logging.info("local password: [%s]" % (local_password))
  logging.info("remote password: [%s]" % (remote_password))

  return local_password == remote_password


def log_result(op, in_user, result):
  if result:
    logging.info("%s successful for %s"%(op, in_user))
  else:
    logging.info("%s unsuccessful for %s"%(op, in_user))


if __name__ == '__main__':
  sys.stderr = open(LOG_FILE, 'a')
  logging.basicConfig(
    level=logging.INFO, format=LOG_FORMAT, filename=LOG_FILE, filemode='a')

  logging.debug('Authentication script: waiting for ejabberd requests')

  ua_client = UAClient()

  while True:
    try:
      ejab_request = ejabberd_in()
    except EjabberdInputError as inst:
      logging.info("Exception occurred: %s", inst)
      break

    logging.debug('operation: %s'%(ejab_request[0]))
    op_result = False

    if ejab_request[0] == "auth":
      op_result = auth(ejab_request[1], ejab_request[2], ejab_request[3])
      ejabberd_out(op_result)
      log_result(ejab_request[0], ejab_request[1], op_result)
    elif ejab_request[0] == "isuser":
      op_result = isuser(ejab_request[1], ejab_request[2])
      ejabberd_out(op_result)
      log_result(ejab_request[0], ejab_request[1], op_result)
    elif ejab_request[0] == "setpass":
      op_result=False
      ejabberd_out(op_result)
      log_result(ejab_request[0], ejab_request[1], op_result)

  logging.info("extauth script terminating")
