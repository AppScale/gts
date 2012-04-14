#base class to be used by all the dbmigration classes
import logging,os,ConfigParser

class migratedb:    
    configfilepath = "config.cfg"  #path to config file    
    def __init__(self):
        # initialize logger
        # the logging might go off when used multithreading with this model. In that case separate logs should be used for each log
        logging.basicConfig(filename='python.log',level=logging.DEBUG,format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        #initialize properties file
        self.config = ConfigParser.RawConfigParser( )
        if os.path.exists(self.configfilepath):
            self.config.read(self.configfilepath)
        else:
            logging.error("Config file doesn't exists")
            os.sys.exit(1)     
       
    def exportdata(self):
        #this method has to be implemented
        raise NotImplementedError("The export data class has not been implemented")        
    
    def importdata(self, filepath):
        #this method has to be implemented
        raise NotImplementedError("The import data class has not been implemented")        
            
    
    def iskeypresent(self):
        pass
    
    
    def readconfig(self,section,parameter):
        try:
            val = self.config.get(section, parameter)
            return val.strip()  
        except Exception,e:
            raise e

    def fakepopulate(self, number):
        pass

if __name__ == "__main__":
    mdb = migratedb()
    
    
    
    
    
