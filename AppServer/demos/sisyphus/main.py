try:
  import simplejson as json
except ImportError:
  import json

import datetime
import logging

from google.appengine.api import memcache
from google.appengine.api import users

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util


# A Component in the system refers to a server that will be reporting data,
# uniquely identified by its name (e.g., AppController) and its IP address.
# TODO(cgb): Will there be scenarios where more than one component runs on
# a given machine and they need to be uniquely identified?
class Component(db.Model):
  name = db.StringProperty()
  ip = db.StringProperty()


# A single Log entry has a reference to the Component that produced it,
# the actual log text, and the time of the event.
class Log(db.Model):
  component = db.ReferenceProperty(Component)
  text = db.TextProperty()
  timestamp = db.FloatProperty()


# Stores and retrieves logs from user requests.
class LogHandler(webapp.RequestHandler):

  # GET /log accepts at least two parameters: a name and ip, used to
  # uniquely identify the component that we want logs for, and (optionally)
  # the earliest time that we want logs for, used for pagination.
  def get(self):
    if not users.is_current_user_admin():
      response = json.dumps({'success' : False, 'reason' : 'not authorized'})
      self.response.out.write(response)
      return

    str_payload = self.request.get('payload')
    payload = json.loads(str_payload)

    name = payload['name']
    ip = payload['ip']
    name_and_ip = name + ip

    earliest_time = 0.0
    if 'earliest_time' in payload:
      earliest_time = payload['earliest_time']

    # Check memcache for our logs before going to the Datastore
    key = name + ip + str(earliest_time)
    memcache_data = memcache.get(key)
    if memcache_data is not None:
      self.response.out.write(memcache_data)
      return

    # If we get here, it's not in Memcache, so get it from the Datastore
    component = Component.get_by_key_name(name_and_ip)
    logs_to_return = []
    logs = db.GqlQuery("SELECT * FROM Log " +
                       "WHERE component = :1 AND timestamp >= :2",
                       component, earliest_time)
    for log in logs:
      item = {'text' : log.text, 
              'timestamp' : log.timestamp}
      logs_to_return.append(item)
    
    last_log_index = len(logs_to_return) - 1
    log_data = {'success' : True, 'logs' : logs_to_return}

    if last_log_index < 0:
      log_data['last_timestamp'] = 0.0
    else:
      log_data['last_timestamp'] = logs_to_return[last_log_index]['timestamp']

    # Dump the log data into Memcache to speed up further reads
    # and send it to the user
    dumped_log_data = json.dumps(log_data)
    memcache.set(key, dumped_log_data, 30)
    self.response.out.write(dumped_log_data)


  # POST /log accepts a single object, payload, which is a dict with three
  # entries: name (string), ip (string), and logs (list). The first two
  # are used to uniquely identify the component that is dumping logs to us,
  # while the third is a list of logs (each a log entry and timestamp) that
  # we should store.
  def post(self):
    str_payload = self.request.get('payload')
    payload = json.loads(str_payload)

    name = payload['name']
    ip = payload['ip']
    name_and_ip = name + ip
    component = Component.get_by_key_name(name_and_ip)

    logs = payload['logs']
    for log in logs:
      new_log = Log(component = component,
                    text = log['text'],
                    timestamp = float(log['timestamp']))
      new_log.put()

    response = {"success" : True}
    self.response.out.write(json.dumps(response))


# Reports on the components that we are receiving log events for, and
# accepts registration for new components.
class ComponentHandler(webapp.RequestHandler):

  # GET /component returns a JSON list, where each element is a dict
  # with the name and ip of that component.
  def get(self):
    if not users.is_current_user_admin():
      response = json.dumps({'success' : False, 'reason' : 'not authorized'})
      self.response.out.write(response)
      return

    component_list = []

    components = db.GqlQuery("SELECT * FROM Component")
    for component in components:
      item = {'success' : True, "name" : component.name, "ip" : component.ip}
      component_list.append(item)

    self.response.out.write(json.dumps(component_list))
  
  # POST /component accepts info about the new component and saves
  # it accordingly. It requires a single parameter, 'components',
  # which is a JSON list of dicts, in the same format as is returned
  # in the GET method above.
  def post(self):
    str_payload = self.request.get('payload')
    payload = json.loads(str_payload)
    components = payload['components']

    for component in components:
      name = component['name']
      ip = component['ip']
      name_and_ip = name + ip
      new_component = Component(key_name = name_and_ip)
      new_component.name = name
      new_component.ip = ip
      new_component.put()

    response = {"success" : True}
    self.response.out.write(json.dumps(response))


# Tells callers who is logged in
class UserInfoHandler(webapp.RequestHandler):
  # The top-left bar needs to know who is signed in to the app. This route
  # provides that information. Sisyphus should be guarded to admins-only,
  # since these logs definitely have security-sensitive info, but in testing
  # that may be disabled, so it is possible not to be logged in.
  def get(self):
    response = {}
    user = users.get_current_user()
    if user:
      response = {'user' : user.nickname(), 'logged_in' : True}
    else:
      response = {'user' : None, 'logged_in' : False}
    self.response.out.write(json.dumps(response))


# Displays logs to the user
class IndexPage(webapp.RequestHandler):
  def get(self):
    if not users.is_current_user_admin():
      response = json.dumps({'success' : False, 'reason' : 'not authorized'})
      self.response.out.write(response)
      return

    self.response.out.write(template.render('index.html', {}))


# Sets up URL routes
def main():
  logging.getLogger().setLevel(logging.DEBUG)
  application = webapp.WSGIApplication([('/log', LogHandler),
                                        ('/component', ComponentHandler),
                                        ('/whoami', UserInfoHandler),
                                        ('/', IndexPage),
                                        ],
                                        debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
