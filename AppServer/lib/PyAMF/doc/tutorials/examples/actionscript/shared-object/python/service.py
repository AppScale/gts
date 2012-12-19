# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

import sys, os.path, operator
import logging

import pyamf
from pyamf import sol


def default_folder():
    """
    Return default platform specific Shared Objects folder.

    @rtype: str
    """
    if sys.platform.startswith('linux'):
        folder = "~/.macromedia/Flash_Player/#SharedObjects"
    elif sys.platform.startswith('win'):
        folder = '~\\AppData\\Roaming\Macromedia\\Flash Player\\#SharedObjects'
    elif sys.platform.startswith('darwin'):
        folder = "~/Library/Preferences/Macromedia/Flash Player/#SharedObjects"
    else:
        import warnings

        warnings.warn("Could not find a platform specific folder " \
            "function for '%s'" % sys.platform, RuntimeWarning)

    return os.path.expanduser(folder)
    
class SharedObjectService:
    """
    AMF service for Local Shared Object example.
    """
    
    def __init__(self, path, pattern):
        self.logger = logging
        self.path = path
        self.pattern = pattern
        
    def getApps(self):
        """
        Get list of applications, containing one or more .sol files,
        sorted by domain.
        """
        extList = []
        apps = []
        
        # convert pattern string to file extensions
        for ext in self.pattern.split(';'):
            extList.append(ext.lstrip('*'))

        self.logger.debug('Path: %s' % self.path)
        self.logger.debug('File extension(s): %s' % extList)
        
        # walk the tree to get apps
        for directory in os.walk(self.path):
            files = self._soDirectory(directory, extList)
            
            if len(files) > 0:
                dup = False
                for app in apps:
                    if files[0].domain == app.domain:
                        dup = True
                        break
                    
                if dup == False:
                    newapp = App()
                    newapp.path = directory[0]
                    newapp.name = os.path.basename(newapp.path)
                    newapp.files = files
                    newapp.domain = files[0].domain
                    apps.append(newapp)               
                else:
                    app.files.extend(files)
                    
        # sort apps by domain
        apps.sort(key=operator.attrgetter('domain'))

        self.logger.debug('Total apps: %d' % len(apps))
        
        return (self.path, apps)

    def getDetails(self, path):
        """
        Read and return Shared Object.
        """
        lso = sol.load(path)
        
        return lso
    
    def _soFiles(self, dirList, typeList):
        """
        Return files that match to file extension(s).
        """
        files = []
        
        for lso in dirList[2]:
            file_info = os.path.splitext(lso)
            
            for ext in typeList:
                if file_info[1] == ext:
                    so = SharedObject()
                    so.name = file_info[0]
                    so.filename = lso
                    so.path = os.path.abspath(os.path.join(dirList[0], lso))
                    so.app = os.path.basename(dirList[0])
                    so.size = os.path.getsize(so.path)
                    so.domain = so.path[len(self.path)+1:].rsplit(os.sep)[1]
                    files.append(so)
                    
                    self.logger.debug(' -- '.rjust(5) + repr(so))
                    break
                
        return files
    
    def _soDirectory(self, dirEntry, typeList):
        """
        Return each sub-directory.
        """        
        return self._soFiles(dirEntry, typeList)

class App(object):
    def __init__(self):
        self.name = ''
        self.path = ''
        self.domain = ''
        self.files = []
        
    def __repr__(self):
        return '<%s name=%s files=%s path=%s>' % (App.__name__, self.name, len(self.files), self.path)

pyamf.register_class(App, 'org.pyamf.examples.sharedobject.vo.App')

class SharedObject(object):
    def __init__(self):
        self.name = ''
        self.app = ''
        self.path = ''
        self.domain = ''
        self.size = 0
        
    def __repr__(self):
        return '<%s app=%s size=%s filename=%s>' % (SharedObject.__name__, self.app, self.size, self.filename)

pyamf.register_class(SharedObject, 'org.pyamf.examples.sharedobject.vo.SharedObject')
