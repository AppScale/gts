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


"""Main handler script for running Django applications on App Engine."""










import logging
import os

from google.appengine.api import lib_config











_config_handle = lib_config.register(
    'django', {'settings_module': os.getenv('DJANGO_SETTINGS_MODULE',
                                            'settings')})
settings_path = _config_handle.settings_module

from google.appengine.ext.webapp import util




os.environ['DJANGO_SETTINGS_MODULE'] = settings_path

if os.environ.get('APPENGINE_RUNTIME') == 'python':


  import google.appengine.ext.webapp.template
else:

  try:
    import django
  except ImportError:
    msg = (
        'django must be included in the "libraries:" clause of your app.yaml '
        'file when using the django_wsgi builtin.')
    logging.error(msg)
    raise RuntimeError(msg)

from django.core import management
from django.core.handlers import wsgi





try:
  settings = __import__(settings_path)
  management.setup_environ(settings, original_settings_path=settings_path)
except ImportError:



  pass

app = wsgi.WSGIHandler()


def main():
  """Main program. Run the Django WSGIApplication."""
  util.run_wsgi_app(app)


if __name__ == '__main__':
  main()
