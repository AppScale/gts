# Pycassa library is used to communicate with cassandra. It can be installed as :
# sudo apt-get install python-pip
# sudo pip install pycassa 
# For more inforamtion visit
# http://pycassa.github.com/pycassa/installation.html
# Author: Anand Gupta
import cPickle as pickle 
import sys
import tarfile
from migrateDB import *
from pycassa.pool import ConnectionPool
from uuid import uuid1
from pycassa import ColumnFamily
from pycassa.system_manager import *
from datetime import datetime

class cassandradb(migratedb):    
  logsection = "cassandra"    
  
  def __init__(self):
    migratedb.__init__(self)
    logging.info("inside init method")
    # connect to cassandra
    try:
      self.keyspace = self.readconfig(self.logsection, "keyspace")
      host= self.readconfig(self.logsection, "host")
      port = self.readconfig(self.logsection, "port")
      self.address = "%s:%s" % (host,port)
      logging.debug("init: keyspace, host, port read is : %s %s %s", self.keyspace, host, port)
      logging.debug("connecting to cassandra")            
      
      self.sysmanager = SystemManager(self.address)  #http://pycassa.github.com/pycassa/api/pycassa/system_manager.html
      logging.debug("connection to cassandra successful")          
      
    except Exception,e:
      logging.error("Error in init method : Details - %s", e)
      logging.info("Exiting init method")
        
  def importdata(self, filepath):
    ''' method to import data from files and upload it on the database '''
    logging.info("Inside import data method")
    
    #open each file
        #populate the dict
            #check if keyspace exists
                 #create if not
                 #check if colfam exsist
                    #create if not
                        #create entries
        
  def fakepopulate(self, numkeyspace, numcolfam, numentries):
    ''' this method populates fake data in casandra'''
    countkeys = numkeyspace        
    logging.info("Inside fake populate method")        
    logging.debug("Method started at : %s", str(datetime.now()))
    #create random keyspace
    while(countkeys):            
      name = str(uuid1()).replace("-","")
      if name not in self.sysmanager.list_keyspaces():
        countkeys = countkeys - 1
        self.sysmanager.create_keyspace(name,strategy_options={"replication_factor": "1"})        
    
    #create random key families in each key space        
    for keyspace in self.sysmanager.list_keyspaces():            
      if (keyspace != 'system'):  #check to skip the system database  
        countcolfam = numcolfam
        while(countcolfam):
          name = str(uuid1()).replace("-","")
          if name not in self.sysmanager.get_keyspace_column_families(keyspace).keys(): 
            countcolfam = countcolfam - 1                    
            self.sysmanager.create_column_family(keyspace, name)
        
    #create random keys in each key column family of each keyspace
    totalcount=0
    for keyspace in self.sysmanager.list_keyspaces():            
      if (keyspace != 'system'):  #check to skip the system database
        pool = ConnectionPool(keyspace,[self.address])
        columnfamilies = self.sysmanager.get_keyspace_column_families(keyspace)
        for columnfamilyname in columnfamilies.keys():                    
          colfamily = ColumnFamily(pool,columnfamilyname)
          countnumetries = numentries
          while(countnumetries):
            rowkeyname = str(uuid1()).replace("-","")
            colname = str(uuid1()).replace("-","")
            colval = str(uuid1()).replace("-","")
            #col_fam.insert('row_key', {'col_name': 'col_val'})
            colfamily.insert(rowkeyname, {colname:colval})
            countnumetries = countnumetries - 1
            totalcount = totalcount + 1
        
    logging.debug("Method ended at : %s", str(datetime.now()))
    logging.debug("Total Entries added : %s", str(totalcount))
    logging.info("Exiting fakepopulate method")
    
  def exportdata(self,destination=None):
    ''' Method to export data to files '''            
    
    logging.info("inside export data method")
    count = 0
    try:
      os.mkdir('output')
    except Exception, e:
      pass 
    for keyspace in self.sysmanager.list_keyspaces():            
      if (keyspace != 'system'):  #check to skip the system database
        pool = ConnectionPool(keyspace,[self.address])
        columnfamilies = self.sysmanager.get_keyspace_column_families(keyspace)
        result = {}
      relt['cols']=[]
        # iterate through all the column family
        for columnfamilyname in columnfamilies.keys():
          #result[keyspace][columnfamilyname]=[]
          colfamily = ColumnFamily(pool,columnfamilyname)
          cols = colfamily.get_range(column_reversed=True)
          result['keyspace']=keyspace
          result['columnfamily']= columnfamilyname
          for col in cols:                        
            result['cols'].append(col)
            count = count + 1
            # check count if it 10000 then reset it flush result
            if (count == 100000):
              filename ="%s.out" % str(uuid1()).replace("-","")
              filepath = "output/%s" % filename
              file = open(filepath,"w")                            
              pickle.dump(result, file, protocol=-1)
              file.close()                
              #reset cols
              print sys.getsizeof(result)#in mb     
              result['cols']=[]                               
              count = 0
          
    if  count > 0:
      filename ="%s.out" % str(uuid1()).replace("-","")
      filepath = "output/%s" % filename
      file = open(filepath,"w")                            
      pickle.dump(result, file, protocol=-1)
      file.close()                
      os.chdir('output')
      tf = tarfile.open('data.tar.gz', 'w:gz')
      tf.add(filename)
      tf.close() 
      os.remove(filename)
    # dump the dictionary in a file using cpickle       
  
  def _iskeypresent(self):
    pass
  
if __name__ == "__main__":
  cdb = cassandradb()
  #cdb.fakepopulate(0,0,1000)
  cdb.exportdata("destination.out")
