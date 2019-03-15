#!/usr/bin/env python2
""" This SOAP server is a data access layer over the datastore. It
presents information about applications and users as SOAP callable
functions.

"""
#TODO(raj) Rewrite this to use the lastest version of the AppScale
# datastore API.

import datetime
import logging
import SOAPpy
import sys
import time

from appscale.common import appscale_info
from appscale.common.constants import LOG_FORMAT
from tornado import gen

from appscale.datastore import appscale_datastore
from appscale.datastore.dbconstants import (
  AppScaleDBConnectionError, USERS_SCHEMA, USERS_TABLE
)
from appscale.datastore.utils import tornado_synchronous

# Name of the users table which stores information about AppScale users.
USER_TABLE = USERS_TABLE

# The default datastore used to store user and app information.
DEFAULT_DATASTORE = "cassandra"

# The port this server binds to.
DEFAULT_PORT = 4342

# The port avaialble from the outside via SSL.
DEFAULT_SSL_PORT = 4343

# The default datastore used.
datastore_type = DEFAULT_DATASTORE

# The port this application binds to.
bindport = DEFAULT_PORT

# The datastore error codes.
ERROR_CODES = []

# Global secret to validate incoming soap requests.
super_secret = appscale_info.get_secret()

# Datastore accessor.
db = []

# The schema we use to store user information.
user_schema = []

# Different types of valid users created.
VALID_USER_TYPES = ["user", "xmpp_user", "app", "channel"]

# Port separator used to store http and https application ports.
PORT_SEPARATOR = '-'

logger = logging.getLogger(__name__)


class Users:
  attributes_ = USERS_SCHEMA
  def __init__(self, email, password, utype):
    self.email_ = email
    self.pw_ = password
    t = datetime.datetime.now()
    self.date_creation_ = str(time.mktime(t.timetuple()))
    self.date_change_ = str(self.date_creation_)
    self.date_last_login_ = str(self.date_creation_)
    self.applications_ = []
    self.appdrop_rem_token_ = "notSet"
    self.appdrop_rem_token_exp_ = "0"
    self.visit_cnt_ = "0"
    self.cookie_ = "notSet"
    self.cookie_ip_ = "0.0.0.0"
    self.cookie_exp_ = "0"
    self.cksum_ = "0"
    self.enabled_ = "true"
    self.type_ = utype
    self.is_cloud_admin_ = "false"
    self.capabilities_ = ""
    return

  def stringit(self):
    userstring = ""
    userstring += "user_email:" + str(self.email_) + "\n"
    userstring += "password:" + str(self.pw_) + "\n"
    userstring += "num_apps:" + str(len(self.applications_)) + "\n"
    userstring += "applications:" + ':'.join(self.applications_) + "\n"
    userstring += "creation_date:" + str(self.date_creation_) + "\n"
    userstring += "change_date:" + str(self.date_change_) + "\n"
    userstring += "login_date:" + str(self.date_last_login_) + "\n"
    userstring += "visit_cnt:" + str(self.visit_cnt_) + "\n"
    userstring += "appdrop_rem_token:" + str(self.appdrop_rem_token_) + "\n"
    userstring += "session_cookie:" + str(self.cookie_) + "\n"
    userstring += "cookie_exp:" + str(self.cookie_exp_) + "\n"
    userstring += "cookie_ip:" + str(self.cookie_ip_) + "\n"
    userstring += "ck_sum:" + str(self.cksum_) + "\n"
    userstring += "enabled:" + str(self.enabled_) + "\n"
    userstring += "type:" + str(self.type_) + "\n"
    userstring += "is_cloud_admin:" + str(self.is_cloud_admin_) + "\n"
    userstring += "capabilities:" + str(self.capabilities_) + "\n"
    return userstring

  def checksum(self):
    return 1

  def arrayit(self):
    array = []
    # order must match self.attributes_
    # some entries must be converted to string format from arrays
    for ii in Users.attributes_:
      if ii == "applications":
        array.append(':'.join(getattr(self, ii + "_")))
      else:
        array.append(str(getattr(self, ii+ "_")))

    return array

  def unpackit(self, array):
    for ii in range(0,len(array)):
      setattr(self, Users.attributes_[ii] + "_", array[ii])

    # convert from string to list
    if self.applications_:
      self.applications_ = self.applications_.split(':')
    else:
      self.applications_ = []

    return "true"


@tornado_synchronous
@gen.coroutine
def does_user_exist(username, secret):
  global db
  global super_secret
  if secret != super_secret:
    raise gen.Return("Error: bad secret")
  try:
    result = yield db.get_entity(USER_TABLE, username, ["email"])
  except AppScaleDBConnectionError as db_error:
    raise gen.Return('Error: {}'.format(db_error))
  if result[0] in ERROR_CODES and len(result) == 2:
    raise gen.Return("true")
  else:
    raise gen.Return("false")


@tornado_synchronous
@gen.coroutine
def get_user_data(username, secret):
  global db
  global super_secret
  global user_schema
  if secret != super_secret:
    raise gen.Return("Error: bad secret")
  try:
    result = yield db.get_entity(USER_TABLE, username, user_schema)
  except AppScaleDBConnectionError as db_error:
    raise gen.Return('Error: {}'.format(db_error))

  if result[0] in ERROR_CODES or len(result) == 1:
    result = result[1:]
  else:
    raise gen.Return("Error: " + result[0])
  if len(user_schema) != len(result):
    raise gen.Return(
      "Error: Bad length of user schema vs user result "
      "user schem:" + str(user_schema) + " result: " + str(result)
    )

  user = Users("a","b", "c")
  user.unpackit(result)
  raise gen.Return(user.stringit())


@tornado_synchronous
@gen.coroutine
def commit_new_user(user, passwd, utype, secret):
  global db
  global super_secret
  global user_schema
  if secret != super_secret:
    raise gen.Return("Error: bad secret")
  if utype not in VALID_USER_TYPES:
    raise gen.Return("Error: Not a valid user type %s"%utype)
  error =  "Error: username should be an email"
  # look for the @ and . in the email
  if user.find("@") == -1 or user.find(".") == -1:
    raise gen.Return(error)

  error = "Error: user already exists"
  ret = does_user_exist(user, secret)
  if ret == "true":
    raise gen.Return(error)

  n_user = Users(user, passwd, utype)
  array = n_user.arrayit()
  result = yield db.put_entity(USER_TABLE, user, user_schema, array)
  if result[0] not in ERROR_CODES:
    raise gen.Return("false")
  raise gen.Return("true")


@tornado_synchronous
@gen.coroutine
def add_admin_for_app(user, app, secret):
  """ Grants admin role to a given application.

  Admin:
    user: A str, the user email.
    app: A str, the application ID.
    secret: The secret key for authentication.
  Returns:
    "true" on success, error message otherwise.
  """
  global db
  global user_schema
  global super_secret
  if secret != super_secret:
    raise gen.Return("Error: bad secret")

  try:
    user_result = yield db.get_entity(USER_TABLE, user, user_schema)
  except AppScaleDBConnectionError as db_error:
    raise gen.Return('Error: {}'.format(db_error))

  if user_result[0] not in ERROR_CODES or len(user_result) <= 1:
    raise gen.Return(user_result)

  user_result = user_result[1:]
  n_user = Users("a", "b", "c")
  n_user.unpackit(user_result)
  n_user.applications_.append(app)
  t = datetime.datetime.now()
  n_user.date_change_ = str(time.mktime(t.timetuple()))
  array = n_user.arrayit()

  result = yield db.put_entity(USER_TABLE, user, user_schema, array)
  if result[0] in ERROR_CODES:
    raise gen.Return("true")
  else:
    raise gen.Return("Error: Unable to update the user.")


@tornado_synchronous
@gen.coroutine
def get_all_users(secret):
  global db
  global super_secret
  global user_schema
  users = []
  if secret != super_secret:
    raise gen.Return("Error: bad secret")

  result = yield db.get_table(USER_TABLE, user_schema)
  if result[0] not in ERROR_CODES:
    raise gen.Return("Error:" + result[0])
  result = result[1:]
  for ii in range(0, (len(result)/len(user_schema))):
    partial = result[(ii * len(user_schema)): ((1 + ii) * len(user_schema))]
    if len(partial) != len(user_schema):
      pass
    else:
      a = Users("x", "x", "user")
      a.unpackit(partial)
      users.append(a)

  # this is a placeholder, soap exception happens if returning empty string
  userstring = "____"
  for kk in users:
    userstring += ":" + kk.email_
  raise gen.Return(userstring)


@tornado_synchronous
@gen.coroutine
def commit_new_token(user, token, token_exp, secret):
  global db
  global super_secret
  global user_schema
  if secret != super_secret:
    raise gen.Return("Error: bad secret")
  columns = ['appdrop_rem_token', 'appdrop_rem_token_exp']

  try:
    result = yield db.get_entity(USER_TABLE, user, columns)
  except AppScaleDBConnectionError as db_error:
    raise gen.Return('Error: {}'.format(db_error))

  if result[0] not in ERROR_CODES or len(result) == 1:
    raise gen.Return("Error: User does not exist")

  result = result[1:]
  #appdrop_rem_token = result[0]
  #appdrop_rem_token_exp = result[1]
  t = datetime.datetime.now()
  date_change = str(time.mktime(t.timetuple()))

  values = [token, token_exp, date_change]
  columns += ['date_change']

  result = yield db.put_entity(USER_TABLE, user, columns, values)
  if result[0] not in ERROR_CODES:
    raise gen.Return("false")
  raise gen.Return("true")


@tornado_synchronous
@gen.coroutine
def change_password(user, password, secret):
  global db
  global super_secret
  global user_schema

  if secret != super_secret:
    raise gen.Return("Error: bad secret")

  if not password:
    raise gen.Return("Error: Null password")

  try:
    result = yield db.get_entity(USER_TABLE, user, ['enabled'])
  except AppScaleDBConnectionError as db_error:
    raise gen.Return('Error: {}'.format(db_error))

  if result[0] not in ERROR_CODES or len(result) == 1:
    raise gen.Return("Error: user does not exist")

  if result[1] == "false":
    raise gen.Return("Error: User must be enabled to change password")

  result = yield db.put_entity(USER_TABLE, user, ['pw'], [password])
  if result[0] not in ERROR_CODES:
    raise gen.Return("Error:" + result[0])
  raise gen.Return("true")


@tornado_synchronous
@gen.coroutine
def enable_user(user, secret):
  global db
  global super_secret
  global user_schema
  if secret != super_secret:
    raise gen.Return("Error: bad secret")

  try:
    result = yield db.get_entity(USER_TABLE, user, ['enabled'])
  except AppScaleDBConnectionError as db_error:
    raise gen.Return('Error: {}'.format(db_error))

  if result[0] not in ERROR_CODES or len(result) != 2:
    raise gen.Return("Error: " + result[0])
  if result[1] == "true":
    raise gen.Return("Error: Trying to enable a user twice")
  result = yield db.put_entity(USER_TABLE, user, ['enabled'], ['true'])
  if result[0] not in ERROR_CODES:
    raise gen.Return("false")
  raise gen.Return("true")


@tornado_synchronous
@gen.coroutine
def disable_user(user, secret):
  global db
  global user_schema
  global super_secret
  if secret != super_secret:
    raise gen.Return("Error: bad secret")

  try:
    result = yield db.get_entity(USER_TABLE, user, ['enabled'])
  except AppScaleDBConnectionError as db_error:
    raise gen.Return('Error: {}'.format(db_error))

  if result[0] not in ERROR_CODES or len(result) != 2:
    raise gen.Return("Error: " + result[0])
  if result[1] == "false":
    raise gen.Return("Error: Trying to disable a user twice")

  result = yield db.put_entity(USER_TABLE, user, ['enabled'], ['false'])
  if result[0] not in ERROR_CODES:
    raise gen.Return("false")
  raise gen.Return("true")


@tornado_synchronous
@gen.coroutine
def delete_user(user, secret):
  global db
  global user_schema
  global super_secret
  if secret != super_secret:
    raise gen.Return("Error: bad secret")

  try:
    result = yield db.get_entity(USER_TABLE, user, ['enabled'])
  except AppScaleDBConnectionError as db_error:
    raise gen.Return('Error: {}'.format(db_error))

  if result[0] not in ERROR_CODES or len(result) != 2:
    raise gen.Return("false")

  if result[1] == 'true':
    raise gen.Return("Error: unable to delete active user. Disable user first")

  result = yield db.delete_row(USER_TABLE, user)
  if result[0] not in ERROR_CODES:
    raise gen.Return("false")
  raise gen.Return("true")


@tornado_synchronous
@gen.coroutine
def is_user_enabled(user, secret):
  global db
  global super_secret
  global user_schema
  if secret != super_secret:
    raise gen.Return("Error: bad secret")

  try:
    result = yield db.get_entity(USER_TABLE, user, ['enabled'])
  except AppScaleDBConnectionError as db_error:
    raise gen.Return('Error: {}'.format(db_error))

  if result[0] not in ERROR_CODES or len(result) == 1:
    raise gen.Return("false")
  raise gen.Return(result[1])


@tornado_synchronous
@gen.coroutine
def is_user_cloud_admin(username, secret):
  global db
  global super_secret
  if secret != super_secret:
    raise gen.Return("Error: bad secret")

  try:
    result = yield db.get_entity(USER_TABLE, username, ["is_cloud_admin"])
  except AppScaleDBConnectionError as db_error:
    raise gen.Return('Error: {}'.format(db_error))

  if result[0] in ERROR_CODES and len(result) == 2:
    raise gen.Return(result[1])
  else:
    raise gen.Return("false")


@tornado_synchronous
@gen.coroutine
def set_cloud_admin_status(username, is_cloud_admin, secret):
  global db
  global super_secret
  if secret != super_secret:
    raise gen.Return("Error: bad secret")
  result = yield db.put_entity(USER_TABLE, username, ['is_cloud_admin'], [is_cloud_admin])
  if result[0] not in ERROR_CODES:
    raise gen.Return("false:" + result[0])
  raise gen.Return("true")


@tornado_synchronous
@gen.coroutine
def get_capabilities(username, secret):
  global db
  global super_secret
  if secret != super_secret:
    raise gen.Return("Error: bad secret")

  try:
    result = yield db.get_entity(USER_TABLE, username, ["capabilities"])
  except AppScaleDBConnectionError as db_error:
    raise gen.Return('Error: {}'.format(db_error))

  if result[0] in ERROR_CODES and len(result) == 2:
    raise gen.Return(result[1])
  else:
    raise gen.Return([result[0]])


@tornado_synchronous
@gen.coroutine
def set_capabilities(username, capabilities, secret):
  global db
  global super_secret
  if secret != super_secret:
    raise gen.Return("Error: bad secret")
  result = yield db.put_entity(USER_TABLE, username, ['capabilities'], [capabilities])
  if result[0] not in ERROR_CODES:
    raise gen.Return("false:" + result[0])
  raise gen.Return("true")


def usage():
  print "args: --apps or -a for the application location"
  print "      --users or -u for the user location"
  print "      --type or -t for type of datastore"
  print "        type available: cassandra"
  print "      --port or -p for server port"


def main():
  """ Main function for running the server. """
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
  logger.info('Starting UAServer')

  global bindport
  global datastore_type
  global db
  global ERROR_CODES
  global user_schema

  for ii in range(1, len(sys.argv)):
    if sys.argv[ii] in ("-h", "--help"):
      usage()
      sys.exit()
    elif sys.argv[ii] in ('-t', "--type"):
      datastore_type = sys.argv[ii + 1]
      ii += 1
    elif sys.argv[ii] in ('-p', "--port"):
      bindport = int(sys.argv[ii + 1] )
      ii += 1
    else:
      pass

  db = appscale_datastore.DatastoreFactory.getDatastore(datastore_type)
  ERROR_CODES = appscale_datastore.DatastoreFactory.error_codes()
  valid_datastores = appscale_datastore.DatastoreFactory.valid_datastores()
  if datastore_type not in valid_datastores:
    raise Exception('{} not in valid datastores ({})'.
                    format(datastore_type, valid_datastores))

  # Keep trying until it gets the schema.
  timeout = 5
  while 1:
    try:
      user_schema = db.get_schema_sync(USER_TABLE)
    except AppScaleDBConnectionError:
      time.sleep(timeout)
      continue

    if user_schema[0] in ERROR_CODES:
      user_schema = user_schema[1:]
      Users.attributes_ = user_schema
    else:
      time.sleep(timeout)
      continue
    break

  ip = "0.0.0.0"
  server = SOAPpy.SOAPServer((ip, bindport))
  logger.info('Serving on {}'.format(bindport))
  # To debug this service, uncomment the 2 lines below.
  #server.config.dumpSOAPOut = 1
  #server.config.dumpSOAPIn = 1

  # Register soap functions.
  server.registerFunction(does_user_exist, funcName='does_user_exist')
  server.registerFunction(get_all_users, funcName='get_all_users')
  server.registerFunction(get_user_data, funcName='get_user_data')
  server.registerFunction(add_admin_for_app, funcName='add_admin_for_app')
  server.registerFunction(commit_new_user, funcName='commit_new_user')
  server.registerFunction(commit_new_token, funcName='commit_new_token')
  server.registerFunction(delete_user, funcName='delete_user')

  server.registerFunction(change_password, funcName='change_password')

  server.registerFunction(disable_user, funcName='disable_user')
  server.registerFunction(enable_user, funcName='enable_user')
  server.registerFunction(is_user_enabled, funcName='is_user_enabled')

  server.registerFunction(is_user_cloud_admin, funcName='is_user_cloud_admin')
  server.registerFunction(set_cloud_admin_status, funcName='set_cloud_admin_status')
  server.registerFunction(get_capabilities, funcName='get_capabilities')
  server.registerFunction(set_capabilities, funcName='set_capabilities')

  while 1:
    server.serve_forever()
