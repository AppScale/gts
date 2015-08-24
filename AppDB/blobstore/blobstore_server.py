#!/usr/bin/python
"""
Blobstore server for uploading blobs.
See LICENSE file.

Some code was taken from 
http://blog.doughellmann.com/2009/07/pymotw-urllib2-library-for-opening-urls.html

"""
import cStringIO
import datetime
import getopt
import hashlib
import itertools
import logging
import mimetools
import os 
import os.path
import sys
import urllib
import urllib2

import tornado.httpserver
import tornado.ioloop
import tornado.web

from google.appengine.api import apiproxy_stub_map
from google.appengine.api import datastore_errors
from google.appengine.api import datastore_distributed
from google.appengine.api import datastore

from google.appengine.api.blobstore import blobstore
from google.appengine.api.blobstore import datastore_blob_storage

from google.appengine.tools import dev_appserver_upload

# The URL path used for uploading blobs
UPLOAD_URL_PATH = '_ah/upload/'

# The port this service binds to
DEFAULT_PORT = "6106"

# Connects to localhost to get access to the datastore
DEFAULT_DATASTORE_PATH = "http://127.0.0.1:8888"

# The datastore kind used for storing chunks of a blob
_BLOB_CHUNK_KIND_ = "__BlobChunk__"

# Headers we ignore
STRIPPED_HEADERS = frozenset(('content-length',
                              'content-md5',
                              'content-type',
                             ))

UPLOAD_ERROR = """There was an error with your upload. Redirect path not found. The path given must be a redirect code in the 300's. Please contact the app owner if this persist."""

# Global used for setting the datastore path when registering the DB
datastore_path = ""

class MultiPartForm(object):
  """Accumulate the data to be used when posting a form."""

  def __init__(self, boundary):
    """ Constructor. """
    self.form_fields = []
    self.files = []
    if not boundary:
      self.boundary = mimetools.choose_boundary()
    else:
      self.boundary = boundary
    return
  
  def get_content_type(self):
    """ Get the content type to use. """
    return 'multipart/form-data; boundary=%s' % self.boundary

  def add_field(self, name, value):
    """Add a simple field to the form data."""
    self.form_fields.append((name, value))
    return

  def add_file(self, 
               fieldname, 
               filename,  
               fileHandle, 
               blob_key, 
               access_type,
               size,
               creation):
    """Add a file to be uploaded."""
    body = fileHandle.read()
    mimetype = 'message/external-body; blob-key="%s"; access-type="%s"' % \
       (blob_key, access_type)
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
        for field_name, filename, content_type, body, size, \
            creation in self.files
        )
     
    # Flatten the list and add closing boundary marker,
    # then return CR+LF separated data
    flattened = list(itertools.chain(*parts))
    flattened.append('--' + self.boundary + '--')
    flattened.append('')
    return '\r\n'.join(flattened)
 
def get_blobinfo(blob_key):
  """ Get BlobInfo from the datastore given its key. 
   
  Args:
    blob_key: A BlobInfo key
  Returns:
    The BlobInfo entity referenced by the blob_key.
  """
  datastore_key = datastore.Key.from_path(blobstore.BLOB_INFO_KIND,
                                          blob_key,
                                          namespace='')
  try:
    return datastore.Get(datastore_key)
  except datastore_errors.EntityNotFoundError:
    return None

def get_session(session_id):
  """ Get the session entity of the given session ID. 
    
  Args:
    session_id: The session ID we want the cooresponding session entity.
  Returns:
    The session entity
  """
  try:
    return datastore.Get(session_id)
  except datastore_errors.EntityNotFoundError:
    return None

def setup_env():
  """ Sets required environment variables for GAE datastore library """
  os.environ['AUTH_DOMAIN'] = "appscale.com"
  os.environ['USER_EMAIL'] = ""
  os.environ['USER_NICKNAME'] = ""
  os.environ['APPLICATION_ID'] = ""

class Application(tornado.web.Application):
  """ The tornado web application handling uploads and healthchecks. """
  def __init__(self):
    """ Constructor. """
    handlers = [
      (r"/_ah/upload/(.*)/(.*)", UploadHandler),
      (r"/", HealthCheck)
    ]   
    tornado.web.Application.__init__(self, handlers)

def split_content_type(c_type):
  """ Parses the content type. 
  
  Args: 
    c_type: the content type.
  Returns:
    A tuple the first portion of the content type and a key/value dictionary
    of the content-type.
  """
  delim = ';'
  ps = c_type.split(delim)
  tup = dict([(k.lower().strip(), v) for k, v in [p.split('=', 1) \
                                     for p in ps[1:]]])
  return tup

class SmartRedirectHandler(urllib2.HTTPRedirectHandler):     
  """ An overridden class for custom actions on redirects. """
  def http_error_301(self, req, fp, code, msg, headers):  
    """ Stubbed out to do nothing since we do not follow redirects. """
    return None

  def http_error_302(self, req, fp, code, msg, headers):   
    """ Stubbed out to do nothing since we do not follow redirects. """
    return None

class HealthCheck(tornado.web.RequestHandler):
  """ Tornado handler for health checks. """
  def get(self):
    """ This path is called to make sure the server is up and running. """
    self.finish("Hello") 
 
class UploadHandler(tornado.web.RequestHandler):
  """ Tornado handler for uploads. """
  def post(self, app_id="blob", session_id = "session"):
    """ Handler a post request from a user uploading a blob. 
    
    Args:
      app_id: The application triggering the upload.
      session_id: Authentication token to validate the upload.
    """
    global datastore_path
    db = datastore_distributed.DatastoreDistributed(
      app_id, datastore_path, require_indexes=False)
    apiproxy_stub_map.apiproxy.RegisterStub('datastore_v3', db)
    os.environ['APPLICATION_ID'] = app_id

    # Setup the app id in the datastore.
    # Get session info and upload success path.
    blob_session = get_session(session_id)
    if not blob_session:
      self.finish('Session has expired. Contact the owner of the ' + \
                  'app for support.\n\n')
      return

    success_path = blob_session["success_path"]

    server_host = success_path[:success_path.rfind("/", 3)]

    if server_host.startswith("http://"):
      # Strip off the beginging of the server host
      server_host = server_host[len("http://"):]
    server_host = server_host.split('/')[0]

    blob_storage = datastore_blob_storage.DatastoreBlobStorage(app_id)
    uploadhandler = dev_appserver_upload.UploadCGIHandler(blob_storage)

    datastore.Delete(blob_session)

    # This request is sent to the upload handler of the app
    # in the hope it returns a redirect to be forwarded to the user
    urlrequest = urllib2.Request(success_path)

    # Forward all relevant headers and create data for request
    content_type = self.request.headers["Content-Type"]
    kv = split_content_type(content_type)
    boundary = None
    if "boundary" in kv:
      boundary = kv["boundary"]

    urlrequest.add_header("Content-Type",
                          'application/x-www-form-urlencoded')

    for name, value in self.request.headers.items():
      if name.lower() not in STRIPPED_HEADERS:
        urlrequest.add_header(name, value)
  
    # Get correct redirect addresses, otherwise it will redirect back
    # to this port.
    urlrequest.add_header("Host", server_host)

    form = MultiPartForm(boundary)
    creation = datetime.datetime.now()

    # Loop on all files in the form.
    for filekey in self.request.files.keys():
      data = {"metadata": {filekey: []}}
      file = self.request.files[filekey][0] 
      body = file["body"]
      size = len(body)
      filename = file["filename"]
      file_content_type = file["content_type"]
     
      blob_entity = uploadhandler.StoreBlob(file, creation)

      blob_key = str(blob_entity.key().name())

      if not blob_key: 
        self.finish('Status: 500\n\n')
        return 
      creation_formatted = blobstore._format_creation(creation)
      form.add_file(filekey, filename, cStringIO.StringIO(blob_key), blob_key,
                    blobstore.BLOB_KEY_HEADER, size, creation_formatted)

      md5_handler = hashlib.md5(str(body))
      data["metadata"][filekey].append( 
        {"filename": filename, "creation-date": creation_formatted, "key": blob_key, "size": str(size),
         "content-type": file_content_type, "md5-hash": md5_handler.hexdigest()})

    # Loop through form fields
    for fieldkey in self.request.arguments.keys():
      form.add_field(fieldkey, self.request.arguments[fieldkey][0])
      data[fieldkey] = self.request.arguments[fieldkey][0]

    logging.debug("Callback data: \n{}".format(data))
    data = urllib.urlencode(data)
    urlrequest.add_header("Content-Length", str(len(data)))
    urlrequest.add_data(data)

    opener = urllib2.build_opener(SmartRedirectHandler())
    f = None
    redirect_path = None

    # We are catching the redirect error here
    # and extracting the Location to post the redirect.
    try:
      f = opener.open(urlrequest)
      output = f.read()
      self.finish(output)
    except urllib2.HTTPError, e: 
      if "Location" in e.hdrs:
        # Catch any errors, use the success path to 
        # get the ip and port, use the redirect path
        # for the path. We split redirect_path just in case
        # its a full path.
        redirect_path = e.hdrs["Location"]
        self.redirect(redirect_path)
        return
      else:
        self.finish(UPLOAD_ERROR + "</br>" + str(e.hdrs) + "</br>" + str(e))
        return         
    self.finish("There was an error with your upload")

def usage():
  """ The usage printed to the screen. """
  print "-p or --port for binding port"
  print "-d or --datastore_path for location of the pbserver"

def main(port):
  """ Initialization code of the blobstore server. 
  
   Args:
     port: The port to bind to for this service.
  """
  setup_env()

  http_server = tornado.httpserver.HTTPServer(Application())
  http_server.listen(int(port))
  tornado.ioloop.IOLoop.instance().start()
  
if __name__ == "__main__":
  global datastore_path
  try:
    opts, args = getopt.getopt(sys.argv[1:], "p:d:",
                               ["port", "database_path"])
  except getopt.GetoptError:
    usage()
    sys.exit(1)

  port = DEFAULT_PORT
  for opt, arg in opts:
    if opt in ("-p", "--port"):
      port = arg
    elif opt  in ("-d", "--datastore_path"):
      datastore_path = arg
    
  main(port)

