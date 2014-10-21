#!/usr/bin/env python
#
""" Checks different APIs. See http://appscale.com for more info.
"""
import logging
import webapp2
import uuid 

try:
  import json
except ImportError:
  import simplejson as json

from google.appengine.ext import db

from google.appengine.api import images
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.api import urlfetch
from google.appengine.api import users
from google.appengine.api import xmpp


SECRET = "PLACE SECRET HERE"

RUNNING = 'running'
FAILED = 'failed'

class StatusText(db.Model):
  """ This simple entity class is used for testing puts, gets, and 
  deletes for the database API.
  """
  content = db.StringProperty(multiline=False)

class Home(webapp2.RequestHandler):
  """ Paths for seeing if the API Checker app is up. """
  def get(self):
    """ GET request handler which returns text to notify caller it is up. """
    self.response.out.write("baz")

  def post(self):
    """ POST request handler which returns text to notify caller it is up. """
    self.response.out.write("baz")

class HealthChecker(webapp2.RequestHandler):
  def get(self, capability):
    health = {}

    if capability == "all" or capability == "blobstore":
      try:
        from google.appengine.ext import blobstore
        from google.appengine.api import files
        health['blobstore'] = RUNNING
      except Exception, e:
        health['blobstore'] = FAILED
        logging.error("Blobstore FAILED %s" % (str(e)))
    if capability == "all" or capability == "datastore":
      try:
        health['datastore'] = RUNNING
        key_name = str(uuid.uuid4())
        entry = StatusText(key_name=key_name)
        entry.content = key_name
        if not entry.put():
          logging.error("Datastore was not able to put key %s" % key_name)
          health['datastore'] = FAILED
        elif not StatusText.get_by_key_name(key_name):
          logging.error("Datastore was not able to get key %s" % key_name)
          health['datastore'] = FAILED
        elif entry.delete():
          logging.error("Datastore was not able to delete key %s" % key_name)
          health['datastore'] = FAILED
        else: 
          health['datastore'] = RUNNING
      except Exception, e:
        health['datastore'] = FAILED
        logging.error("Datastore FAILED %s" % (str(e)))

    if capability == "all" or capability == "images":
      try:
        image = urlfetch.fetch("http://localhost:8079/images/cloud.png").content
        images.horizontal_flip(image)
        images.vertical_flip(image)
        images.rotate(image, 90)
        images.rotate(image, 270)
        health['images'] = RUNNING
      except Exception, e:
        health['images'] = FAILED
        logging.error("images API FAILED %s" % (str(e)))

    if capability == "all" or capability == "memcache":
      try:
        key_name = str(uuid.uuid4())
        if memcache.set(key_name, key_name, 10):
          health['memcache'] = RUNNING
        else:
          health['memcache'] = FAILED
          logging.error("memcached API FAILED no exception")
      except Exception, e:
        health['memcache'] = FAILED
        logging.error("memcached API FAILED %s" % (str(e)))

    if capability == "all" or capability == "taskqueue":
      try:
        taskqueue.add(url='/')
        health['taskqueue'] = RUNNING
      except Exception, e:
        health['taskqueue'] = FAILED
        logging.error("taskqueue API FAILED %s" % (str(e)))

    if capability == "all" or capability == "urlfetch":
      try:
        urlfetch.fetch("http://localhost:1080")
        health['urlfetch'] = RUNNING
      except Exception, e:
        health['urlfetch'] = FAILED
        logging.error("urlfetch API FAILED %s" % (str(e)))

    if capability == "all" or capability == "users":
      try:
        users.get_current_user()
        users.create_login_url("/")
        users.create_logout_url("/")
        health['users'] = RUNNING
      except Exception, e:
        health['users'] = FAILED
        logging.error("users API FAILED %s" % (str(e)))


    if capability == "all" or capability == "xmpp":
      try:
        xmpp.get_presence("a@a.a")
        health['xmpp'] = RUNNING
      except Exception, e:
        health['xmpp'] = FAILED
        logging.error("xmpp API FAILED %s" % (str(e)))

    self.response.out.write(json.dumps(health))

app = webapp2.WSGIApplication([
  ('/', Home),
  (r'/health/(.*)', HealthChecker),
], debug=True)

