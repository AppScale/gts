# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Interactive Python shell for Flex example.

@since: 0.3
"""

import sys, logging, types, new
import traceback, pickle
import StringIO

from google.appengine.ext import webapp
from google.appengine.ext import db
import wsgiref.handlers

from pyamf.remoting.gateway.django import DjangoGateway
from pyamf.remoting.gateway import expose_request

# Types that can't be pickled.
UNPICKLABLE_TYPES = (
  types.ModuleType,
  types.TypeType,
  types.ClassType,
  types.FunctionType,
)

# Unpicklable statements to seed new sessions with.
INITIAL_UNPICKLABLES = [
  'import logging',
  'import os',
  'import sys',
  'from google.appengine.ext import db',
  'from google.appengine.api import users',
  ]

class Session(db.Model):
  """A shell session. Stores the session's globals.

  Each session globals is stored in one of two places:

  If the global is picklable, it's stored in the parallel globals and
  global_names list properties. (They're parallel lists to work around the
  unfortunate fact that the datastore can't store dictionaries natively.)

  If the global is not picklable (e.g. modules, classes, and functions), or if
  it was created by the same statement that created an unpicklable global,
  it's not stored directly. Instead, the statement is stored in the
  unpicklables list property. On each request, before executing the current
  statement, the unpicklable statements are evaluated to recreate the
  unpicklable globals.

  The unpicklable_names property stores all of the names of globals that were
  added by unpicklable statements. When we pickle and store the globals after
  executing a statement, we skip the ones in unpicklable_names.

  Using Text instead of string is an optimization. We don't query on any of
  these properties, so they don't need to be indexed.
  """
  global_names = db.ListProperty(db.Text)
  globals = db.ListProperty(db.Blob)
  unpicklable_names = db.ListProperty(db.Text)
  unpicklables = db.ListProperty(db.Text)

  def set_global(self, name, value):
    """Adds a global, or updates it if it already exists.

    Also removes the global from the list of unpicklable names.

    Args:
      name: the name of the global to remove
      value: any picklable value
    """
    blob = db.Blob(pickle.dumps(value))

    if name in self.global_names:
      index = self.global_names.index(name)
      self.globals[index] = blob
    else:
      self.global_names.append(db.Text(name))
      self.globals.append(blob)

    self.remove_unpicklable_name(name)

  def remove_global(self, name):
    """Removes a global, if it exists.

    Args:
      name: string, the name of the global to remove
    """
    if name in self.global_names:
      index = self.global_names.index(name)
      del self.global_names[index]
      del self.globals[index]

  def globals_dict(self):
    """Returns a dictionary view of the globals.
    """
    return dict((name, pickle.loads(val))
                for name, val in zip(self.global_names, self.globals))

  def add_unpicklable(self, statement, names):
    """Adds a statement and list of names to the unpicklables.

    Also removes the names from the globals.

    Args:
      statement: string, the statement that created new unpicklable global(s).
      names: list of strings; the names of the globals created by the statement.
    """
    self.unpicklables.append(db.Text(statement))

    for name in names:
      self.remove_global(name)
      if name not in self.unpicklable_names:
        self.unpicklable_names.append(db.Text(name))

  def remove_unpicklable_name(self, name):
    """Removes a name from the list of unpicklable names, if it exists.

    Args:
      name: string, the name of the unpicklable global to remove
    """
    if name in self.unpicklable_names:
      self.unpicklable_names.remove(name)

class ShellService:
  
  def _evalCode(self, statement, session):
    if not statement:
      return

    # add a couple newlines at the end of the statement. this makes
    # single-line expressions such as 'class Foo: pass' evaluate happily.
    statement += '\n\n'

    # log and compile the statement up front
    logging.info('Compiling and evaluating:\n%r' % statement)
    compiled = compile(statement, '<string>', 'single')

    # create a dedicated module to be used as this statement's __main__
    statement_module = new.module('__main__')

    # use this request's __builtin__, since it changes on each request.
    # this is needed for import statements, among other things.
    import __builtin__
    statement_module.__builtins__ = __builtin__

    # swap in our custom module for __main__. then unpickle the session
    # globals, run the statement, and re-pickle the session globals, all
    # inside it.
    old_main = sys.modules.get('__main__')
    try:
      sys.modules['__main__'] = statement_module
      statement_module.__name__ = '__main__'

      # re-evaluate the unpicklables
      for code in session.unpicklables:
        exec code in statement_module.__dict__

      # re-initialize the globals
      for name, val in session.globals_dict().items():
        try:
          statement_module.__dict__[name] = val
        except:
          msg = 'Dropping %s since it could not be unpickled.\n' % name
          logging.warning(msg + traceback.format_exc())
          session.remove_global(name)
          buffer.write(msg)

      # run!
      old_globals = dict(statement_module.__dict__)
      exec compiled in statement_module.__dict__

      # extract the new globals that this statement added
      new_globals = {}
      for name, val in statement_module.__dict__.items():
        if name not in old_globals or val != old_globals[name]:
          new_globals[name] = val

      if True in [isinstance(val, UNPICKLABLE_TYPES)
                  for val in new_globals.values()]:
        # this statement added an unpicklable global. store the statement and
        # the names of all of the globals it added in the unpicklables.
        session.add_unpicklable(statement, new_globals.keys())
        logging.debug('Storing this statement as an unpicklable.')

      else:
        # this statement didn't add any unpicklables. pickle and store the
        # new globals back into the datastore.
        for name, val in new_globals.items():
          if not name.startswith('__'):
            session.set_global(name, val)

    finally:
      sys.modules['__main__'] = old_main

  def evalCode(self, request, statement):
    statement = statement.strip().replace('\r\n', '\n').replace('\r', '\n')
    buffer = StringIO.StringIO()

    buffer.write(statement + '\n')

    session = request.session

    try:
      old_stdout = sys.stdout
      old_stderr = sys.stderr
      try:
        sys.stdout = buffer
        sys.stderr = buffer

        self._evalCode(statement, session)
      finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

        session.put()
    except:
      buffer.write(traceback.format_exc())
    
    buffer.write('>>> ')

    return buffer.getvalue()

  def startup(self, request):
    return "Welcome to the PyAMF Python Shell Demo!\n\n>>> "


class SessionExposingAppGateway(DjangoGateway):
    def __call__(self, http_request):
        new = False

        try:
            key = http_request.COOKIES['SESSION_KEY']
            http_request.session = Session.get(key)
        except KeyError:
            new = True
            http_request.session = Session()
            http_request.session.put()

        try:
            http_response = DjangoGateway.__call__(self, http_request)
        finally:
            if new:
                http_response.set_cookie('SESSION_KEY', http_request.session.key())

        return http_response

services = {
    'shell': ShellService
}

gateway = SessionExposingAppGateway(services)