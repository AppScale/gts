#!/usr/bin/python
# Blobstore server for uploading blobs
# Author: 
# Navraj Chohan (nchohan@cs.ucsb.edu)
# See LICENSE file
import sys
import os 
import getopt
import datetime
import time
import cgi
import cStringIO
import mimetools
import itertools
import mimetypes
from cStringIO import StringIO
import urllib2
import logging 
from email.mime import base
from email.mime import multipart
from email import generator

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
from google.appengine.api.blobstore import blobstore
from google.appengine.api.blobstore import blobstore_service_pb
from google.appengine.api.blobstore import blobstore_stub
from google.appengine.api.blobstore import datastore_blob_storage
from SocketServer import BaseServer
import tornado.httpserver, tornado.ioloop, tornado.options, tornado.web, os.path
from tornado.options import define, options

UPLOAD_URL_PATH = '_ah/upload/'

UPLOAD_URL_PATTERN = '/%s(.*)' % UPLOAD_URL_PATH

port = "6106"
datastore_path = "http://127.0.0.1:8888"
private = "127.0.0.1"
public = "127.0.0.1"
_BLOB_CHUNK_KIND_ = "__BlobChunk__"
STRIPPED_HEADERS = frozenset(('content-length',
                              'content-md5',
                              'content-type',
                             ))

UPLOAD_ERROR = """There was an error with your upload. Redirect path not found. The path given must be a redirect code in the 300's. Please contact the app owner if this persist."""

"""
Code from http://blog.doughellmann.com/2009/07/pymotw-urllib2-library-for-opening-urls.html
"""
class MultiPartForm(object):
   """Accumulate the data to be used when posting a form."""

   def __init__(self, boundary):
     self.form_fields = []
     self.files = []
     if not boundary:
       self.boundary = mimetools.choose_boundary()
     else:
       self.boundary = boundary
     return
   
   def get_content_type(self):
     return 'multipart/form-data; boundary=%s' % self.boundary

   def add_field(self, name, value):
     """Add a simple field to the form data."""
     self.form_fields.append((name, value))
     return

   def add_file(self, fieldname, filename, fileHandle, blob_key, access_type,
                size,
                creation):
     """Add a file to be uploaded."""
     body = fileHandle.read()
     mimetype = 'message/external-body; blob-key="%s"; access-type="%s"'%(blob_key, access_type)
     #mimetype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
     self.files.append((fieldname, filename, mimetype, body, size, creation))
     return
   
   def __str__(self):
     """Return a string representing the form data, including attached files."""
     # Build a list of lists, each containing "lines" of the
     # request.  Each part is separated by a boundary string.
     # Once the list is built, return a string where each
     # line is separated by '\r\n'.  
     parts = []
     part_boundary = '--' + self.boundary
      
     # Add the form fields
     parts.extend(
         [ part_boundary,
           'Content-Disposition: form-data; name="%s"' % name,
           '',
           value,
         ]
         for name, value in self.form_fields
         )
      
     # Add the files to upload
     parts.extend(
         [ part_boundary,
           'Content-Type: %s' % content_type,
           'MIME-Version: 1.0',
           'Content-Disposition: form-data; name="%s"; filename="%s"' % \
              (field_name, filename),
           '',
           'Content-Type: application/octet-stream',
           'MIME-Version: 1.0',
           'Content-Length: %d'%size,
           'content-type: application/octet-stream',
           'content-disposition: form-data; name="%s"; filename="%s"' % \
              (field_name, filename),
           blobstore.UPLOAD_INFO_CREATION_HEADER + ": %s" % creation,
           '',
           ''
         ]
         for field_name, filename, content_type, body, size, creation in self.files
         )
      
     # Flatten the list and add closing boundary marker,
     # then return CR+LF separated data
     flattened = list(itertools.chain(*parts))
     flattened.append('--' + self.boundary + '--')
     flattened.append('')
     return '\r\n'.join(flattened)
 
def get_blobinfo(blob_key):
  datastore_key = datastore.Key.from_path(blobstore.BLOB_INFO_KIND,
                                          blob_key,
                                          namespace='')
  try:
    return datastore.Get(datastore_key)
  except datastore_errors.EntityNotFoundError:
    return None

def get_session(session_id):
  try:
    return datastore.Get(session_id)
  except datastore_errors.EntityNotFoundError:
    return None

def setup_env():
  os.environ['AUTH_DOMAIN'] = "appscale.cs.ucsb.edu"
  os.environ['USER_EMAIL'] = ""
  os.environ['USER_NICKNAME'] = ""
  os.environ['APPLICATION_ID'] = ""
  # This should be customized for the version of the app
  # Blob store will break if this does not change when a new version
  # of an app is uploaded
  os.environ['APPSCALE_VERSION'] = "1"

class Application(tornado.web.Application):
  def __init__(self):
    handlers = [
      (r"/_ah/upload/(.*)/(.*)", UploadHandler),
      (r"/", HealthCheck)
    ]   
    tornado.web.Application.__init__(self, handlers)

def split_content_type(c_type):
   delim = ';'
   ps = c_type.split(delim)
   tup = dict([(k.lower().strip(), v) for k, v in [p.split('=', 1) for p in ps[1:]]])
   return ps[0].strip(), tup

class SmartRedirectHandler(urllib2.HTTPRedirectHandler):     
  def http_error_301(self, req, fp, code, msg, headers):  
    # Dont follow redirects
    #result = urllib2.HTTPRedirectHandler.http_error_301( 
    #    self, req, fp, code, msg, headers)              
    #result.status = code                                 
    return None

  def http_error_302(self, req, fp, code, msg, headers):   
    # Dont follow redirects
    #result = urllib2.HTTPRedirectHandler.http_error_301( 
    #    self, req, fp, code, msg, headers)              
    #result.status = code                                
    return None

class HealthCheck(tornado.web.RequestHandler):
  def get(self):
    self.finish("Hello") 
 
class UploadHandler(tornado.web.RequestHandler):
  #@tornado.web.asynchronous
  def post(self, app_id="blob", session_id = "session"):
    global datastore_path
    #file = self.request.files['file'][0]
    db = datastore_distributed.DatastoreDistributed(
      app_id, datastore_path, False, False)
    apiproxy_stub_map.apiproxy.RegisterStub('datastore_v3', db)
    os.environ['APPLICATION_ID'] = app_id

    # setup the app id in the datastore
    # Get session info and upload success path
    blob_session = get_session(session_id)
    if not blob_session:
      self.finish('Session has expired. Contact the owner of the app for support.\n\n')
      return
    success_path = blob_session["success_path"]

    server_host = success_path[:success_path.rfind("/",3)]
    if server_host.startswith("http://"):
      # strip off the beginging
      server_host = server_host[len("http://"):]
    server_host = server_host.split('/')[0]

    blob_storage = datastore_blob_storage.DatastoreBlobStorage("", app_id)
    uploadhandler = dev_appserver_upload.UploadCGIHandler(blob_storage)

    datastore.Delete(blob_session)
    # This request is sent to the upload handler of the app
    # in the hope it returns a redirect to be forwarded to the user
    urlrequest = urllib2.Request(success_path)

    # Forward all relevant headers
    # Create data for request

    reqbody = self.request.body
    content_type = self.request.headers["Content-Type"]
    main, kv = split_content_type(content_type)
    boundary = None
    if "boundary" in kv:
      boundary = kv["boundary"]

    urlrequest.add_header("Content-Type",'multipart/form-data; boundary="%s"'%boundary)

    for name, value in self.request.headers.items():
      if name.lower() not in STRIPPED_HEADERS:
        urlrequest.add_header(name, value)
  
    # Get correct redirect addresses, otherwise it will redirect back
    # to this port
    urlrequest.add_header("Host",server_host)

    form = MultiPartForm(boundary)
    creation = datetime.datetime.now()
    # Loop on all files in the form
    for filekey in self.request.files.keys():
      file = self.request.files[filekey][0] 
      body = file["body"]
      size = len(body)
      filetype = file["content_type"]
      filename = file["filename"]
     
      blob_entity = uploadhandler.StoreBlob(file, creation)

      blob_key = str(blob_entity.key().name())

      if not blob_key: 
        self.finish('Status: 500\n\n')
        return 
      creation_formatted = blobstore._format_creation(creation)
      form.add_file(filekey, filename, cStringIO.StringIO(blob_key), blob_key,
                    blobstore.BLOB_KEY_HEADER, size, creation_formatted) 
    # Loop through form fields
    for fieldkey in self.request.arguments.keys():
      form.add_field(fieldkey, self.request.arguments[fieldkey][0])
    request_body = str(form)
    urlrequest.add_header("Content-Length",str(len(request_body)))
    urlrequest.add_data(request_body)

    opener = urllib2.build_opener(SmartRedirectHandler())
    f = None
    redirect_path = None
    # We are catching the redirect error here
    # and extracting the Location to post the redirect
    try:
      f = opener.open(urlrequest)
      output = f.read()
      self.finish(output)
    except urllib2.HTTPError, e: 
      if "Location" in e.hdrs:  
        redirect_path = e.hdrs["Location"] 
        toks = redirect_path.split(':')
        # The java app server redirects to the private IP if the POST to 
        # the successful path was from the private IP
        if toks[1] == "//"+private:
          redirect_path = toks[0] + "://" + public + ":" + ':'.join(toks[2:])
        self.redirect(redirect_path)
        return
      else:
        self.finish(UPLOAD_ERROR + "</br>" + str(e.hdrs) + "</br>" + str(e))
        return         
    self.finish("There was an error with your upload")

def usage():
  print "-p or --port for binding port"
  print "-d or --datastore_path for location of the pbserver"
  print "-u --public for public IP"
  print "-r --private for private IP"

def main():
  global port
  setup_env()

  http_server = tornado.httpserver.HTTPServer(Application())
  http_server.listen(int(port))
  tornado.ioloop.IOLoop.instance().start()
  
if __name__ == "__main__":
  try:
    opts, args = getopt.getopt(sys.argv[1:], "p:d:u:r:",
                               ["port", "database_path", "public", "private"] )
  except getopt.GetoptError:
    usage()
    sys.exit(1)
  for opt, arg in opts:
    if opt in ("-p", "--port"):
      port = arg
    elif opt  in ("-d", "--datastore_path"):
      datastore_path = arg
    elif opt  in ("-d", "--datastore_path"):
      datastore_path = arg
    elif opt  in ("-u", "--public"):
      public = arg
    elif opt  in ("-r", "--private"):
      private = arg
    
  main()

