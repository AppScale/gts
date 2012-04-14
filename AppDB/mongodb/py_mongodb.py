#Written by Jovan Chohan

# First we get a connection to Mongo.
# Our Mongo instance must be running locally on port 27017.

import sys
import base64
import pymongo
from dbinterface import *
import sqlalchemy.pool as pool
import appscale_logger
import time
#Define some variables here
ERROR_MONGO = "DB_ERROR:"
DEBUG = False

class DatastoreProxy(AppDBInterface):
  def __init__(self, logger = appscale_logger.getLogger("datastore-mongodb")):
    self.logger = logger
    self.pool = pool.QueuePool(self.__create_connection)
    self.table_cache = []
    self.schema_cache = {}
  # "localhost", 27017
  def __create_connection(self):
    conn = pymongo.Connection()
    return conn

  def __init_connection(self):
    conn = self.pool.connect()
    return conn

  def __close_connection(self, conn):
    if conn:
      conn.close()

  def put_entity(self, table_name, row_key, column_names, cell_values):
    st = time.time()
    elist = [ERROR_MONGO]
    if (not row_key) or (not table_name):
      elist[0] += "Null row_key or table_name"
      return elist

    if len(column_names) != len(cell_values):
      elist[0] += "Amount of columns did not equal the amount of data"
      return elist

    #assuming that if the row already exists, delete and overwrite it

    columns = self.get_schema(table_name)
      #print "from get schema:"
      #print columns
    #print "Get schema",str(time.time() - st)
    if columns == [] or len(columns) == 1:
      self.create_table(table_name, column_names)
      columns = column_names
    else:
      columns = columns[1:]
    #print "Get schema",str(time.time() - st)

    db = self.__init_connection()
    collection = db.appscale[table_name]

    for ii in range(0, len(columns)):
      found = 0
      for pp in range (0,len(column_names)):
        if (column_names[pp] == columns[ii]):
          # update column
          collection.update({"column":column_names[pp],"row":row_key},{"row":row_key, "column":column_names[pp],"data":base64.b64encode(cell_values[pp]),"__schema_info__":"0"},True,True)
          found = 1
          break
      if found == 0:
        # if just updating a few columns, this gets called over and 
        # over again, but in appscale this is uncommon if done through
        # an application server
        old_data = self.get_entity(table_name, row_key, columns)
        old_data = old_data[1:]
        if not old_data: value = ""
        else: value = old_data[ii]
        collection.update({"column":columns[ii],"row":row_key},{"row":row_key, "column":columns[ii],"data":base64.b64encode(value),"__schema_info__":"0"},True,True)

    elist.append("0")
    self.__close_connection(db)
    if len(elist) == 1:
      elist[0] += "Not found"
    return elist

  def create_table(self, table_name, columns):
      elist = [ERROR_MONGO]
      if (not table_name) or (not columns):
          elist[0] += "Null columns or table_name"
          return 0

      db = self.__init_connection()
      if not db:
        elist[0] += "Unable to create table"
        return 0

      collection = db.appscale[table_name]
      collection.remove({})

      myObject = {"schema":columns, "__schema_info__":"1"}
      collection.insert(myObject)

      self.__close_connection(db)
      self.table_cache.append(table_name)
      return 1

  def delete_table(self, table_name):
      elist = [ERROR_MONGO]

      if not table_name:
          elist[0] += "Null table_name"
          return elist

      if not self.__table_exists(table_name):
        elist[0] += "Table %s does not exist." % table_name
        return elist

      db = self.__init_connection()
      #assuming we can just delete all the data in the table without
      #deleting the table itself
      collection = db.appscale[table_name]
      collection.remove({})
      db.appscale.drop_collection(table_name)
      self.table_cache.delete(table_name)
      elist.append("0")
      self.__close_connection(db)
      return elist

  def delete_row(self, table_name, row_key):
      elist = [ERROR_MONGO]

      if (not row_key) or (not table_name):
          elist[0] += "Null row_key or table_name"
          return elist

      if not self.__table_exists(table_name):
        elist[0] += "Table %s does not exist." % table_name
        return elist

      db = self.__init_connection()
      collection = db.appscale[table_name]
      if not collection.remove({"row":row_key}, True):
        elist[0] += "key %s does not exist." % row_key
      else:
        elist.append("0")
      self.__close_connection(db)
      return elist

  def get_entity(self, table_name, row_key, column_names):
      elist = [ERROR_MONGO]

      if (not row_key) or (not table_name):
        elist[0] += "Null row_key or table_name"
        return elist

      schema = self.get_schema(table_name)
      schema = schema[1:]

      db = self.__init_connection()
      collection = db.appscale[table_name]
      data = []
      for ii in range(0, len(schema)):
        cursor = collection.find({"row":row_key, "column":schema[ii]},
                                   ["data"])
        if(cursor.count()==0):
          elist[0] += "data not found for particular row and column for table name: %s on row key: %s, with columns: %s and  elist: %s"%(table_name, row_key, str(column_names), str(elist))
          return elist
        newent = ""
        for d in cursor:
          newent += str(base64.b64decode(d["data"]))
        data.append(newent)
      # retrieve only the columns requested from entire schema range 
      for column in column_names:
        for ii in range(0,len(schema)):
          if column == schema[ii]:
            elist.append(data[ii])
      self.__close_connection(db)
      if len(elist) == 1:
        elist[0] += "Not found"
      return elist

  def get_schema(self, table_name):
      elist = [ERROR_MONGO]
      #mytemp = [ERROR_MONGO]
      if (not table_name):
          elist[0] += "Null table_name"
          return elist
      if table_name in self.schema_cache:
        return self.schema_cache[table_name]

      db = self.__init_connection()
      duplicate = 0
      collection = db.appscale[table_name]
      cursor = collection.find({"__schema_info__":"1"})

      #variable duplicate makes sure no duplicate columns are returned
      mytemp = []
      for d in cursor:
          mytemp = d["schema"]
      for ii in mytemp:
          elist.append(str(ii))

      if(len(elist) == 1):
        elist[0] += "table not found"
      else:
        self.schema_cache[table_name] = elist

      self.__close_connection(db)
      return elist

  def get_table(self, table_name, column_names = []):
      elist = [ERROR_MONGO]
      used = 0
      usedRows = [ERROR_MONGO]
      columnList = self.get_schema(table_name)

      if (not table_name):
          elist[0] += "Null table_name"
          return elist

      db = self.__init_connection()
      collection = db.appscale[table_name]

      cursor = collection.find(None,None,1)
      for d in cursor:
          if(str(d["__schema_info__"])=="0"):
              myRow = str(d["row"])
              for pp in range(1,len(usedRows)):
                  if(myRow == usedRows[pp]):
                      used = 1
              if(used == 0):
                  for ii in range(1,len(columnList)):
                      aa = collection.find({"row":myRow,"column":columnList[ii]})
                      for dd in aa:
                          elist.append(str(base64.b64decode(dd["data"])))
              used = 0
              usedRows.append(myRow)


      #if len(elist) == 1:
      #  elist[0] += "table not found"

      self.__close_connection(db)
      return elist

  def __table_exists(self, table):
    if table in self.table_cache:
      return True
    db = self.__init_connection()
    if table in db.appscale.collection_names():
      ret = True
    else:
      ret = False
    self.__close_connection(db)
    return ret
