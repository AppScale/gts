#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#




"""A bridge between dev_appserver.py and a Go app."""























import asyncore
import atexit
import datetime
import errno
import getpass
import logging
import os
import random
import re
import shutil
import signal
import socket
import subprocess
import stat
import sys
import tempfile
import threading
import time

from google.appengine.ext.remote_api import handler
from google.appengine.ext.remote_api import remote_api_pb
from google.appengine.runtime import apiproxy_errors
from google.appengine.tools import dev_appserver

GAB_WORK_DIR = None
GO_APP = None
GO_APP_NAME = '_go_app'
GO_HTTP_PORT = 0
GO_API_PORT = 0
RAPI_HANDLER = None
HEALTH_CHECK_PATH = '/_appengine_delegate_health_check'
INTERNAL_SERVER_ERROR = ('Status: 500 Internal Server Error\r\n' +
    'Content-Type: text/plain\r\n\r\nInternal Server Error')
MAX_START_TIME = 10



HEADER_MAP = {
    'APPLICATION_ID': 'X-AppEngine-Inbound-AppId',
    'CONTENT_TYPE': 'Content-Type',
    'CURRENT_VERSION_ID': 'X-AppEngine-Inbound-Version-Id',
    'REMOTE_ADDR': 'X-AppEngine-Remote-Addr',
    'REQUEST_LOG_ID': 'X-AppEngine-Request-Log-Id',
    'USER_EMAIL': 'X-AppEngine-Inbound-User-Email',
    'USER_ID': 'X-AppEngine-Inbound-User-Id',
    'USER_IS_ADMIN': 'X-AppEngine-Inbound-User-Is-Admin',
}


ENV_PASSTHROUGH = re.compile(
    r'^(BACKEND_PORT\..*|INSTANCE_ID|SERVER_SOFTWARE)$'
)


OS_ENV_PASSTHROUGH = (

    'SYSTEMROOT',

    'USER',
)


APP_CONFIG = None


def quiet_kill(pid):
  """Send a SIGTERM to pid; won't raise an exception if pid is not running."""
  try:
    os.kill(pid, signal.SIGTERM)
  except OSError:
    pass


def pick_unused_port():
  for _ in range(10):
    port = int(random.uniform(32768, 60000))
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
      s.bind(('127.0.0.1', port))
      return port
    except socket.error:
      logging.info('could not bind to port %d', port)
    finally:
      s.close()
  raise dev_appserver.ExecuteError('could not pick an unused port')


def gab_work_dir(config, user, port):
  base = os.getenv('XDG_CACHE_HOME')
  if not base:
    if sys.platform == 'darwin':
      base = os.path.join(os.getenv('HOME'), 'Library', 'Caches',
                          'com.google.GoAppEngine')
    else:

      base = os.path.join(os.path.expanduser('~'), '.cache')


  if os.path.islink(base):
    try:
      os.makedirs(os.path.realpath(base))
    except OSError, e:

      if e.errno != errno.EEXIST:
        raise

  app = re.sub(r'[.:]', '_', config.application)
  return os.path.join(base,
      'dev_appserver_%s_%s_%s_go_app_work_dir' % (app, user, port))


def cleanup():
  try:
    shutil.rmtree(GAB_WORK_DIR)
  except:
    pass


class DelegateClient(asyncore.dispatcher):
  def __init__(self, http_req):
    asyncore.dispatcher.__init__(self)
    self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
    self.connect(('127.0.0.1', GO_HTTP_PORT))
    self.buffer = http_req
    self.result = ''
    self.closed = False

  def handle_close(self):
    self.close()
    self.closed = True

  def handle_connect(self):
    pass

  def handle_read(self):
    self.result += self.recv(8192)

  def handle_write(self):
    sent = self.send(self.buffer)
    self.buffer = self.buffer[sent:]

  def writable(self):
    return len(self.buffer) > 0


class DelegateServer(asyncore.dispatcher):
  def __init__(self):
    asyncore.dispatcher.__init__(self)
    self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
    self.bind(('127.0.0.1', GO_API_PORT))
    self.listen(5)

  def handle_accept(self):
    pair = self.accept()
    if not pair:
      return
    sock, addr = pair
    RemoteAPIHandler(sock)

  def writable(self):
    return False


class RemoteAPIHandler(asyncore.dispatcher_with_send):
  def __init__(self, sock):
    asyncore.dispatcher_with_send.__init__(self, sock)



    self.n = -1
    self.data = ''

  def handle_read(self):
    self.data += self.recv(8192)
    if self.n == -1:
      i = self.data.find('\n')
      if i == -1:

        return
      try:
        self.n = int(self.data[:i])
      except:
        self.n = -2
      if self.n < 0:

        self.n = -2
        self.data = ''
        return
      self.data = self.data[i+1:]
    elif self.n == -2:
      self.data = ''
      return
    if len(self.data) < self.n:

      return

    req = remote_api_pb.Request()
    req.ParseFromString(self.data[:self.n])
    self.data, self.n = self.data[self.n:], -1
    rapi_result = None
    rapi_error = 'unknown error'
    try:
      rapi_result = RAPI_HANDLER.ExecuteRequest(req)
    except apiproxy_errors.CallNotFoundError, e:


      service_name = req.service_name()
      method = req.method()
      rapi_error = 'call not found for %s/%s' % (service_name, method)
    except Exception, e:
      rapi_error = str(e)

    res = remote_api_pb.Response()
    if rapi_result:
      res.set_response(rapi_result.Encode())
    else:
      ae = res.mutable_application_error()


      ae.set_code(1)
      ae.set_detail(rapi_error)
    res1 = res.Encode()
    self.send('%d\n' % len(res1))
    self.send(res1)




def find_app_files(basedir):
  if not basedir.endswith(os.path.sep):
    basedir = basedir + os.path.sep
  files, dirs = {}, [basedir]
  while dirs:
    dname = dirs.pop()
    for entry in os.listdir(dname):
      ename = os.path.join(dname, entry)
      if APP_CONFIG.skip_files.match(ename):
        continue
      try:
        s = os.stat(ename)
      except OSError, e:
        logging.warn('%s', e)
        continue
      if stat.S_ISDIR(s[stat.ST_MODE]):
        dirs.append(ename)
        continue
      files[ename[len(basedir):]] = s[stat.ST_MTIME]
  return files




def find_go_files_mtime(app_files):
  files, mtime = [], 0
  for f, mt in app_files.items():
    if not f.endswith('.go'):
      continue
    if APP_CONFIG.nobuild_files.match(f):
      continue
    files.append(f)
    mtime = max(mtime, mt)
  return files, mtime


def wait_until_go_app_ready(proc, tee):

  deadline = (datetime.datetime.now() +
              datetime.timedelta(seconds=MAX_START_TIME))
  while datetime.datetime.now() < deadline:
    if proc.poll():
      raise dev_appserver.ExecuteError('Go app failed during init', tee.buf)
    try:
      s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      s.connect(('127.0.0.1', GO_HTTP_PORT))
      s.send('HEAD %s HTTP/1.0\r\n\r\n' % HEALTH_CHECK_PATH)
      s.close()
      return
    except:
      time.sleep(0.1)
  quiet_kill(proc.pid)
  raise dev_appserver.ExecuteError('unable to start ' + GO_APP_NAME, tee.buf)


def up(path, n):
  """Return the nth parent directory of the given path."""
  for _ in range(n):
    path = os.path.dirname(path)
  return path


class Tee(threading.Thread):
  """A simple line-oriented "tee".

  This class connects two file-like objects, piping the output of one to the
  input of the other, and buffering the last N lines.
  """

  MAX_LINES = 100

  def __init__(self, in_f, out_f):
    threading.Thread.__init__(self, name='Tee')
    self.__in = in_f
    self.__out = out_f
    self.buf = []

  def run(self):
    while True:
      line = self.__in.readline()
      if not line:
        break
      self.__out.write(line)
      self.buf.append(line)
      if len(self.buf) > Tee.MAX_LINES:
        self.buf.pop(0)


class GoApp:
  def __init__(self, root_path):
    self.root_path = root_path
    self.proc = None
    self.proc_start = 0
    self.last_extras_hash = None
    self.goroot = os.path.join(

        up(__file__, 5),
        'goroot')
    if not os.path.isdir(self.goroot):
      raise Exception('no goroot found at ' + self.goroot)


    self.arch = None
    arch_map = {
        'arm': '5',
        'amd64': '6',
        '386': '8',
    }
    for p in os.listdir(os.path.join(self.goroot, 'pkg', 'tool')):

      if '_' not in p:
        continue
      arch = p.split('_', 1)[1]
      if arch in arch_map:
        self.arch = arch_map[arch]
        break
    if not self.arch:
      raise Exception('bad goroot: no compiler found')

    atexit.register(self.cleanup)

  def cleanup(self):
    if self.proc:
      quiet_kill(self.proc.pid)
      self.proc = None

  def make_and_run(self, env):
    app_files = find_app_files(self.root_path)
    go_files, go_mtime = find_go_files_mtime(app_files)
    if not go_files:
      raise Exception('no .go files in %s', self.root_path)
    app_mtime = max(app_files.values())
    bin_name, bin_mtime = os.path.join(GAB_WORK_DIR, GO_APP_NAME), 0
    try:
      bin_mtime = os.stat(bin_name)[stat.ST_MTIME]
    except:
      pass





    rebuild, restart = False, False
    if go_mtime >= bin_mtime:
      rebuild, restart = True, True
    elif app_mtime > self.proc_start:
      restart = True
    if not rebuild:



      h = self.extras_hash(go_files)
      if h != self.last_extras_hash:
        logging.info('extra-app files hash changed to %s; rebuilding', h)
        self.last_extras_hash = h
        rebuild, restart = True, True

    if restart and self.proc:
      quiet_kill(self.proc.pid)
      self.proc.wait()
      self.proc = None
    if rebuild:
      self.build(go_files)


    if not self.proc or self.proc.poll() is not None:
      logging.info('running %s, HTTP port = %d, API port = %d',
          GO_APP_NAME, GO_HTTP_PORT, GO_API_PORT)

      limited_env = {
          'GOROOT': self.goroot,
          'PWD': self.root_path,
          'TZ': 'UTC',
      }
      for k, v in env.items():
        if ENV_PASSTHROUGH.match(k):
          limited_env[k] = v
      for e in OS_ENV_PASSTHROUGH:
        if e in os.environ:
          limited_env[e] = os.environ[e]
      self.proc_start = app_mtime
      self.proc = subprocess.Popen([bin_name,
          '-addr_http', 'tcp:127.0.0.1:%d' % GO_HTTP_PORT,
          '-addr_api', 'tcp:127.0.0.1:%d' % GO_API_PORT],
          stderr=subprocess.PIPE,
          cwd=self.root_path, env=limited_env)
      tee = Tee(self.proc.stderr, sys.stderr)
      tee.start()
      wait_until_go_app_ready(self.proc, tee)

  def _gab_args(self):
    argv = [
        os.path.join(self.goroot, 'bin', 'go-app-builder'),
        '-app_base', self.root_path,
        '-arch', self.arch,
        '-binary_name', GO_APP_NAME,
        '-dynamic',
        '-goroot', self.goroot,
        '-unsafe',
        '-work_dir', GAB_WORK_DIR,
    ]
    if 'GOPATH' in os.environ:
      argv.extend(['-gopath', os.environ['GOPATH']])
    return argv

  def build(self, go_files):
    logging.info('building ' + GO_APP_NAME)
    if not os.path.exists(GAB_WORK_DIR):
      os.makedirs(GAB_WORK_DIR)
    gab_argv = self._gab_args() + go_files
    try:
      p = subprocess.Popen(gab_argv, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, env={})
      gab_retcode = p.wait()
    except Exception, e:
      raise Exception('cannot call go-app-builder', e)
    if gab_retcode != 0:
      raise dev_appserver.CompileError(p.stdout.read() + '\n' + p.stderr.read())

  def extras_hash(self, go_files):
    logging.info('checking extra files')
    gab_argv = self._gab_args() + ['-print_extras_hash'] + go_files
    try:
      p = subprocess.Popen(gab_argv, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, env={})
      gab_retcode = p.wait()
    except Exception, e:
      raise Exception('cannot call go-app-builder', e)
    if gab_retcode != 0:
      raise dev_appserver.CompileError(p.stderr.read())
    return p.stdout.read()


OldSigTermHandler = None

def SigTermHandler(signum, frame):
  if GO_APP:
    GO_APP.cleanup()
  if OldSigTermHandler:
    OldSigTermHandler(signum, frame)

def execute_go_cgi(root_path, config, handler_path, cgi_path,
                   env, infile, outfile):

  global RAPI_HANDLER, GAB_WORK_DIR, GO_APP, GO_HTTP_PORT, GO_API_PORT
  global OldSigTermHandler
  if not RAPI_HANDLER:
    GAB_WORK_DIR = gab_work_dir(config, getpass.getuser(), env['SERVER_PORT'])
    GO_HTTP_PORT = pick_unused_port()
    GO_API_PORT = pick_unused_port()
    atexit.register(cleanup)
    try:









      OldSigTermHandler = signal.signal(signal.SIGTERM, SigTermHandler)
    except ValueError:












      pass
    DelegateServer()
    RAPI_HANDLER = handler.ApiCallHandler()
    GO_APP = GoApp(root_path)
  GO_APP.make_and_run(env)


  request_method = env['REQUEST_METHOD']
  server_protocol = env['SERVER_PROTOCOL']
  request_uri = env['PATH_INFO']
  if env.get('QUERY_STRING'):
    request_uri += '?' + env['QUERY_STRING']
  content = infile.getvalue()
  headers = []
  for k, v in env.items():
    if k in HEADER_MAP:
      headers.append('%s: %s' % (HEADER_MAP[k], v))
    elif k.startswith('HTTP_'):
      hk = k[5:].replace("_", "-")
      if hk.title() == 'Connection':
        continue
      headers.append('%s: %s' % (hk, v))

  headers.append('Content-Length: %d' % len(content))
  headers.append('Connection: close')
  http_req = (request_method + ' ' + request_uri + ' ' + server_protocol +
      '\r\n' + '\r\n'.join(headers) + '\r\n\r\n' + content)





  old_env = os.environ.copy()
  try:
    os.environ.clear()
    os.environ.update(env)


    x = DelegateClient(http_req)
    while not x.closed:
      asyncore.loop(30.0, False, None, 1)
    res = x.result
  finally:
    os.environ.clear()
    os.environ.update(old_env)



  if res.startswith('HTTP/1.0 ') or res.startswith('HTTP/1.1 '):
    res = 'Status:' + res[8:]
  else:
    res = INTERNAL_SERVER_ERROR
  outfile.write(res)
