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
  def setup_transaction(self, txnid):
    raise NotImplementedError("rollback is not implemented in %s." % self.__class__)
