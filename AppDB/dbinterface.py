# 
# AppScale Datastore Interface 
#
__author__="Soo Hwan Park"
__date__="$2009.5.5 18:27:00$"

import os

class AppDBInterface:
  def get_entity(self, table_name, row_key, column_names, txnid = 0):  
    raise NotImplementedError("get_entity is not implemented in %s." % self.__class__)

  def put_entity(self, table_name, row_key, column_names, cell_values, txnid = 0):
    raise NotImplementedError("put_entity is not implemented in %s." % self.__class__)

  def put_entity_dict(self, table_name, row_key, value_dict):
    raise NotImplementedError("put_entity_dict is not implemented in %s." % self.__class__)

  def get_table(self, table_name, column_names, txnid = 0):
    raise NotImplementedError("get_table is not implemented in %s." % self.__class__)

  def delete_row(self, table_name, row_id, txnid = 0):
    raise NotImplementedError("delete_row is not implemented in %s." % self.__class__)

  def get_schema(self, table_name):
    raise NotImplementedError("get_schema is not implemented in %s." % self.__class__)

  def delete_table(self, table_name):
    raise NotImplementedError("delete_table is not implemented in %s." % self.__class__)

  def commit(self, txnid):
    raise NotImplementedError("commit is not implemented in %s." % self.__class__)
  def rollback(self, txnid):
    raise NotImplementedError("rollback is not implemented in %s." % self.__class__)
  def setupTransaction(self, txnid):
    raise NotImplementedError("rollback is not implemented in %s." % self.__class__)
    

  def get_local_ip(self):
    try:
      local_ip = self.__local_ip
    except AttributeError:
      local_ip = None

    if local_ip is None:
      local_ip = os.environ.get("LOCAL_DB_IP")

      if local_ip is None:
        raise Exception("Env var LOCAL_DB_IP was not set.")
      else:
        self.__local_ip = local_ip

    return self.__local_ip

  def get_master_ip(self):
    try:
      master_ip = self.__master_ip
    except AttributeError:
      master_ip = None

    if master_ip is None:
      master_ip = os.environ.get("MASTER_IP")

      if master_ip is None:
        raise Exception("Env var MASTER_IP was not set.")
      else:
        self.__master_ip = master_ip

    return self.__master_ip

