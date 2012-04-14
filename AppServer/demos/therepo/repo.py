#!/usr/bin/env python
#
# Programmer: Chris Bunch
# Provides a HTTP API to the underlying database for Neptune jobs
# See http://appscale.cs.ucsb.edu for more info

from __future__ import with_statement

import os
import re
import urllib
import wsgiref.handlers

from django.utils import simplejson as json

from google.appengine.ext import db
from google.appengine.ext import webapp

from google.appengine.api import files
from google.appengine.ext import blobstore
from google.appengine.api import images
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.api import urlfetch
from google.appengine.api import users
from google.appengine.api import xmpp

from google.appengine.api.appscale.ec2 import ec2
from google.appengine.api.appscale.mapreduce import mapreduce
from google.appengine.api.appscale.neptune import neptune

import logging

SECRET = "PLACE SECRET HERE"

NO_SECRET = "you failed to provide a secret"
BAD_SECRET = "you provided a bad secret"
NO_KEY = "you failed to provide a key"
NO_VALUE = "you failed to provide a value"
NO_TYPE = "you failed to provide a type"
BAD_TYPE = "you provided a bad type2"

NOT_FOUND = "not found"
SUCCESS = "success"
FAILURE = "failure"
PRIVATE_DATA = "data is private"

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

class GetInterface(webapp.RequestHandler):
  def post(self):
    secret = self.request.get('SECRET')
    if secret is None or secret == "":
      self.response.out.write(NO_SECRET)
      return

    if secret != SECRET:
      self.response.out.write(BAD_SECRET)
      return

    key = self.request.get('KEY')
    if key is None or key == "":
      self.response.out.write(NO_KEY)
      return

    type = self.request.get('TYPE')
    if type is None or type == "":
       self.response.out.write(NO_TYPE)
       return
   
    if type != "output" and type != "acl":
      self.response.out.write(BAD_TYPE)
      return

    entry = Entry.get_by_key_name(key)

    if entry is None:
      self.response.out.write(NOT_FOUND)
      return

    if type == "output":
      self.response.out.write(entry.content)
    else: # type is acl
      self.response.out.write(entry.acl)

    return

class SetInterface(webapp.RequestHandler):
  def post(self):
    secret = self.request.get('SECRET')
    if secret is None or secret == "":
      self.response.out.write(NO_SECRET)
      return

    if secret != SECRET:
      self.response.out.write(BAD_SECRET)
      return

    key = self.request.get('KEY')
    if key is None or key == "":
      self.response.out.write(NO_KEY)
      return

    # TODO - should we be allowed to write zero-length files?
    # right now we do - uncomment below line to disable it
    value = self.request.get('VALUE')
    if value is None or value == "":
      self.response.out.write(SUCCESS)
      #self.response.out.write(NO_VALUE)
      return

    type = self.request.get('TYPE')
    if type is None or type == "":
       self.response.out.write(NO_TYPE)
       return
   
    if (type != "output") and (type != "acl"):
      self.response.out.write(BAD_TYPE)
      return

    entry = None

    if type == "output":
      entry = Entry(key_name = key)
      entry.content = db.Blob(str(value))
      entry.acl = "private"
    else: # type is acl
      entry = Entry.get_by_key_name(key)

      if entry is None:
        self.response.out.write(NOT_FOUND)
        return

      entry.acl = value

    if entry.put():
      self.response.out.write(SUCCESS)
    else:
      self.response.out.write(FAILURE)

class DoesExistInterface(webapp.RequestHandler):
  def post(self):
    secret = self.request.get('SECRET')
    if secret is None or secret == "":
      self.response.out.write(NO_SECRET)
      return

    if secret != SECRET:
      self.response.out.write(BAD_SECRET)
      return

    key = self.request.get('KEY')
    if key is None or key == "":
      self.response.out.write(NO_KEY)
      return

    entry = Entry.get_by_key_name(key)

    if entry is None:
      self.response.out.write("false")
    else:
      self.response.out.write("true")

    return

class ViewInterface(webapp.RequestHandler):
  def get(self, key):
    entry = Entry.get_by_key_name(key)

    if entry is None:
      self.response.out.write(NOT_FOUND)
      return

    if entry.acl == "private":
      self.response.out.write(PRIVATE_DATA)
      return

    # else it must be public
    # later we can change this to restrict
    # on a user-level basis
    self.response.out.write(entry.content)
    return

class HealthChecker(webapp.RequestHandler):
  def get(self, capability):
    health = {}

    if capability == "all" or capability == "blobstore":
      try:
        file_name = files.blobstore.create(mime_type='application/octet-stream')
        with files.open(file_name, 'a') as f:
          f.write('data')

        files.finalize(file_name)
        # The following is not done because it requires a query and will slow down the 
        # system over time it not cleaned up correctly
        #blob_key = files.blobstore.get_blob_key(file_name)
        #blobstore.delete(blob_key) 
        health['blobstore'] = RUNNING
      except Exception, e:
        health['blobstore'] = FAILED
        logging.error("Blobstore FAILED %s"%(str(e)))
    if capability == "all" or capability == "datastore":
      try:
        entry = Entry.get_by_key_name("bazbookey")
        health['datastore'] = RUNNING
      except Exception, e:
        health['datastore'] = FAILED
        logging.error("Datastore FAILED %s"%(str(e)))
    if capability == "all" or capability == "datastore_write":
      try:
        entry = StatusText(key_name = "bazbookey")
        entry.content = "bazbooval"
        if entry.put():
          health['datastore_write'] = RUNNING
        else:
          health['datastore_write'] = FAILED
          logging.error("Datastore write FAILED no exception given")
      except Exception, e:
        health['datastore_write'] = FAILED
        logging.error("Datastore write FAILED %s"%(str(e)))

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

    if capability == "all" or capability == "mapreduce":
      try:
        if mapreduce.can_run_jobs():
          health['mapreduce'] = RUNNING
        else:
          health['mapreduce'] = FAILED
      except Exception, e:
        health['mapreduce'] = FAILED
        logging.error("mapreduce API FAILED %s"%(str(e)))

    if capability == "all" or capability == "ec2":
      try:
        if ec2.can_run_jobs():
          health['ec2'] = RUNNING
        else:
          health['ec2'] = FAILED
          logging.error("ec2 API FAILED no exception")
      except Exception, e:
        health['ec2'] = FAILED
        logging.error("ec2 API FAILED %s"%(str(e)))

    if capability == "all" or capability == "neptune":
      try:
        if neptune.can_run_jobs():
          health['neptune'] = RUNNING
        else:
          health['neptune'] = FAILED
      except Exception, e:
        health['neptune'] = FAILED
        logging.error("neptune API FAILED %s"%(str(e)))

    self.response.out.write(json.dumps(health))

class PermsChecker(webapp.RequestHandler):
  def get(self, user, perm):
    user = urllib.unquote(user)
    result = users.is_user_capable(user, perm)
    self.response.out.write(json.dumps(result))

application = webapp.WSGIApplication([
  ('/', Home),
  ('/get', GetInterface),
  ('/set', SetInterface),
  ('/doesexist', DoesExistInterface),
  (r'/view/(.*)', ViewInterface),
  (r'/health/(.*)', HealthChecker),
  (r'/perms/(.*)/(.*)', PermsChecker)
], debug=True)

def main():
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
