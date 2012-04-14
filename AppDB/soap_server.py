# Author: Navraj Chohan
# 2nd major revision: No longer are tables being cached in memory
# See LICENSE file


# we don't use PYTHONPATH now.
#PYTHON_PATH = os.environ.get("PYTHONPATH")
#print "Python path: ",PYTHON_PATH
#print sys.path

import sys
import SOAPpy
import time
import datetime
import re
from dbconstants import *
import appscale_datastore
import appscale_logger
from M2Crypto import SSL

logger = appscale_logger.getLogger("soap_server")

APP_TABLE = APPS_TABLE
USER_TABLE = USERS_TABLE
DEFAULT_USER_LOCATION = ".flatfile_users"
DEFAULT_APP_LOCATION = ".flatfile_apps"
DEFAULT_DATASTORE = "hbase"
DEFAULT_SSL_PORT = 4343
DEFAULT_PORT = 9899
IP_TABLE = "IPS___"
DEFAULT_ENCRYPTION = 1
VALID_DATASTORES = []   
CERT_LOCATION = APPSCALE_HOME + "/.appscale/certs/mycert.pem" 
KEY_LOCATION = APPSCALE_HOME + "/.appscale/certs/mykey.pem" 
SECRET_LOCATION = APPSCALE_HOME + "/.appscale/secret.key"
user_location = DEFAULT_USER_LOCATION
app_location = DEFAULT_APP_LOCATION
datastore_type = DEFAULT_DATASTORE
encryptOn = DEFAULT_ENCRYPTION
bindport = DEFAULT_SSL_PORT

ERROR_CODES = []
super_secret = ""
DEBUG = True
db = []
user_schema = []
app_schema = []

APPNAME_REGEX = r'^[\d\w\.@-]+$'
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
    #try:
    for ii in range(0,len(array)):
      setattr(self, Users.attributes_[ii] + "_", array[ii])
    #except Exception, ex:
    #  print ex
    #  return    
    
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
   #try:
    for ii in range(0,len(array)):
      setattr(self, Apps.attributes_[ii] + "_", array[ii])
    #except Exception, ex:
    #  print ex
     # return    
    
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
    #logger.error("does_user_exist: bad secret")
    return "Error: bad secret"
  if DEBUG: print "Checking to see if user %s exist"%username
  result = db.get_entity(USER_TABLE, username, ["email"])
  if result[0] in ERROR_CODES and len(result) == 2:
    if DEBUG: print "true"
    return "true" 
  else:
    if DEBUG: print "false"
    return "false"    

def does_app_exist(appname, secret):
  global db
  global super_secret
  if secret != super_secret:
    #logger.error("does_app_exist: bad secret")
    return "Error: bad secret"
  if DEBUG: print "Checking to see if app %s exist"%appname
  result = db.get_entity(APP_TABLE, appname, ["name"])
  if result[0] in ERROR_CODES and len(result) == 2:
    if DEBUG: print "true"
    return "true"
  else:
    if DEBUG: print "false"
    return "false"    

def get_user_apps(username, secret):
  global db
  global super_secret
  if secret != super_secret:
    #logger.error("get_user_apps: bad secret")
    return "Error: bad secret"
  if DEBUG: print "Getting user %s apps"%username
  result = db.get_entity(USER_TABLE, username, ["applications"])
  if result[0] in ERROR_CODES and len(result) == 2:
    if DEBUG: print result[1]
    return result[1] 
  else:
    error = "Error: user not found"  
    #logger.error(error)
    if DEBUG: print error
    return error

def get_user_data(username, secret):
  global db
  global super_secret
  global user_schema
  if secret != super_secret:
    #logger.error("get_user_data: bad secret")
    return "Error: bad secret"
  if DEBUG: print "Getting user %s data"%username 
  result = db.get_entity(USER_TABLE, username, user_schema)
   
  if result[0] in ERROR_CODES or len(result) == 1:
    if DEBUG: print result[1:]
    result = result[1:]
  else:
    #logger.error(result[0])
    if DEBUG: print result[0]
    return "Error: " + result[0]
  #print "user result:"
  #print result
  if len(user_schema) != len(result):
    #logger.error("Bad length of user schema vs user result")
    return "Error: Bad length of user schema vs user result user schem:" + str(user_schema) + " result: " + str(result)

  user = Users("a","b", "c")
  user.unpackit(result)
  return user.stringit()

def get_app_data(appname, secret):
  global db
  global super_secret
  global app_schema
  if secret != super_secret:
    #logger.error("get_app_data: bad secret")
    return "Error: bad secret"
  if not appname or  not secret:
    #logger.error("get_app_data: null appname")
    return "Error: Null appname"
    
  result = db.get_entity(APP_TABLE, appname, app_schema)

  if result[0] not in ERROR_CODES or len(result) == 1:
    #logger.error(result[0])
    return "Error: " + result[0]

  result = result[1:]

  if len(app_schema) != len(result):
    error = "Error: Bad length of app schema vs app result " + str(app_schema) + " vs " + str(result) + " for appname: " + appname
    #logger.error(error)
    if DEBUG: print error
    return  error 
  app = Apps("a","b", "c")
  app.unpackit(result)
  return app.stringit()

def commit_new_user(user, passwd, utype, secret):  
  global db
  global super_secret
  global user_schema
  if secret != super_secret:
    #logger.error("commit_new_user: bad secret")
    return "Error: bad secret"
  if utype not in VALID_USER_TYPES:
    return "Error: Not a valid user type %s"%utype
  if DEBUG: print "Commiting a new user %s"%user
  error =  "Error: username should be an email"
  # look for the @ and . in the email
  if user.find("@") == -1 or user.find(".") == -1:
    #logger.error(error)
    if DEBUG: print error
    return error
  
  error = "Error: user already exist"
  ret = does_user_exist(user, secret)
  if ret == "true":
    if DEBUG: print error
    return error

  n_user = Users(user, passwd, utype)
  array = n_user.arrayit()
  result = db.put_entity(USER_TABLE, user, user_schema, array) 
  if result[0] not in ERROR_CODES:
    if DEBUG: print "false"
    if DEBUG: print result[0]
    return "false"
  if DEBUG: print "true"
  return "true"

def commit_new_app(appname, user, language, secret):
  global db
  global user_schema
  global app_schema
  global super_secret
  if secret != super_secret:
    #logger.error("commit_new_app: bad secret")
    return "Error: bad secret"
  if DEBUG: print "Commiting a new application"
  #logger.error("commit_new_app: " + user + " and " + appname + " and " + language)
  """ 
  error =  "Error: username and appname collide"
  # check to see if appnames and user names collide
  for ii in apps:
    if ii.name_ == user:
      logger.error(error)
      return error
  """ 

  error =  "Error: appname/language can only be alpha numeric"
 
  if not language.isalnum():
    #logger.error("language %s is not alpha numeric" % language)
    if DEBUG: print error
    return error

  if re.search(APPNAME_REGEX,appname) is None:
    #logger.error("appname %s is not alpha numeric" % appname)
    if DEBUG: print error
    return error

  error =  "Error: appname already exist"
  if does_app_exist(appname, secret) == "true":
    #logger.error("appname already exist: %s" % appname)
    if DEBUG: print error
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
      #logger.error("updating user put: %s failed %s" % (user, result[0]))
      return "false" 
    
    array = n_app.arrayit()
    result = db.put_entity(APP_TABLE, appname, app_schema, array)
    if result[0] in ERROR_CODES:
      ret = "true"
    else:
      #logger.error("creating a new app: %s failed %s" % (appname, result[0])) 
      return "false"
    return ret
  else:
    error = "Error: User not found"
    #logger.error(error)
    if DEBUG: print error
    return error

def get_tar(app_name, secret):
  global db
  global super_secret
  #logger.info("get_tar app:%s, secret:%s" % (app_name, secret)) 
  if secret != super_secret:
    #logger.debug("get_tar: bad secret")
    return "Error: bad secret"
  if DEBUG: print "get_tar: entry" 
  result = db.get_entity(APP_TABLE, app_name, ["tar_ball"])
  if result[0] in ERROR_CODES and len(result) == 2:
    #logger.info("get_tar app:%s length of tar %s" % (app_name, str(len(result[1]))) )
    return result[1]
  else:
    #logger.error(error + result[0])
    if DEBUG: print result[0]
    return "Error:" + result[0]

def commit_tar(app_name, tar, secret):
  global db
  global super_secret
  global app_schema
  if DEBUG: print "commit_tar: entry"

  #logger.info("commit_tar app:%s, secret:%s" % (app_name, secret))
  if DEBUG: print "Committing a tar for %s"%app_name
  if secret != super_secret:
    #logger.error("commit_tar: bad secret")
    return "Error: bad secret"

  if does_app_exist(app_name, secret) == "false":
    #logger.error("commit_tar: app does not exist %s" %(app_name)) 
    if DEBUG: "Error app does not exist"
    return "Error: app does not exist"

  if DEBUG: print "commit_tar: attempting get"

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
      #logger.error("commit_tar: unable to commit new app tar ball %s" % (result[0])) 
      return "Error: unable to commit new tar ball %s" % result[0]
  else:
    error = "Error: unable to get app %s" % result[0]
    #logger.error("commit_tar--" + error)
    return error
  if DEBUG: print "commit_tar: exiting successfully"
  return "true"

def delete_all_users(secret):
  global db
  global super_secret
  global user_schema
  users = []
  if secret != super_secret:
    #logger.error("delete_all_users: bad secret")
    return "Error: bad secret"

  result = db.get_table(USER_TABLE, user_schema)
  if result[0] not in ERROR_CODES:
    #logger.error("delete_all_users: Unable to get user table")
    return "false"

  result = result[1:] 
  for ii in range(0, (len(result)/len(user_schema))):
    partial = result[(ii * len(user_schema)): ((1 + ii) * len(user_schema))]
    if len(partial) != len(user_schema):
      pass
      #logger.warn("%d size  partial: %s" % (len(partial), partial))
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
    #logger.error("delete_all_users: bad secret")
    return "Error: bad secret"

  ret = "true"
  result = db.get_table(APP_TABLE, ['name'])
  if result[0] not in ERROR_CODES:
    #logger.error("delete_all_app: Unable to get apps table")
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
    #logger.error("get_all_users: bad secret")
    return "Error: bad secret"

  result = db.get_table(USER_TABLE, user_schema)
  if result[0] not in ERROR_CODES:
    #logger.error("get_all_user: Unable to get apps table")
    return "Error:" + result[0]
  result = result[1:] 
  for ii in range(0, (len(result)/len(user_schema))):
    partial = result[(ii * len(user_schema)): ((1 + ii) * len(user_schema))]
    if len(partial) != len(user_schema):
      pass
      #logger.warn("%d size  partial: %s" % (len(partial), partial))
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
    #logger.error("get_all_apps: bad secret")
    return "Error: bad secret"

  result = db.get_table(APP_TABLE, app_schema)
  if result[0] not in ERROR_CODES:
    #logger.error("get_all_app: Unable to get apps table")
    return "Error:" + result[0]
  result = result[1:] 
  for ii in range(0, (len(result)/len(app_schema))):
    partial = result[(ii * len(app_schema)): ((1 + ii) * len(app_schema))]
    if len(partial) != len(app_schema):
      pass
      #logger.warn("%d size  partial: %s" % (len(partial), partial))
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
    #logger.error("add_instance: bad secret")
    return "Error: bad secret"
  
  columns = ["host", "port"]
  result = db.get_entity(APP_TABLE, appname, columns)
  error = result[0]
  if error not in ERROR_CODES or len(columns) != (len(result) - 1):
    #logger.error("add_instance: Unable to get entity for app %s" % appname)
    #logger.error("cgb: result[0] was --%s--"%str(result[0]))
    return "false"

  if DEBUG: logger.error("add_instance: %s" % result)
  #logger.error("add_instance: result %s" % result)
  hosts = []
  ports = []
  result = result[1:]

  if result[0]: hosts = result[0].split(':')
  if result[1]: ports = result[1].split(':')

  hosts += [str(host)]
  ports += [str(port)]
  hosts = ':'.join(hosts)
  ports = ':'.join(ports)

  result = db.put_entity(APP_TABLE, appname, columns, [hosts,ports]) 
  if result[0] not in ERROR_CODES:
    #logger.error("add_instance: Unable to put entity for app %s" %appname)
    #logger.error("cgb: result[0] was --%s--"%str(result[0]))
    return "false"
  return "true" 

def add_class(appname, classname, namespace, secret):
  global db
  global super_secret
  global app_schema
  if secret != super_secret:
    #logger.error("add_class: bad secret")
    return "Error: bad secret"
  
  columns = ["classes"]
  result = db.get_entity(APP_TABLE, appname, columns)
  error = result[0]
  if error not in ERROR_CODES or len(columns) != (len(result) - 1):
    #logger.error("add_class: Unable to get entity for app %s" % appname)
    return "Error: Unable to get entity for app"

  if DEBUG: logger.error("add_class: %s" % result)
  #logger.error("add_class: result %s" % result)
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
    #logger.error("add_class: Unable to put entity for app %s" %appname)
    return "false: Unable to put entity for app"
  return "true" 

def delete_app(appname, secret):
  global db
  global super_secret
  if secret != super_secret:
    #logger.error("delete_app: bad secret")
    return "Error: bad secret"

  result = db.get_entity(APP_TABLE, appname, ["owner"])
  if result[0] not in ERROR_CODES or len(result) == 1:
    #logger.error("delete_app: Unable to get entity for app %s" %appname)
    return "false: unable to get entity for app"
  """
  owner = result[1]
  result = db.get_entity(USER_TABLE, owner, ['applications'])
  if result[0] not in ERROR_CODES and len(result) == 1:
    logger.error("delete_app: Unable to get entity for app %s" %appname)
    return "false: unable to get entity for users app"
  result = result[1:]
  try:
    applications = result[0].split(':')
    applications.remove(appname)
  except: 
    # Unable to find app
    return "false: unable to find app in users app list:%s"%(str(result))
  applications = ':'.join(applications)
  t = datetime.datetime.now()
  date_change = str(time.mktime(t.timetuple()))

  result = db.put_entity(USER_TABLE, owner, ['applications', 'date_change'], 
    [applications, date_change])
  if result[0] not in ERROR_CODES and len(result) == 1:
    logger.error("delete_app: Unable to get entity for app %s" %appname)
    return "false: unable to put for user modified app list"
  """
  # look up all the class tables of this app and delete their tables
  result = db.get_entity(APP_TABLE, appname, ["classes"])
  if result[0] not in ERROR_CODES or len(result) == 1:
    #logger.error("delete_app: Unable to get classes for app %s"%appname)
    return "false: unable to get classes for app"
  result = result[1:]
  if result[0]:
    classes = result[0].split(':')
  else:
    classes = []
  result = db.put_entity(APP_TABLE, appname, ["host", "port"], ["", ""])
  if result[0] not in ERROR_CODES:
    #logger.error("delete_app: Unable to delete instances for app %s"%appname)
    return "false: unable to delete instances"

  for classname in classes:
    table_name = appname + "___" + classname
    db.delete_table(table_name)
    #logger.error("delete_app: removed %s"%table_name)

  result = db.put_entity(APP_TABLE, appname, ["classes", "num_entries"], ["", "0"])
  if result[0] not in ERROR_CODES:
    #logger.error("delete_app: Unable to clear classes for app %s"%appname)
    return "Error: unable to clear classes"


  #result = db.delete_row(APP_TABLE, appname)
  #if result[0] not in ERROR_CODES:
  #  logger.error("delete_app: Unable to delete entity for app %s" %appname)
  #  return "false"
  
  # disabling the app, a type of soft delete 
  return disable_app(appname, secret)
  
def delete_instance(appname, host, port, secret):
  global db
  global super_secret
  global app_schema
  if secret != super_secret:
    #logger.error("delete_instance: bad secret")
    return "Error: bad secret"

  ret = "true"
  result = db.get_entity(APP_TABLE, appname, ['host', 'port'])
  error = result[0]
  if error not in ERROR_CODES or len(result) == 1:
    #logger.error("delete_instance: Unable to get entity for app %s" % appname)
    return "false"
  result = result[1:]

  hosts = []
  ports = []

  if result[0]: hosts = result[0].split(':') 
  if result[1]: ports = result[1].split(':')
  #print hosts 
  #print ports 
  if len(hosts) != len(ports):
    #logger.error("delete_instance: inequal number of hosts and ports")
    return "Error: bad number of hosts to ports"
  for kk in range(0, len(hosts)):
    #print kk
    if str(hosts[kk]) == str(host) and str(ports[kk]) == str(port):
      del hosts[kk]
      del ports[kk]
      break
  hosts = ':'.join(hosts)
  ports = ':'.join(ports)

  result = db.put_entity(APP_TABLE, appname, ['host', 'port'], [hosts, ports]) 
  if result[0] not in ERROR_CODES:
    #logger.error("delete_instance: Unable to put entity for app %s" %appname)
    return "false"
  return ret 

def commit_new_token(user, token, token_exp, secret):
  global db
  global super_secret
  global user_schema
  if secret != super_secret:
    #logger.error("commit_new_token: bad secret")
    return "Error: bad secret"
  columns = ['appdrop_rem_token', 'appdrop_rem_token_exp']
  result = db.get_entity(USER_TABLE, user, columns)
  if result[0] not in ERROR_CODES or len(result) == 1:
    #logger.error("commit_new_token: unable to get user %s" %user)
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
    #logger.error("commit_new_token: unable to put user update %s" % user)
    return "false"
  return "true"

def get_token(user, secret):
  global db
  global super_secret
  if secret != super_secret:
    #logger.error("get_token: bad secret")
    return "Error: bad secret"
  columns = ['appdrop_rem_token', 'appdrop_rem_token_exp']
  result = db.get_entity(USER_TABLE, user, columns)
  if result[0] not in ERROR_CODES or len(result) == 1:
    #logger.error("get_token: unable to get user %s" %user)
    return "false"
  result = result[1:]
  return "token:"+ result[0] + "\n" + "token_exp:" + result[1] + "\n"

def get_version(appname, secret):
  global db
  global super_secret
  if secret != super_secret:
    #logger.error("get_version: bad secret")
    return "Error: bad secret"
  columns = ['version']
  result = db.get_entity(APP_TABLE, appname, columns)
  if result[0] not in ERROR_CODES or len(result) == 1:
    #logger.error("get_version: unable to get appname %s" %appname)
    return "false"
  result = result[1:]
  return "version: " + result[0] + "\n"
 
def change_password(user, password, secret):
  global db
  global super_secret
  global user_schema
  
  if secret != super_secret:
    #logger.error("change password: bad secret")
    return "Error: bad secret"

  if not password:
    #logger.error("change password: Null password")
    return "Error: Null password"

  result = db.get_entity(USER_TABLE, user, ['enabled'])
  if result[0] not in ERROR_CODES or len(result) == 1:
    #logger.error("change password: unable to get user %s" %user)
    return "Error: user does not exist"

  if result[1] == "false":
    #logger.error("change password: user must be enabled for password change")
    return "Error: User must be enabled to change password"

  result = db.put_entity(USER_TABLE, user, ['pw'], [password])
  if result[0] not in ERROR_CODES:
    #logger.error("change password: unable to put user update %s" % user)
    return "Error:" + result[0]
  return "true"

def enable_app(appname, secret):
  global db
  global super_secret
  global app_schema
  if secret != super_secret:
    #logger.error("enable_app: bad secret")
    return "Error: bad secret"

  result = db.get_entity(APP_TABLE, appname, ['enabled'])
  if result[0] not in ERROR_CODES or len(result) != 2:
    #logger.error("enable_app: " + result[0])
    return "Error: " + result[0]
  if result[1] == "true":
    #logger.error("enable_app: Trying to enable an enabled app")
    return "Error: Trying to enable an application that is already enabled"

  result = db.put_entity(APP_TABLE, appname, ['enabled'], ['true'])
  if result[0] not in ERROR_CODES:
    #logger.error("enable_app: unable to put app update %s" % appname)
    return "false"
  return "true"


def disable_app(appname, secret):
  global db
  global super_secret
  global app_schema
  if secret != super_secret:
    #logger.error("disable_app: bad secret")
    return "Error: bad secret"
  result = db.get_entity(APP_TABLE, appname, ['enabled'])
  if result[0] not in ERROR_CODES or len(result) != 2:
    #logger.error("disable_app: " + result[0])
    return "Error: " + result[0]
  if result[1] == "false":
    #logger.error("disable_app: Trying to disable a disabled app")
    return "Error: Trying to disable an application twice"
  result = db.put_entity(APP_TABLE, appname, ['enabled'], ['false'])
  if result[0] not in ERROR_CODES:
    #logger.error("disable_app: unable to put app update %s" % appname)
    return "false"
  return "true"

def is_app_enabled(appname, secret):
  global db
  global super_secret
  global app_schema
  if secret != super_secret:
    #logger.error("is_app_enabled: bad secret")
    return "Error: bad secret"
  result = db.get_entity(APP_TABLE, appname, ['enabled'])
  if result[0] not in ERROR_CODES or len(result) != 2:
    #logger.error("is_app_enabled: unable to get app %s" %appname)
    return "false" 
  return result[1]
 
def enable_user(user, secret):
  global db
  global super_secret
  global user_schema
  if secret != super_secret:
    #logger.error("enable_user: bad secret")
    return "Error: bad secret"
  result = db.get_entity(USER_TABLE, user, ['enabled'])
  if result[0] not in ERROR_CODES or len(result) != 2:
    #logger.error("enable_user: " + result[0])
    return "Error: " + result[0]
  if result[1] == "true":
    #logger.error("enable_user: Trying to enable an enabled user")
    return "Error: Trying to enable a user twice"
  result = db.put_entity(USER_TABLE, user, ['enabled'], ['true'])
  if result[0] not in ERROR_CODES:
    #logger.error("enable_user: unable to put user update %s" % user)
    return "false"
  return "true"


def disable_user(user, secret):
  global db
  global user_schema
  global super_secret
  if secret != super_secret:
    #logger.error("disable_user: bad secret")
    return "Error: bad secret"
  result = db.get_entity(USER_TABLE, user, ['enabled'])
  if result[0] not in ERROR_CODES or len(result) != 2:
    #logger.error("enable_user: " + result[0])
    return "Error: " + result[0]
  if result[1] == "false":
    #logger.error("enable_user: Trying to disable a disabled user")
    return "Error: Trying to disable a user twice"

  result = db.put_entity(USER_TABLE, user, ['enabled'], ['false'])
  if result[0] not in ERROR_CODES:
    #logger.error("disable_user: unable to put user update %s" % user)
    return "false"
  return "true"

def delete_user(user, secret):
  global db
  global user_schema
  global super_secret
  if secret != super_secret:
    #logger.error("delete_user: bad secret")
    return "Error: bad secret"
  result = db.get_entity(USER_TABLE, user, ['enabled'])
  if result[0] not in ERROR_CODES or len(result) != 2:
    #logger.error("delete_user: unable to retrieve user info for %s"%user)
    return "false"

  if result[1] == 'true':
    #logger.error("delete_user: tried to delete an active user %s"%user)
    return "Error: unable to delete active user. Disable user first"

  result = db.delete_row(USER_TABLE, user)
  if result[0] not in ERROR_CODES:
    #logger.error("delete_user: unable to delete user %s" % user)
    return "false"
  return "true"

def is_user_enabled(user, secret):
  global db
  global super_secret
  global user_schema
  if secret != super_secret:
    #logger.error("is_user_enabled: bad secret")
    return "Error: bad secret"
  result = db.get_entity(USER_TABLE, user, ['enabled'])
  if result[0] not in ERROR_CODES or len(result) == 1:
    #logger.error("is_user_enabled: unable to get user %s" %user)
    return "false" 
  return result[1]

def get_key_block(app_id, block_size, secret):
  global db
  global super_secret
  global app_schema
  if secret != super_secret:
    #logger.error("is_user_enabled: bad secret")
    return "Error: bad secret"
  result = db.get_entity(APP_TABLE, app_id, ['num_entries'])
  if result[0] not in ERROR_CODES or len(result) == 1:
    #logger.error("get_key_block: unable to get number of entries for table %s"%app_id)
    #logger.error("cgb: result[0] was --%s--"%str(result[0]))
    return "false"
  key = result[1]
  if key == "0":
    key = "1"
  next_key = str(int(key) + int(block_size))
  #Update number of entries
  result = db.put_entity(APP_TABLE, app_id, ['num_entries'], [next_key])
  if result[0] not in ERROR_CODES:
    #logger.error("get_key_block: unable to put updated number of entries for table %s"%app_id)
    #logger.error("cgb: result[0] was --%s--"%str(result[0]))
    return "false"
  return key

def commit_ip(ip, email, secret):
  global db
  global super_secret
  if secret != super_secret:
    #logger.error("commit_ip: bad secret")
    return "Error: bad secret"
  result = db.put_entity(IP_TABLE, ip, ['email'], [email])
  if result[0] not in ERROR_CODES:
    #logger.error("commit_ip:Error commiting new ip: " + result[0])
    return "false:" + result[0]
  return "true"

def get_ip(ip, secret):
  global db
  global super_secret
  if secret != super_secret:
    #logger.error("get_ip: bad secret")
    return "Error: bad secret"
  result = db.get_entity(IP_TABLE, ip, ['email'])
  if result[0] not in ERROR_CODES or len(result) != 2:
    #logger.error("get_ip:Error getting new ip: " + result[0])
    return "false:" + result[0]
  return result[1] 

def is_user_cloud_admin(username, secret):
  global db
  global super_secret
  if secret != super_secret:
    #logger.error("is_cloud_admin: bad secret")
    return "Error: bad secret"
  if DEBUG: print "Getting user %s cloud admin status"%username
  result = db.get_entity(USER_TABLE, username, ["is_cloud_admin"])
  if result[0] in ERROR_CODES and len(result) == 2:
    if DEBUG: print result[1]
    return result[1]
  else:
    if DEBUG: print "false"
    return "false"

def set_cloud_admin_status(username, is_cloud_admin, secret):
  global db
  global super_secret
  if secret != super_secret:
    #logger.error("set_cloud_admin_status: bad secret")
    return "Error: bad secret"
  result = db.put_entity(USER_TABLE, username, ['is_cloud_admin'], [is_cloud_admin])
  if result[0] not in ERROR_CODES:
    #logger.error("set_cloud_admin:Error commiting new ip: " + result[0])
    return "false:" + result[0]
  return "true"

def get_capabilities(username, secret):
  global db
  global super_secret
  if secret != super_secret:
    #logger.error("get_capabilities: bad secret")
    return "Error: bad secret"
  if DEBUG: print "Getting user %s capabilities"%username
  result = db.get_entity(USER_TABLE, username, ["capabilities"])
  if result[0] in ERROR_CODES and len(result) == 2:
    if DEBUG: print result[1]
    return result[1]
  else:
    if DEBUG: print [result[0]]
    return [result[0]]

def set_capabilities(username, capabilities, secret):
  global db
  global super_secret
  if secret != super_secret:
    #logger.error("set_capabilities: bad secret")
    return "Error: bad secret"
  result = db.put_entity(USER_TABLE, username, ['capabilities'], [capabilities])
  if result[0] not in ERROR_CODES:
    #logger.error("set_capabilities:Error commiting new ip: " + result[0])
    return "false:" + result[0]
  return "true"

def usage():
  print "args: --apps or -a for the application location"
  print "      --users or -u for the user location"
  print "      --type or -t for type of datastore"
  print "        type available: hypertable"
  print "                      mysql"
  print "                      hbase"
  print "                      cassandra"
  print "      --port or -p for server port"
  print "      --http for http rather than ssl"

if __name__ == "__main__":
  encrypt = 1

  for ii in range(1,len(sys.argv)):
    if sys.argv[ii] in ("-h", "--help"): 
      #print "help menu:"
      usage()
      sys.exit()
    elif sys.argv[ii] in ('-a', "--apps"):
      #print "apps location set to ",sys.argv[ii+ 1]
      app_location = sys.argv[ii + 1]
      ii += 1
    elif sys.argv[ii] in ('-u', "--users"):
      #print "user location set to ",sys.argv[ii+1]
      user_location = sys.argv[ii + 1]
      ii += 1
    elif sys.argv[ii] in ('-t', "--type"):
      #print "setting datastore type to ",sys.argv[ii+1]
      datastore_type = sys.argv[ii + 1]
      ii += 1
    elif sys.argv[ii] in ('-p', "--port"):
      #print "opening on port ", sys.argv[ii+1]
      bindport = int(sys.argv[ii + 1] )
      ii += 1
    elif sys.argv[ii] in ('-s','--secret'):
      #print "Your secret is safe with me. shhhhh!"
      super_secret = sys.argv[ii + 1]
      ii += 1
    elif sys.argv[ii] in ('--http'):
      #print "The connection is no longer encryptyed"
      encrypt = 0
    else:
      pass
      #print "Unknown option ",sys.argv[ii]
      #usage()
      #sys.exit(2)

  db = appscale_datastore.DatastoreFactory.getDatastore(datastore_type)
  ERROR_CODES = appscale_datastore.DatastoreFactory.error_codes()
  VALID_DATASTORES = appscale_datastore.DatastoreFactory.valid_datastores()
  if not datastore_type in VALID_DATASTORES:
    #print "Invalid type for datastore type: " + datastore_type
    #print "valid datestores include:"
    #print VALID_DATASTORES
    #usage()
    exit(2)

  # Keep trying until it gets the schema
  timeout = 5
  while 1:
    user_schema = db.get_schema(USER_TABLE)
    if user_schema[0] in ERROR_CODES:
      user_schema = user_schema[1:]
      Users.attributes_ = user_schema
    else:
      #error = "Error: unable to get user schema.\n Trying again in ",timeout,"seconds" 
      #print error
      #logger.info(error)
      time.sleep(timeout)
      #timeout = timeout * 2
      continue
    app_schema = db.get_schema(APP_TABLE)
    if app_schema[0] in ERROR_CODES:
      app_schema = app_schema[1:]
      Apps.attributes_ = app_schema
    else:
      #error = "Error: unable to get apps schema. \n Trying again in ",timeout,"seconds" 
      #print error
      #logger.info(error)
      time.sleep(timeout)
      #timeout = timeout * 2
      continue
    break

  # socket.gethostbyname(socket.gethostname())
  ip = "0.0.0.0"

  if super_secret == "":
    FILE = open(SECRET_LOCATION, 'r')
    super_secret = FILE.read()

  # Secure Socket Layer
  if encrypt == 1:
    ssl_context = SSL.Context()
    cert_location = CERT_LOCATION
    key_location = KEY_LOCATION
    ssl_context.load_cert(cert_location, key_location)

    server = SOAPpy.SOAPServer((ip, bindport), ssl_context = ssl_context)
  else:
    server = SOAPpy.SOAPServer((ip,bindport))
  #Register Functions

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
  server.registerFunction(get_ip)
  server.registerFunction(commit_new_user)
  server.registerFunction(commit_new_app)
  server.registerFunction(commit_tar)
  server.registerFunction(commit_new_token)
  server.registerFunction(commit_ip)
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
    try:
      # Run Server
      server.serve_forever()
    except SSL.SSLError:
      pass
      #logger.warn("Unexpected input on port %d for SOAP Server" % bindport)
      #print "WARNING: Unexpected input on port " + str(bindport) + "for SOAP Server"
