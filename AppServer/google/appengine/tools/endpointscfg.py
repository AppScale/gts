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

"""External script for generating Cloud Endpoints related files.

The gen_discovery_doc subcommand takes a list of fully qualified ProtoRPC
service names and calls a cloud service which generates a discovery document in
REST or RPC style.

Example:
  endpointscfg.py gen_discovery_doc -o . -f rest postservice.GreetingsV1

The gen_client_lib subcommand takes a discovery document and calls a cloud
service to generate a client library for a target language (currently just Java)

Example:
  endpointscfg.py gen_client_lib java -o . greetings-v0.1-rest.api

The get_client_lib subcommand does both of the above commands at once.

Example:
  endpointscfg.py get_client_lib java -o . -f rest postservice.GreetingsV1

The gen_api_config command outputs an .api configuration file for a service.

Example:
  endpointscfg.py gen_api_config -o . -a /path/to/app \
    --hostname myhost.appspot.com postservice.GreetingsV1
"""

from __future__ import with_statement


import contextlib

try:
  import json
except ImportError:
  import simplejson as json
import os
import re
import sys
import urllib
import urllib2

from protorpc import remote

from google.appengine.ext.endpoints import api_config


DISCOVERY_DOC_BASE = ('https://webapis-discovery.appspot.com/_ah/api/'
                      'discovery/v1/apis/generate/')
CLIENT_LIBRARY_BASE = 'https://google-api-client-libraries.appspot.com/generate'


class ServerRequestException(Exception):
  """Exception for problems with the request to a server."""

  def __init__(self, http_error):
    """Create a ServerRequestException from a given urllib2.HTTPError.

    Args:
      http_error: The HTTPError that the ServerRequestException will be
        based on.
    """
    error_details = None
    if http_error.fp:
      try:
        error_body = json.load(http_error.fp)
        error_details = ['%s: %s' % (detail['message'], detail['debug_info'])
                         for detail in error_body['error']['errors']]
      except (ValueError, TypeError, KeyError):
        pass
    if error_details:
      error_message = ('HTTP %s (%s) error when communicating with URL: %s.  '
                       'Details: %s' % (http_error.code, http_error.reason,
                                        http_error.filename, error_details))
    else:
      error_message = ('HTTP %s (%s) error when communicating with URL: %s.' %
                       (http_error.code, http_error.reason,
                        http_error.filename))
    super(ServerRequestException, self).__init__(error_message)


def _WriteFile(output_path, name, content):
  """Write given content to a file in a given directory.

  Args:
    output_path: The directory to store the file in.
    name: The name of the file to store the content in.
    content: The content to write to the file.close

  Returns:
    The full path to the written file.
  """
  path = os.path.join(output_path, name)
  with open(path, 'wb') as f:
    f.write(content)
  return path


def GenApiConfig(service_class_names, generator=None, hostname=None):
  """Write an API configuration for endpoints annotated ProtoRPC services.

  Args:
    service_class_names: A list of fully qualified ProtoRPC service classes.
    generator: An generator object that produces API config strings using its
      pretty_print_config_to_json method.
    hostname: A string hostname which will be used as the default version
      hostname. If no hostname is specificied in the @endpoints.api decorator,
      this value is the fallback. Defaults to None.

  Raises:
    TypeError: If any service classes don't inherit from remote.Service.
    messages.DefinitionNotFoundError: If a service can't be found.

  Returns:
    A map from service names to a string containing the API configuration of the
      service in JSON format.
  """
  service_map = {}
  generator = generator or api_config.ApiConfigGenerator()
  for service_class_name in service_class_names:
    module_name, base_service_class_name = service_class_name.rsplit('.', 1)
    module = __import__(module_name, fromlist=base_service_class_name)
    service = getattr(module, base_service_class_name)
    if not (isinstance(service, type) and issubclass(service, remote.Service)):
      raise TypeError('%s is not a ProtoRPC service' % service_class_name)


    hostname = service.api_info.hostname or hostname
    service_map[service_class_name] = generator.pretty_print_config_to_json(
        service, hostname=hostname)

  return service_map


def GenDiscoveryDoc(service_class_names, doc_format,
                    output_path, hostname=None):
  """Write discovery documents generated from a cloud service to file.

  Args:
    service_class_names: A list of fully qualified ProtoRPC service names.
    doc_format: The requested format for the discovery doc. (rest|rpc)
    output_path: The directory to output the discovery docs to.
    hostname: A string hostname which will be used as the default version
      hostname. If no hostname is specificied in the @endpoints.api decorator,
      this value is the fallback. Defaults to None.

  Raises:
    ServerRequestException: If fetching the generated discovery doc fails.

  Returns:
    A mapping from service names to discovery docs.
  """
  output_files = []
  service_configs = GenApiConfig(service_class_names, hostname=hostname)
  for service_class_name, config in service_configs.iteritems():
    body = json.dumps({'config': config}, indent=2, sort_keys=True)
    request = urllib2.Request(DISCOVERY_DOC_BASE + doc_format, body)
    request.add_header('content-type', 'application/json')

    try:
      with contextlib.closing(urllib2.urlopen(request)) as response:
        content = response.read()
        _, base_service_class_name = service_class_name.rsplit('.', 1)
        discovery_name = base_service_class_name + '.discovery'
        output_files.append(_WriteFile(output_path, discovery_name, content))
    except urllib2.HTTPError, error:
      raise ServerRequestException(error)

  return output_files


def GenClientLib(discovery_path, language, output_path):
  """Write a client library from a discovery doc, using a cloud service to file.

  Args:
    discovery_path: Path to the discovery doc used to generate the client
      library.
    language: The client library language to generate. (java)
    output_path: The directory to output the client library zip to.

  Raises:
    IOError: If reading the discovery doc fails.
    ServerRequestException: If fetching the generated client library fails.

  Returns:
    The path to the zipped client library.
  """
  with open(discovery_path) as f:
    discovery_doc = f.read()

  client_name = re.sub(r'\.discovery$', '.zip',
                       os.path.basename(discovery_path))

  _GenClientLibFromContents(discovery_doc, language, output_path, client_name)


def _GenClientLibFromContents(discovery_doc, language, output_path,
                              client_name):
  """Write a client library from a discovery doc, using a cloud service to file.

  Args:
    discovery_doc: A string, the contents of the discovery doc used to
      generate the client library.
    language: A string, the client library language to generate. (java)
    output_path: A string, the directory to output the client library zip to.
    client_name: A string, the filename used to save the client lib.

  Raises:
    IOError: If reading the discovery doc fails.
    ServerRequestException: If fetching the generated client library fails.

  Returns:
    The path to the zipped client library.
  """

  body = urllib.urlencode({'lang': language, 'content': discovery_doc})
  request = urllib2.Request(CLIENT_LIBRARY_BASE, body)
  try:
    with contextlib.closing(urllib2.urlopen(request)) as response:
      content = response.read()
      return _WriteFile(output_path, client_name, content)
  except urllib2.HTTPError, error:
    raise ServerRequestException(error)


def GetClientLib(service_class_names, doc_format, language,
                 output_path, hostname=None):
  """Fetch discovery documents and client libraries from a cloud service.

  Args:
    service_class_names: A list of fully qualified ProtoRPC service names.
    doc_format: The requested format for the discovery doc. (rest|rpc)
    language: The client library language to generate. (java)
    output_path: The directory to output the discovery docs to.
    hostname: A string hostname which will be used as the default version
      hostname. If no hostname is specificied in the @endpoints.api decorator,
      this value is the fallback. Defaults to None.

  Returns:
    A tuple (discovery_files, client_libs):
      discovery_files: A list of paths to discovery documents.
      client_libs: A list of paths to client libraries.
  """
  discovery_files = GenDiscoveryDoc(service_class_names, doc_format,
                                    output_path, hostname=hostname)
  client_libs = []
  for discovery_path in discovery_files:
    client_libs.append(
        GenClientLib(discovery_path, language, output_path))
  return discovery_files, client_libs


def _GenApiConfigCallback(args, api_func=GenApiConfig):
  """Generate an api file.

  Args:
    args: An argparse.Namespace object to extract parameters from.
    api_func: A function that generates and returns an API configuration
      for a list of services.
  """
  service_class_names, output_path, hostname = (
      args.service, args.output, args.hostname)
  service_configs = api_func(service_class_names, hostname=hostname)

  for service_class_name, config in service_configs.iteritems():
    _, base_service_class_name = service_class_name.rsplit('.', 1)
    api_name = base_service_class_name + '.api'
    _WriteFile(output_path, api_name, config)


def _GetClientLibCallback(args,
                          client_func=GetClientLib):
  """Generate discovery docs and client libraries to files.

  Args:
    args: An argparse.Namespace object to extract parameters from.
    client_func: A function that generates client libraries and stores them to
      files, accepting a list of service names, a discovery doc format, a client
      library language, and an output directory.
  """
  service_class_names, doc_format, language, output_path, hostname = (
      args.service, args.format, args.language, args.output, args.hostname)
  discovery_paths, client_paths = client_func(
      service_class_names, doc_format, language, output_path, hostname=hostname)

  for discovery_path in discovery_paths:
    print 'API discovery document written to %s' % discovery_path

  for client_path in client_paths:
    print 'API client library written to %s' % client_path


def _GenDiscoveryDocCallback(args, discovery_func=GenDiscoveryDoc):
  """Generate discovery docs to files.

  Args:
    args: An argparse.Namespace object to extract parameters from
    discovery_func: A function that generates discovery docs and stores them to
      files, accepting a list of service names, a discovery doc format, and an
      output directory.
  """
  services, doc_format, output_path, hostname = (
      args.service, args.format, args.output, args.hostname)
  discovery_paths = discovery_func(services, doc_format,
                                   output_path, hostname=hostname)
  for discovery_path in discovery_paths:
    print 'API discovery document written to %s' % discovery_path


def _GenClientLibCallback(args, client_func=GenClientLib):
  """Generate a client library to file.

  Args:
    args: An argparse.Namespace object to extract parameters from
    client_func: A function that generates client libraries and stores them to
      files, accepting a path to a discovery doc, a client library language, and
      an output directory.
  """
  discovery_path, language, output_path = (args.discovery_doc[0], args.language,
                                           args.output)
  client_path = client_func(discovery_path, language, output_path)
  print 'API client library written to %s' % client_path


def MakeParser(prog):
  """Create an argument parser.

  Args:
    prog: The name of the program to use when outputting help text.

  Returns:
    An argparse.ArgumentParser built to specification.
  """



  import argparse

  def AddStandardOptions(parser, *args):
    """Add common endpoints options to a parser.

    Args:
      parser: The parser to add options to.
      *args: A list of option names to add. Possible names are: application,
        format, output, language, service, and discovery_doc.
    """
    if 'application' in args:
      parser.add_argument('-a', '--application', default='.',
                          help='The path to the Python App Engine App')
    if 'format' in args:
      parser.add_argument('-f', '--format', default='rest',
                          choices=['rest', 'rpc'],
                          help='The requested API protocol type')
    if 'hostname' in args:
      help_text = ('Default application hostname, if none is specified '
                   'for API service.')
      parser.add_argument('--hostname', help=help_text)
    if 'output' in args:
      parser.add_argument('-o', '--output', default='.',
                          help='The directory to store output files')
    if 'language' in args:
      parser.add_argument('language', choices=['java'],
                          help='The target output programming language')
    if 'service' in args:
      parser.add_argument('service', nargs='+',
                          help='Fully qualified service class name')
    if 'discovery_doc' in args:
      parser.add_argument('discovery_doc', nargs=1,
                          help='Path to the discovery document')

  parser = argparse.ArgumentParser(prog=prog)
  subparsers = parser.add_subparsers(title='subcommands')

  get_client_lib = subparsers.add_parser(
      'get_client_lib', help=('Generates discovery documents and client '
                              'libraries from service classes'))
  get_client_lib.set_defaults(callback=_GetClientLibCallback)
  AddStandardOptions(get_client_lib, 'application', 'format', 'hostname',
                     'output', 'language', 'service')

  gen_api_config = subparsers.add_parser(
      'gen_api_config', help=('Generates an .api file for the given service '
                              'classes'))
  gen_api_config.set_defaults(callback=_GenApiConfigCallback)
  AddStandardOptions(gen_api_config, 'application', 'hostname', 'output',
                     'service')

  gen_discovery_doc = subparsers.add_parser(
      'gen_discovery_doc',
      help='Generates discovery documents from service classes')
  gen_discovery_doc.set_defaults(callback=_GenDiscoveryDocCallback)
  AddStandardOptions(gen_discovery_doc, 'application', 'format', 'hostname',
                     'output', 'service')

  gen_client_lib = subparsers.add_parser(
      'gen_client_lib', help='Generates a client library from service classes')
  gen_client_lib.set_defaults(callback=_GenClientLibCallback)
  AddStandardOptions(gen_client_lib, 'output', 'language', 'discovery_doc')

  return parser


def main(argv):
  parser = MakeParser(argv[0])
  args = parser.parse_args(argv[1:])



  application_path = getattr(args, 'application', None)
  if application_path is not None:
    sys.path.insert(0, os.path.abspath(application_path))

  args.callback(args)
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv))
