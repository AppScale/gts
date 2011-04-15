# Constants

import os
APPSCALE_HOME=os.environ.get("APPSCALE_HOME")

LOG_DIR = "%s/AppDB/logs" % APPSCALE_HOME

ERROR_DEFAULT = "DB_ERROR:"
NONEXISTANT_TRANSACTION = "0"

# DB schema

USERS_TABLE = "USERS__"
APPS_TABLE = "APPS__"
JOURNAL_TABLE = "JOURNAL__"
JOURNAL_SCHEMA = [
  "Encoded_Entity"]
ENTITY_TABLE_SCHEMA = [
  "Encoded_Entity",
  "Txn_Num" ]

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
