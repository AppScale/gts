##### BEGIN CICERO-BOILERPLATE CODE  #####
try:
  import simplejson as json
except ImportError:
  import json

import datetime
import logging
import os
import StringIO
import wsgiref.handlers

from google.appengine.api import taskqueue

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util


# For this app, we only interact with a single pull queue. Therefore, we
# save the name of the pull queue here and also use it as the key name for
# the counter that stores the current size of the pull queue (the number of
# items in the queue).
PULL_QUEUE_NAME = "neptune"


# Pull queue-specific parameters: the duration of leased tasks and the number
# of tasks to lease. For our purposes, we grab tasks and immediately delete them,
# so the lease time isn't too important, but our accessing program always wants
# tasks one at a time.
ONE_HOUR = 3600  # seconds
ONE_TASK = 1


# The definiton for our counter class, stored in the datastore. Normally a
# single counter is not advisable within Google App Engine, but under less
# than excessive workloads (as we expect here), it's unlikely to become a
# bottleneck.
class Counter(db.Model):
  count = db.IntegerProperty()


# This class provides RESTful access to a Google App Engine pull queue.
class TaskRoute(webapp.RequestHandler):
  # The GET route pops a task off the queue (whose payload is JSON),
  # returning null if the queue is empty.
  def get(self):
    q = taskqueue.Queue(PULL_QUEUE_NAME)
    tasks = q.lease_tasks(ONE_HOUR, ONE_TASK)
    result = 'null'  # the JSON-dumped version of None
    if len(tasks) == 1:
      task = tasks[0]
      result = task.payload
      q.delete_tasks(tasks)

      # decrement our count
      counter = Counter.get_by_key_name(PULL_QUEUE_NAME)
      try:
        counter.count -= 1
        counter.put()
      except AttributeError:  # the Counter doesn't exist
        pass

    # The task is already stringified JSON, so don't dump it
    # again - just pass it the way it is.
    self.response.out.write(result)


  # The PUT route pushes a JSON-dumped item onto the queue, for
  # later execution.
  def put(self):
    payload_str = self.request.get('payload')
    result = {}
    if payload_str == '':  # an empty payload isn't acceptable
      result['ok'] = False
    else:
      # put the item on the queue
      q = taskqueue.Queue(PULL_QUEUE_NAME)
      tasks = []
      tasks.append(taskqueue.Task(payload=payload_str, method='PULL'))
      q.add(tasks)

      # increment our count
      counter = Counter.get_by_key_name(PULL_QUEUE_NAME)
      try:
        counter.count += 1
      except AttributeError:  # the Counter doesn't exist
        counter = Counter(key_name = PULL_QUEUE_NAME)
        counter.count = 1
      counter.put()
      result['ok'] = True
    self.response.out.write(json.dumps(result))


# Returns the number of items in the pull queue by checking
# a Counter object with a predetermined keyname (the name of the pull queue).
class SizeRoute(webapp.RequestHandler):
  def get(self):
    counter = Counter.get_by_key_name(PULL_QUEUE_NAME)
    result = {}
    try:
      result['size'] = counter.count
    except AttributeError:  # if the Counter doesn't exist
      result['size'] = 0

    self.response.out.write(json.dumps(result))


# A route that external services can use to make sure this app supports the
# Pull Queue API. This route is really only necessary since we may not be
# sure that this app is uploaded to App Engine for a given appid, so this
# provides a way to uniquely identify a pull queue-ready app (namely, this one).
class SupportsPullQueue(webapp.RequestHandler):
  def get(self):
    self.response.out.write(json.dumps(True))


# Sets up a default route that will eventually be refactored to produce a
# generic blurb about Pull Queues and the REST API - and maybe even some
# AJAX stuff that lets users access it directly.
class IndexPage(webapp.RequestHandler):
  def get(self):
    # TODO(cgb): write something nicer about pull queues here!
    self.response.out.write("hello!")


# Sets up routes in the usual fashion and starts the app.
def main():
  logging.getLogger().setLevel(logging.DEBUG)
  application = webapp.WSGIApplication([('/task', TaskRoute),
                                        ('/size', SizeRoute),
                                        ('/supportspullqueue', SupportsPullQueue),
                                        ('/', IndexPage),
                                        ],
                                        debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
