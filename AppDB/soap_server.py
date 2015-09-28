""" This SOAP server is a data access layer over the datastore. It 
presents information about applications and users as SOAP callable
functions.

"""
#TODO(raj) Rewrite this to use the lastest version of the AppScale 
# datastore API.

import datetime
import os
import re
import sys
import time

from dbconstants import *
import appscale_datastore

import SOAPpy

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import constants
import appscale_info

# Name of the application table which stores AppScale application information.
APP_TABLE = APPS_TABLE

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

# The schema we use to store app information.
app_schema = []

# The application name regex to validate an application ID.
APPNAME_REGEX = r'^[\d\w\.@-]+$'

# Different types of valid users created.
VALID_USER_TYPES = ["user", "xmpp_user", "app", "channel"]

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
        array.append(str(getattr(self, ii+ "_")));

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

class Apps:
  attributes_ = APPS_SCHEMA
  def __init__(self, name, owner, language):
    self.tar_ball_ = "None"
    self.yaml_file_ = "None"
    self.version_ = "0"
    self.language_ = language
    self.admins_list_ = []
    self.host_ = []
    self.port_ = []
    self.creation_date_ = "0"
    self.last_time_updated_date_ = "0"
    self.name_ = name
    self.owner_ = owner
    t = datetime.datetime.now()
    self.creation_date_ = str(time.mktime(t.timetuple()))
    self.last_time_updated_date_ = str(self.creation_date_)
    self.cksum_ = "0"
    self.num_entries_ = "0"
    self.enabled_ = "true"
    self.classes_ = []
    self.indexes_ = "0"
    return
  
  def stringit(self):
    appstring = ""
    appstring += "app_name:" + str(self.name_) + "\n"
    appstring += "language:" + str(self.language_) + "\n"
    appstring += "version:" + str(self.version_) + "\n"
    appstring += "app_owner:" + self.owner_ + "\n"
    appstring += "num_admins:" + str(len(self.admins_list_)) + "\n"
    appstring += "admins:" + ':'.join(self.admins_list_) + "\n"
    appstring += "num_hosts:" + str(len(self.host_)) + "\n"
    appstring += "hosts:" + ':'.join(self.host_) + "\n"
    appstring += "num_ports:" + str(len(self.port_)) + "\n"
    appstring += "ports: " + ':'.join(self.port_) + "\n"
    appstring += "creation_date:" + str(self.creation_date_) + "\n"
    appstring += "last_update_date:" + str(self.last_time_updated_date_) + "\n"
    appstring += "check_sum:" + str(self.cksum_) + "\n"
    appstring += "num_entries:" + str(self.num_entries_) + "\n"
    appstring += "enabled:" + str(self.enabled_) + "\n"
    appstring += "classes:" + ':'.join(self.classes_) + "\n"
    appstring += "indexes:" + str(self.indexes_) + "\n"
    return appstring
  
  def checksum(self):
    return "true"
  
  def arrayit(self):
    array = []
    # order must match self.attributes
    # some entries must be converted to string format from arrays
    for ii in Apps.attributes_:
      if ii == "admins_list" or ii == 'host' or ii == 'port' or ii == 'classes':
        array.append(':'.join(getattr(self, ii + "_")))
      else:
        array.append(str(getattr(self, ii+ "_")));

    return array 
  
  def unpackit(self, array):
    for ii in range(0,len(array)):
      setattr(self, Apps.attributes_[ii] + "_", array[ii])
    
    # convert to different types
    if self.admins_list_:
      self.admins_list_ = self.admins_list_.split(':')
    else:
      self.admins_list_ = []

    if self.host_:
      self.host_ = self.host_.split(':')
    else:
      self.host_ = []

    if self.port_:
      self.port_ = self.port_.split(':')
    else: 
      self.port_ = []
     
    if self.classes_:
      self.classes_ = self.classes_.split(':')
    else:
      self.classes_ = []
    return "true"

def does_user_exist(username, secret):
  global db
  global super_secret
  if secret != super_secret:
    return "Error: bad secret"
  result = db.get_entity(USER_TABLE, username, ["email"])
  if result[0] in ERROR_CODES and len(result) == 2:
    return "true" 
  else:
    return "false"    

def does_app_exist(appname, secret):
  global db
  global super_secret
  if secret != super_secret:
    return "Error: bad secret"
  result = db.get_entity(APP_TABLE, appname, ["name"])
  if result[0] in ERROR_CODES and len(result) == 2:
    return "true"
  else:
    return "false"    

def get_user_apps(username, secret):
  global db
  global super_secret
  if secret != super_secret:
    return "Error: bad secret"
  result = db.get_entity(USER_TABLE, username, ["applications"])
  if result[0] in ERROR_CODES and len(result) == 2:
    return result[1] 
  else:
    error = "Error: user not found"  
    return error

def get_user_data(username, secret):
  global db
  global super_secret
  global user_schema
  if secret != super_secret:
    return "Error: bad secret"
  result = db.get_entity(USER_TABLE, username, user_schema)
   
  if result[0] in ERROR_CODES or len(result) == 1:
    result = result[1:]
  else:
    return "Error: " + result[0]
  if len(user_schema) != len(result):
    return "Error: Bad length of user schema vs user result user schem:" + str(user_schema) + " result: " + str(result)

  user = Users("a","b", "c")
  user.unpackit(result)
  return user.stringit()

def get_app_data(appname, secret):
  global db
  global super_secret
  global app_schema
  if secret != super_secret:
    return "Error: bad secret"
  if not appname or  not secret:
    return "Error: Null appname"
    
  result = db.get_entity(APP_TABLE, appname, app_schema)

  if result[0] not in ERROR_CODES or len(result) == 1:
    return "Error: " + result[0]

  result = result[1:]

  if len(app_schema) != len(result):
    error = "Error: Bad length of app schema vs app result " + str(app_schema) + " vs " + str(result) + " for appname: " + appname
    return  error 
  app = Apps("a","b", "c")
  app.unpackit(result)
  return app.stringit()

def commit_new_user(user, passwd, utype, secret):  
  global db
  global super_secret
  global user_schema
  if secret != super_secret:
    return "Error: bad secret"
  if utype not in VALID_USER_TYPES:
    return "Error: Not a valid user type %s"%utype
  error =  "Error: username should be an email"
  # look for the @ and . in the email
  if user.find("@") == -1 or user.find(".") == -1:
    return error
  
  error = "Error: user already exists"
  ret = does_user_exist(user, secret)
  if ret == "true":
    return error

  n_user = Users(user, passwd, utype)
  array = n_user.arrayit()
  result = db.put_entity(USER_TABLE, user, user_schema, array) 
  if result[0] not in ERROR_CODES:
    return "false"
  return "true"

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
  global app_schema
  global super_secret
  if secret != super_secret:
    return "Error: bad secret"

  user_result = db.get_entity(USER_TABLE, user, user_schema)
  if user_result[0] not in ERROR_CODES or len(user_result) <= 1:
    return user_result

  user_result = user_result[1:]
  n_user = Users("a", "b", "c") 
  n_user.unpackit(user_result)
  n_user.applications_.append(app)
  t = datetime.datetime.now()
  n_user.date_change_ = str(time.mktime(t.timetuple()))
  array = n_user.arrayit()

  result = db.put_entity(USER_TABLE, user, user_schema, array) 
  if result[0] in ERROR_CODES:
    return "true"
  else: 
    return "Error: Unable to update the user."
 
def commit_new_app(appname, user, language, secret):
  global db
  global user_schema
  global app_schema
  global super_secret
  if secret != super_secret:
    return "Error: bad secret"

  error =  "Error: appname/language can only be alpha numeric"
  if not language.isalnum():
    return error

  if re.search(APPNAME_REGEX,appname) is None:
    return error

  error =  "Error: appname already exist"
  if does_app_exist(appname, secret) == "true":
    return error

  ret = "true"

  user_result = db.get_entity(USER_TABLE, user, user_schema)
  if user_result[0] in ERROR_CODES and len(user_result) > 1:
    user_result = user_result[1:]
    n_user = Users("a", "b", "c") 
    n_user.unpackit(user_result)
    n_user.applications_.append(appname)
    t = datetime.datetime.now()
    n_user.date_change_ = str(time.mktime(t.timetuple()))
    n_app = Apps(appname, user, language)
    array = n_user.arrayit()

    result = db.put_entity(USER_TABLE, user, user_schema, array) 
    if result[0] in ERROR_CODES:
      ret = "true"
    else: 
      return "false" 
    
    array = n_app.arrayit()
    result = db.put_entity(APP_TABLE, appname, app_schema, array)
    if result[0] in ERROR_CODES:
      ret = "true"
    else:
      return "false"
    return ret
  else:
    error = "Error: User not found"
    return error

def get_tar(app_name, secret):
  global db
  global super_secret
  if secret != super_secret:
    return "Error: bad secret"
  result = db.get_entity(APP_TABLE, app_name, ["tar_ball"])
  if result[0] in ERROR_CODES and len(result) == 2:
    return result[1]
  else:
    return "Error:" + result[0]

def commit_tar(app_name, tar, secret):
  global db
  global super_secret
  global app_schema

  if secret != super_secret:
    return "Error: bad secret"

  if does_app_exist(app_name, secret) == "false":
    return "Error: app does not exist"


  columns = ["tar_ball", "version", "last_time_updated_date", "enabled"]
  result = db.get_entity(APP_TABLE, app_name, columns)
  if result[0] in ERROR_CODES and len(result) > 1:
    result = result[1:]
    values = []
    t = datetime.datetime.now()
    date = str(time.mktime(t.timetuple()))
    version = result[1]
    values += [tar]
    values += [str(int(version) + 1)]
    values += [date]
    values += ["true"] #enable bit
    result = db.put_entity(APP_TABLE, app_name, columns, values)
    if result[0] not in ERROR_CODES:
      return "Error: unable to commit new tar ball %s" % result[0]
  else:
    error = "Error: unable to get app %s" % result[0]
    return error
  return "true"

def delete_all_users(secret):
  global db
  global super_secret
  global user_schema
  users = []
  if secret != super_secret:
    return "Error: bad secret"

  result = db.get_table(USER_TABLE, user_schema)
  if result[0] not in ERROR_CODES:
    return "false"

  result = result[1:] 
  for ii in range(0, (len(result)/len(user_schema))):
    partial = result[(ii * len(user_schema)): ((1 + ii) * len(user_schema))]
    if len(partial) != len(user_schema):
      pass
    else: 
      u = Users("x", "x", "user")
      u.unpackit(partial)
      users.append(u)
  ret = "true"
  for ii in u:
    result = db.delete_row(USER_TABLE, ii.email_)      
    if result[0] not in ERROR_CODES:
      ret = "false"
  return ret 

def delete_all_apps(secret):
  global db
  global super_secret
  global app_schema
  if secret != super_secret:
    return "Error: bad secret"

  ret = "true"
  result = db.get_table(APP_TABLE, ['name'])
  if result[0] not in ERROR_CODES:
    return "false"
  result = result[1:] 
  for ii in result:
    if delete_app(ii, secret) == "false":
      ret = "false"
  return ret 

def get_all_users(secret):
  global db
  global super_secret
  global user_schema
  users = []
  if secret != super_secret:
    return "Error: bad secret"

  result = db.get_table(USER_TABLE, user_schema)
  if result[0] not in ERROR_CODES:
    return "Error:" + result[0]
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
  return userstring

def get_all_apps(secret):
  global db
  global super_secret
  global app_schema
  apps = []
  if secret != super_secret:
    return "Error: bad secret"

  result = db.get_table(APP_TABLE, app_schema)
  if result[0] not in ERROR_CODES:
    return "Error:" + result[0]
  result = result[1:] 
  for ii in range(0, (len(result)/len(app_schema))):
    partial = result[(ii * len(app_schema)): ((1 + ii) * len(app_schema))]
    if len(partial) != len(app_schema):
      pass
    else: 
      a = Apps("x", "x", "x")
      a.unpackit(partial)
      apps.append(a)
  
  # this is a placeholder, soap exception happens if returning empty string
  appstring = "____"
  for kk in apps:
    appstring += ":" + kk.name_
  return appstring

def add_instance(appname, host, port, secret):
  global db
  global super_secret
  global app_schema
  if secret != super_secret:
    return "Error: bad secret"
  
  columns = ["host", "port"]
  result = db.get_entity(APP_TABLE, appname, columns)
  error = result[0]
  if error not in ERROR_CODES or len(columns) != (len(result) - 1):
    return "false"

  # We only have one host/port for each app.
  result = db.put_entity(APP_TABLE, appname, columns, [host, str(port)]) 
  if result[0] not in ERROR_CODES:
    return "false"
  return "true" 

def add_class(appname, classname, namespace, secret):
  global db
  global super_secret
  global app_schema
  if secret != super_secret:
    return "Error: bad secret"
  
  columns = ["classes"]
  result = db.get_entity(APP_TABLE, appname, columns)
  error = result[0]
  if error not in ERROR_CODES or len(columns) != (len(result) - 1):
    return "Error: Unable to get entity for app"

  result = result[1:]

  if result[0]: 
    classes = result[0].split(':')
  else:
    classes = []
  for c in classes:
    if c == classname:
      # already in classes list
      return "true"

  classes += [str(classname+"___"+namespace)]
  classes = ':'.join(classes)

  result = db.put_entity(APP_TABLE, appname, columns, [classes]) 
  if result[0] not in ERROR_CODES:
    return "false: Unable to put entity for app"
  return "true" 

def delete_app(appname, secret):
  global db
  global super_secret
  if secret != super_secret:
    return "Error: bad secret"

  result = db.get_entity(APP_TABLE, appname, ["owner"])
  if result[0] not in ERROR_CODES or len(result) == 1:
    return "false: unable to get entity for app"
  # look up all the class tables of this app and delete their tables
  result = db.get_entity(APP_TABLE, appname, ["classes"])
  if result[0] not in ERROR_CODES or len(result) == 1:
    return "false: unable to get classes for app"
  result = result[1:]
  if result[0]:
    classes = result[0].split(':')
  else:
    classes = []
  result = db.put_entity(APP_TABLE, appname, ["host", "port"], ["", ""])
  if result[0] not in ERROR_CODES:
    return "false: unable to delete instances"

  for classname in classes:
    table_name = appname + "___" + classname
    db.delete_table(table_name)

  result = db.put_entity(APP_TABLE, appname, ["classes", "num_entries"], ["", "0"])
  if result[0] not in ERROR_CODES:
    return "Error: unable to clear classes"

  # disabling the app, a type of soft delete 
  return disable_app(appname, secret)
  
def delete_instance(appname, host, port, secret):
  global db
  global super_secret
  global app_schema
  if secret != super_secret:
    return "Error: bad secret"

  ret = "true"
  result = db.get_entity(APP_TABLE, appname, ['host', 'port'])
  error = result[0]
  if error not in ERROR_CODES or len(result) == 1:
    return "false"
  result = result[1:]

  hosts = []
  ports = []

  if result[0]: hosts = result[0].split(':') 
  if result[1]: ports = result[1].split(':')
  if len(hosts) != len(ports):
    return "Error: bad number of hosts to ports"

  for kk in range(0, len(hosts)):
    if str(hosts[kk]) == str(host) and str(ports[kk]) == str(port):
      del hosts[kk]
      del ports[kk]

  hosts = ':'.join(hosts)
  ports = ':'.join(ports)

  result = db.put_entity(APP_TABLE, appname, ['host', 'port'], [hosts, ports]) 
  if result[0] not in ERROR_CODES:
    return "false"
  return ret 

def commit_new_token(user, token, token_exp, secret):
  global db
  global super_secret
  global user_schema
  if secret != super_secret:
    return "Error: bad secret"
  columns = ['appdrop_rem_token', 'appdrop_rem_token_exp']
  result = db.get_entity(USER_TABLE, user, columns)
  if result[0] not in ERROR_CODES or len(result) == 1:
    return "Error: User does not exist" 

  result = result[1:]
  #appdrop_rem_token = result[0] 
  #appdrop_rem_token_exp = result[1] 
  t = datetime.datetime.now()
  date_change = str(time.mktime(t.timetuple()))

  values = [token, token_exp, date_change]
  columns += ['date_change'] 

  result = db.put_entity(USER_TABLE, user, columns, values)
  if result[0] not in ERROR_CODES:
    return "false"
  return "true"

def get_token(user, secret):
  global db
  global super_secret
  if secret != super_secret:
    return "Error: bad secret"
  columns = ['appdrop_rem_token', 'appdrop_rem_token_exp']
  result = db.get_entity(USER_TABLE, user, columns)
  if result[0] not in ERROR_CODES or len(result) == 1:
    return "false"
  result = result[1:]
  return "token:"+ result[0] + "\n" + "token_exp:" + result[1] + "\n"

def get_version(appname, secret):
  global db
  global super_secret
  if secret != super_secret:
    return "Error: bad secret"
  columns = ['version']
  result = db.get_entity(APP_TABLE, appname, columns)
  if result[0] not in ERROR_CODES or len(result) == 1:
    return "false"
  result = result[1:]
  return "version: " + result[0] + "\n"
 
def change_password(user, password, secret):
  global db
  global super_secret
  global user_schema
  
  if secret != super_secret:
    return "Error: bad secret"

  if not password:
    return "Error: Null password"

  result = db.get_entity(USER_TABLE, user, ['enabled'])
  if result[0] not in ERROR_CODES or len(result) == 1:
    return "Error: user does not exist"

  if result[1] == "false":
    return "Error: User must be enabled to change password"

  result = db.put_entity(USER_TABLE, user, ['pw'], [password])
  if result[0] not in ERROR_CODES:
    return "Error:" + result[0]
  return "true"

def enable_app(appname, secret):
  global db
  global super_secret
  global app_schema
  if secret != super_secret:
    return "Error: bad secret"

  result = db.get_entity(APP_TABLE, appname, ['enabled'])
  if result[0] not in ERROR_CODES or len(result) != 2:
    return "Error: " + result[0]
  if result[1] == "true":
    return "Error: Trying to enable an application that is already enabled"

  result = db.put_entity(APP_TABLE, appname, ['enabled'], ['true'])
  if result[0] not in ERROR_CODES:
    return "false"
  return "true"


def disable_app(appname, secret):
  global db
  global super_secret
  global app_schema
  if secret != super_secret:
    return "Error: bad secret"
  result = db.get_entity(APP_TABLE, appname, ['enabled'])
  if result[0] not in ERROR_CODES or len(result) != 2:
    return "Error: " + result[0]
  if result[1] == "false":
    return "Error: Trying to disable an application twice"
  result = db.put_entity(APP_TABLE, appname, ['enabled'], ['false'])
  if result[0] not in ERROR_CODES:
    return "false"
  return "true"

def is_app_enabled(appname, secret):
  global db
  global super_secret
  global app_schema
  if secret != super_secret:
    return "Error: bad secret"
  result = db.get_entity(APP_TABLE, appname, ['enabled'])
  if result[0] not in ERROR_CODES or len(result) != 2:
    return "false" 
  return result[1]
 
def enable_user(user, secret):
  global db
  global super_secret
  global user_schema
  if secret != super_secret:
    return "Error: bad secret"
  result = db.get_entity(USER_TABLE, user, ['enabled'])
  if result[0] not in ERROR_CODES or len(result) != 2:
    return "Error: " + result[0]
  if result[1] == "true":
    return "Error: Trying to enable a user twice"
  result = db.put_entity(USER_TABLE, user, ['enabled'], ['true'])
  if result[0] not in ERROR_CODES:
    return "false"
  return "true"


def disable_user(user, secret):
  global db
  global user_schema
  global super_secret
  if secret != super_secret:
    return "Error: bad secret"
  result = db.get_entity(USER_TABLE, user, ['enabled'])
  if result[0] not in ERROR_CODES or len(result) != 2:
    return "Error: " + result[0]
  if result[1] == "false":
    return "Error: Trying to disable a user twice"

  result = db.put_entity(USER_TABLE, user, ['enabled'], ['false'])
  if result[0] not in ERROR_CODES:
    return "false"
  return "true"

def delete_user(user, secret):
  global db
  global user_schema
  global super_secret
  if secret != super_secret:
    return "Error: bad secret"
  result = db.get_entity(USER_TABLE, user, ['enabled'])
  if result[0] not in ERROR_CODES or len(result) != 2:
    return "false"

  if result[1] == 'true':
    return "Error: unable to delete active user. Disable user first"

  result = db.delete_row(USER_TABLE, user)
  if result[0] not in ERROR_CODES:
    return "false"
  return "true"

def is_user_enabled(user, secret):
  global db
  global super_secret
  global user_schema
  if secret != super_secret:
    return "Error: bad secret"
  result = db.get_entity(USER_TABLE, user, ['enabled'])
  if result[0] not in ERROR_CODES or len(result) == 1:
    return "false" 
  return result[1]

def get_key_block(app_id, block_size, secret):
  global db
  global super_secret
  global app_schema
  if secret != super_secret:
    return "Error: bad secret"
  result = db.get_entity(APP_TABLE, app_id, ['num_entries'])
  if result[0] not in ERROR_CODES or len(result) == 1:
    return "false"
  key = result[1]
  if key == "0":
    key = "1"
  next_key = str(int(key) + int(block_size))
  #Update number of entries
  result = db.put_entity(APP_TABLE, app_id, ['num_entries'], [next_key])
  if result[0] not in ERROR_CODES:
    return "false"
  return key

def is_user_cloud_admin(username, secret):
  global db
  global super_secret
  if secret != super_secret:
    return "Error: bad secret"
  result = db.get_entity(USER_TABLE, username, ["is_cloud_admin"])
  if result[0] in ERROR_CODES and len(result) == 2:
    return result[1]
  else:
    return "false"

def set_cloud_admin_status(username, is_cloud_admin, secret):
  global db
  global super_secret
  if secret != super_secret:
    return "Error: bad secret"
  result = db.put_entity(USER_TABLE, username, ['is_cloud_admin'], [is_cloud_admin])
  if result[0] not in ERROR_CODES:
    return "false:" + result[0]
  return "true"

def get_capabilities(username, secret):
  global db
  global super_secret
  if secret != super_secret:
    return "Error: bad secret"
  result = db.get_entity(USER_TABLE, username, ["capabilities"])
  if result[0] in ERROR_CODES and len(result) == 2:
    return result[1]
  else:
    return [result[0]]

def set_capabilities(username, capabilities, secret):
  global db
  global super_secret
  if secret != super_secret:
    return "Error: bad secret"
  result = db.put_entity(USER_TABLE, username, ['capabilities'], [capabilities])
  if result[0] not in ERROR_CODES:
    return "false:" + result[0]
  return "true"

def usage():
  print "args: --apps or -a for the application location"
  print "      --users or -u for the user location"
  print "      --type or -t for type of datastore"
  print "        type available: cassandra"
  print "      --port or -p for server port"

if __name__ == "__main__":
  """ Main function for running the server. """
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
  if not datastore_type in \
    appscale_datastore.DatastoreFactory.valid_datastores():
    exit(2)

  # Keep trying until it gets the schema.
  timeout = 5
  while 1:
    user_schema = db.get_schema(USER_TABLE)
    if user_schema[0] in ERROR_CODES:
      user_schema = user_schema[1:]
      Users.attributes_ = user_schema
    else:
      time.sleep(timeout)
      continue
    app_schema = db.get_schema(APP_TABLE)
    if app_schema[0] in ERROR_CODES:
      app_schema = app_schema[1:]
      Apps.attributes_ = app_schema
    else:
      time.sleep(timeout)
      continue
    break

  ip = "0.0.0.0"
  server = SOAPpy.SOAPServer((ip, bindport))
  # To debug this service, uncomment the 2 lines below.
  #server.config.dumpSOAPOut = 1
  #server.config.dumpSOAPIn = 1

  # Register soap functions.
  server.registerFunction(add_class)
  server.registerFunction(add_instance)
  server.registerFunction(does_user_exist)
  server.registerFunction(does_app_exist)

  server.registerFunction(get_key_block)
  server.registerFunction(get_all_apps)
  server.registerFunction(get_all_users)
  server.registerFunction(get_user_data)
  server.registerFunction(get_app_data)
  server.registerFunction(get_tar)
  server.registerFunction(get_token)
  server.registerFunction(get_version)
  server.registerFunction(add_admin_for_app)
  server.registerFunction(commit_new_user)
  server.registerFunction(commit_new_app)
  server.registerFunction(commit_tar)
  server.registerFunction(commit_new_token)
  server.registerFunction(delete_instance)
  server.registerFunction(delete_all_users)
  server.registerFunction(delete_all_apps)
  server.registerFunction(delete_user)
  server.registerFunction(delete_app)

  server.registerFunction(change_password)

  server.registerFunction(disable_app)
  server.registerFunction(enable_app)
  server.registerFunction(is_app_enabled)
  server.registerFunction(disable_user)
  server.registerFunction(enable_user)
  server.registerFunction(is_user_enabled)

  server.registerFunction(is_user_cloud_admin)
  server.registerFunction(set_cloud_admin_status)
  server.registerFunction(get_capabilities)
  server.registerFunction(set_capabilities)

  while 1:
    server.serve_forever()
