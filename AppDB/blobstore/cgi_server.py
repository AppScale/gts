#!/usr/bin/python

import cgi, os
import cgitb; cgitb.enable()

form = cgi.FieldStorage()

# Get filename here.
fileitem = form['filename']

# Test if the file was uploaded
if fileitem.filename:
   # strip leading path from file name to avoid 
   # directory traversal attacks
   fn = os.path.basename(fileitem.filename)
   open('/tmp/' + fn, 'wb').write(fileitem.file.read())

   message = 'The file "' + fn + '" was uploaded successfully'
   
else:
   message = 'No file was uploaded'
   
#
# Author: 
# Navraj Chohan (nchohan@cs.ucsb.edu)
# See LICENSE file
import sys
import socket
import os 
import types
import appscale_datastore
from dbconstants import *
import appscale_logger
import random
import getopt
import threading
import datetime
from google.appengine.api import api_base_pb
from google.appengine.api import datastore_distributed
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import datastore_errors
from google.appengine.api import datastore_types
from google.appengine.api import datastore
from google.appengine.api import datastore
from google.appengine.api import users
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import datastore_index
from google.appengine.runtime import apiproxy_errors
from google.net.proto import ProtocolBuffer
from google.appengine.datastore import entity_pb
from google.appengine.ext.remote_api import remote_api_pb
from google.appengine.tools import dev_appserver_upload
"""
from google.appengine.tools import dev_appserver_blobstore
"""
from google.appengine.api.blobstore import blobstore
from google.appengine.api.blobstore import blobstore_service_pb
from google.appengine.api.blobstore import blobstore_stub
from google.appengine.api.blobstore import datastore_blob_storage
from SocketServer import BaseServer
from M2Crypto import SSL
from drop_privileges import *
import time
import tornado.httpserver, tornado.ioloop, tornado.options, tornado.web, os.path
from tornado.options import define, options
import logging

import cgi
import cStringIO
import logging
import mimetools
from email.mime import base
from email.mime import multipart
from email import generator


UPLOAD_URL_PATH = '_ah/upload/'

UPLOAD_URL_PATTERN = '/%s(.*)' % UPLOAD_URL_PATH


port = "6106"
datastore_path = "http://127.0.0.1:8888"

_BLOB_CHUNK_KIND_ = "__BlobChunk__"
STRIPPED_HEADERS = frozenset(('content-length',
                              'content-md5',
                              'content-type',
                             ))


