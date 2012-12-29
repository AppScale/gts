# Programmer: Navraj Chohan <nlake44@gmail.com>

""" 
 AppScale Datastore Interface 
"""
import os

class AppDBInterface:
  def batch_get_entity(self, table_name, row_key, column_names):
    """
    Takes in batches of keys and retrieves their cooresponding rows.
    
    Args:
      table_name: The table to access
      row_keys: A list of keys to access
      column_names: A list of columns to access
    Returns:
      A dictionary of rows and columns/values of those rows. The format 
      looks like such: {key:{column_name:value,...}}
    """

    raise NotImplementedError("get_entity is not implemented in %s." % self.__class__)
  def batch_put_entity(self, table_name, row_key, column_names, cell_values):
    """
    Allows callers to store multiple rows with a single call. A row can 
    have multiple columns and values with them. We refer to each row as 
    an entity.
   
    Args: 
      table_name: The table to mutate
      row_keys: A list of keys to store on
      column_names: A list of columns to mutate
      cell_values: A dict of key/value pairs
    Raises:
      TypeError: when bad arguments are given
    """

    raise NotImplementedError("put_entity is not implemented in %s." % self.__class__)

  def batch_delete(self, table_name, row_keys, column_names=[]):
    """
    Remove a set of rows cooresponding to a set of keys.
     
    Args:
      table_name: Table to delete rows from
      row_keys: A list of keys to remove
      column_names: Not used
    Raises:
      AppScaleDBConnectionError: when unable to execute deletes
      TypeError: when given bad argument types 
    """
    raise NotImplementedError("delete_row is not implemented in %s." % self.__class__)

  def delete_table(self, table_name):
    """ 
    Drops a given table.
  
    Args:
      table_name: A string name of the table to drop
    Rasies:
      TypeError: when given bad argument types 
    """
    raise NotImplementedError("delete_table is not implemented in %s." % self.__class__)

  def range_query(self,
                  table_name,
                  column_names,
                  start_key,
                  end_key,
                  limit, 
                  offset=0,
                  start_inclusive=True,
                  end_inclusive=True,
                  keys_only=False):
    """ 
    Gets a dense range ordered by keys. Returns an ordered list of 
    a dictionary of [key:{column1:value1, column2:value2},...]
    or a list of keys if keys only.
     
    Args:
      table_name: Name of table to access
      column_names: Columns which get returned within the key range
      start_key: String for which the query starts at
      end_key: String for which the query ends at
      limit: Maximum number of results to return
      offset: Cuts off these many from the results [offset:]
      start_inclusive: Boolean if results should include the start_key
      end_inclusive: Boolean if results should include the end_key
      keys_only: Boolean if to only keys and not values
    Raises:
      TypeError: when bad arguments are given
    Returns:
      An ordered list of dictionaries of key=>columns/values
    """
    raise NotImplementedError("range_query is not implemented in %s." % self.__class__)

  def create_table(self,table_name, column_names):
    """ 
    Creates a table given a schema (column_names).
    
    Args:
      table_name: The name of the table to create
      column_names: Not used but here to match the interface
    Raises:
      TypeError: when given bad argument types 
    """
    raise NotImplementedError("create_table is not implemented in %s." % self.__class__)

  def get_local_ip(self):
    """ Gets the local IP of the current node.
     
    Returns: 
      The local IP
    """

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
    """ Gets the master database IP of the current AppScale deployment.
    
    Returns: 
      The master DB IP
    """

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

    
      
