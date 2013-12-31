# Programmer: Navraj Chohan <nlake44@gmail.com>
"""
 Datastore Constants
"""
SECRET_LOCATION = "/etc/appscale/secret.key"

ERROR_DEFAULT = "DB_ERROR:"
NONEXISTANT_TRANSACTION = "0"
KEY_DELIMITER = '\x00'
KIND_SEPARATOR = '\x01'

# Table names
USERS_TABLE = "USERS__"
APPS_TABLE = "APPS__"
JOURNAL_TABLE = "JOURNAL__"

ASC_PROPERTY_TABLE = "ASC_PROPERTY__"
DSC_PROPERTY_TABLE = "DSC_PROPERTY__"
COMPOSITE_TABLE = "COMPOSITE_INDEXES__"
APP_ID_TABLE = "APP_IDS__"
APP_ENTITY_TABLE = "ENTITIES__"
APP_KIND_TABLE = "KINDS__"
JOURNAL_TABLE = "JOURNAL__"
METADATA_TABLE = "METADATA__"

INITIAL_TABLES = [ASC_PROPERTY_TABLE,
                  DSC_PROPERTY_TABLE,
                  APP_ID_TABLE,
                  APP_ENTITY_TABLE,
                  APP_KIND_TABLE,
                  COMPOSITE_TABLE,
                  JOURNAL_TABLE,
                  METADATA_TABLE]

###########################################
# DB schemas for version 1 of the datastore
###########################################
JOURNAL_SCHEMA = [
  "Encoded_Entity"]

ENTITY_TABLE_SCHEMA = [
  "Encoded_Entity",
  "Txn_Num"]

###########################################
# DB schema for version 2 of the datastore
###########################################

# The schema of the table which holds the encoded entities
APP_ENTITY_SCHEMA = [
  "entity",
  "txnID"]

# Index tables store references are to entity table
PROPERTY_SCHEMA = [
  "reference" ]
APP_ID_SCHEMA = [
  "next_id" ]
APP_KIND_SCHEMA = [
  "reference" ]
COMPOSITE_SCHEMA = [
  "reference" ]
METADATA_SCHEMA = [
  "data" ]

USERS_SCHEMA = [
  "email",
  "pw",
  "date_creation", 
  "date_change",
  "date_last_login",
  "applications",
  "appdrop_rem_token",
  "appdrop_rem_token_exp",
  "visit_cnt",
  "cookie",
  "cookie_ip",
  "cookie_exp",
  "cksum",
  "enabled",
  "type",
  "is_cloud_admin",
  "capabilities" ]

APPS_SCHEMA = [
  "name",
  "language",
  "version",
  "owner",
  "admins_list",
  "host",
  "port",
  "creation_date",
  "last_time_updated_date",
  "yaml_file",
  "cksum",
  "num_entries",
  "tar_ball",
  "enabled",
  "classes",
  "indexes" ]

###############################
# Generic Datastore Exceptions
###############################
class AppScaleDBConnectionError(Exception):
  """ Tossed when there is a bad connection
  """ 
  def __init__(self, value):
    Exception.__init__(self, value)
    self.value = value
  def __str__(self):
    return repr(self.value)

class AppScaleMisconfiguredQuery(Exception):
  """ Tossed when a query is misconfigured
  """
  def __init__(self, value):
    Exception.__init__(self, value)
    self.value = value
  def __str__(self):
    return repr(self.value)

class AppScaleBadArg(Exception):
  """ Bad Argument given for a function
  """
  def __init__(self, value):
    Exception.__init__(self, value)
    self.value = value
  def __str__(self):
    return repr(self.value)

