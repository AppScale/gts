#!/usr/bin/env python
#
# Programmer: Chris Bunch, Navraj Chohan
# Checks different APIs
# See http://appscale.com for more info

from __future__ import with_statement

import os
import re
import urllib
import wsgiref.handlers

from django.utils import simplejson as json

from google.appengine.ext import db
from google.appengine.ext import webapp

from google.appengine.ext import blobstore
from google.appengine.api import files
from google.appengine.api import images
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.api import urlfetch
from google.appengine.api import users
from google.appengine.api import xmpp

import logging

SECRET = "PLACE SECRET HERE"

RUNNING = 'running'
FAILED = 'failed'

class Entry(db.Model):
  content = db.BlobProperty()
  acl = db.StringProperty(multiline=False)

class StatusText(db.Model):
  content = db.StringProperty(multiline=False)

class Home(webapp.RequestHandler):
  def get(self):
    self.response.out.write("baz")

  def post(self):
    self.response.out.write("baz")

class HealthChecker(webapp.RequestHandler):
  def get(self, capability):
    health = {}

    if capability == "all" or capability == "blobstore":
      try:
        file_name = files.blobstore.create(mime_type='application/octet-stream')
        with files.open(file_name, 'a') as f:
          f.write('data')

        files.finalize(file_name)
        blob_key = files.blobstore.get_blob_key(file_name)
        blobstore.delete(blob_key) 
        health['blobstore'] = RUNNING
      except Exception, e:
        health['blobstore'] = FAILED
        logging.error("Blobstore FAILED %s"%(str(e)))
    if capability == "all" or capability == "datastore":
      try:
        entry = Entry.get_by_key_name("bazbookey")
        health['datastore'] = RUNNING
        entry = StatusText(key_name = "bazbookey")
        entry.content = "bazbooval"
        if entry.put():
          health['datastore_write'] = RUNNING
        else:
          health['datastore_write'] = FAILED
          logging.error("Datastore write FAILED no exception given")
      except Exception, e:
        health['datastore'] = FAILED
        logging.error("Datastore FAILED %s"%(str(e)))

    if capability == "all" or capability == "images":
      try:
        image = urlfetch.fetch("http://localhost/images/status_running.gif").content
        images.horizontal_flip(image)
        images.vertical_flip(image)
        images.rotate(image, 90)
        images.rotate(image, 270)
        health['images'] = RUNNING
      except Exception, e:
        health['images'] = FAILED
        logging.error("images API FAILED %s"%(str(e)))

    if capability == "all" or capability == "memcache":
      try:
        if memcache.set("boo", "baz", 10):
          health['memcache'] = RUNNING
        else:
          health['memcache'] = FAILED
          logging.error("memcached API FAILED no exception")
      except Exception, e:
        health['memcache'] = FAILED
        logging.error("memcached API FAILED %s"%(str(e)))

    if capability == "all" or capability == "taskqueue":
      try:
        taskqueue.add(url='/')
        health['taskqueue'] = RUNNING
      except Exception, e:
        health['taskqueue'] = FAILED
        logging.error("taskqueue API FAILED %s"%(str(e)))

    if capability == "all" or capability == "urlfetch":
      try:
        result = urlfetch.fetch("http://localhost")
        health['urlfetch'] = RUNNING
      except Exception, e:
        health['urlfetch'] = FAILED
        logging.error("urlfetch API FAILED %s"%(str(e)))

    if capability == "all" or capability == "users":
      try:
        user = users.get_current_user()
        users.create_login_url("/")
        users.create_logout_url("/")
        health['users'] = RUNNING
      except Exception, e:
        health['users'] = FAILED
        logging.error("users API FAILED %s"%(str(e)))


    if capability == "all" or capability == "xmpp":
      try:
        xmpp.get_presence("a@a.a")
        health['xmpp'] = RUNNING
      except Exception, e:
        health['xmpp'] = FAILED
        logging.error("xmpp API FAILED %s"%(str(e)))

    self.response.out.write(json.dumps(health))

application = webapp.WSGIApplication([
  ('/', Home),
  (r'/health/(.*)', HealthChecker),
], debug=True)

def main():
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
