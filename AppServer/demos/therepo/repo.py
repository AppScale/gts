#!/usr/bin/env python
#
# Programmer: Chris Bunch
# Provides a HTTP API to the underlying database for Neptune jobs
# See http://appscale.cs.ucsb.edu for more info

import os
import re
import wsgiref.handlers

from google.appengine.ext import db
from google.appengine.ext import webapp

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

class Entry(db.Model):
  content = db.TextProperty()
  acl = db.StringProperty(multiline=False)

class Home(webapp.RequestHandler):
  def get(self):
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

    value = self.request.get('VALUE')
    if value is None or value == "":
      self.response.out.write(NO_VALUE)
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
      entry.content = value
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

application = webapp.WSGIApplication([
  ('/', Home),
  ('/get', GetInterface),
  ('/set', SetInterface),
  ('/doesexist', DoesExistInterface),
  (r'/view/(.*)', ViewInterface)
], debug=True)

def main():
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
