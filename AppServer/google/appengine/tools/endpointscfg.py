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
service to generate a client library for a target language (currently Java or
Python)

Example:
  endpointscfg.py gen_client_lib -l java -o . greetings-v0.1-rest.api

The get_client_lib subcommand does both of the above commands at once.

Example:
  endpointscfg.py get_client_lib -o . -f rest -l java postservice.GreetingsV1
"""

from __future__ import with_statement


import contextlib
import os.path
import re
import sys
import urllib
import urllib2

from protorpc import remote

from google.appengine.ext.endpoints import api_config


DISCOVERY_DOC_BASE = ('https://webapis-discovery.appspot.com/_ah/api/'
                      'discovery/v1/apis/generate/')


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
  with open(path, 'w') as f:
    f.write(content)
  return path


def GenApiConfig(service_class_names):
  """Write an API configuration for endpoints annotated ProtoRPC services.

  Args:
    service_class_names: A list of fully qualified ProtoRPC service classes.

  Raises:
    TypeError: If any service classes don't inherit from remote.Service.
    messages.DefinitionNotFoundError: If a service can't be found.

  Returns:
    A map from service names to a string containing the API configuration of the
      service in JSON format.
  """
  service_map = {}
  generator = api_config.ApiConfigGenerator()
  for service_class_name in service_class_names:
    module_name, base_service_class_name = service_class_name.rsplit('.', 1)
    module = __import__(module_name, fromlist=base_service_class_name)
    service = getattr(module, base_service_class_name)
    if issubclass(service, remote.Service):
      service_map[service_class_name] = generator.pretty_print_config_to_json(
          service)
    else:
      raise TypeError('%s is not a ProtoRPC service' % service_class_name)

  return service_map


def GenDiscoveryDoc(service_class_names, doc_format, output_path):
  """Write discovery documents generated from a cloud service to file.

  Args:
    service_class_names: A list of fully qualified ProtoRPC service names.
    doc_format: The requested format for the discovery doc. (rest|rpc)
    output_path: The directory to output the discovery docs to.

  Raises:
    urllib2.HTTPError: If fetching the generated discovery doc fails.

  Returns:
    A mapping from service names to discovery docs.
  """


  import simplejson
  output_files = []
  service_configs = GenApiConfig(service_class_names)
  for service_class_name, config in service_configs.iteritems():
    body = simplejson.dumps({'config': config}, indent=2, sort_keys=True)
    request = urllib2.Request(DISCOVERY_DOC_BASE + doc_format, body)
    request.add_header('content-type', 'application/json')

    with contextlib.closing(urllib2.urlopen(request)) as response:
      content = response.read()
      _, base_service_class_name = service_class_name.rsplit('.', 1)
      discovery_name = base_service_class_name + '.discovery'
      output_files.append(_WriteFile(output_path, discovery_name, content))

  return output_files


def GenClientLib(discovery_path, language, output_path):
  """Write a client library from a discovery doc, using a cloud service to file.

  Args:
    discovery_path: Path to the discovery doc used to generate the client
      library.
    language: The client library language to generate. (java|python)
    output_path: The directory to output the client library zip to.

  Raises:
    IOError: If reading the discovery doc fails.
    urllib2.HTTPError: If fetching the generated client library fails.

  Returns:
    The path to the zipped client library.
  """
  with open(discovery_path) as f:
    discovery_doc = f.read()

  body = urllib.urlencode({'lang': language, 'content': discovery_doc})
  request = urllib2.Request(
      'http://google-api-client-libraries.appspot.com/generate', body)
  with contextlib.closing(urllib2.urlopen(request)) as response:
    content = response.read()
    client_name = re.sub(r'\.discovery$', '.zip',
                         os.path.basename(discovery_path))
    return _WriteFile(output_path, client_name, content)


def GetClientLib(service_class_names, doc_format, language, output_path):
  """Fetch discovery documents and client libraries from a cloud service.

  Args:
    service_class_names: A list of fully qualified ProtoRPC service names.
    doc_format: The requested format for the discovery doc. (rest|rpc)
    language: The client library language to generate. (java|python)
    output_path: The directory to output the discovery docs to.

  Returns:
    A tuple (discovery_files, client_libs):
      discovery_files: A list of paths to discovery documents.
      client_libs: A list of paths to client libraries.
  """
  discovery_files = GenDiscoveryDoc(service_class_names, doc_format,
                                    output_path)
  client_libs = []
  for discovery_path in discovery_files:
    client_libs.append(
        GenClientLib(discovery_path, language, output_path))
  return discovery_files, client_libs


def _GetClientLibCallback(args,
                          client_func=GetClientLib):
  """Generate discovery docs and client libraries to files.

  Args:
    args: An argparse.Namespace object to extract parameters from.
    client_func: A function that generates client libraries and stores them to
      files, accepting a list of service names, a discovery doc format, a client
      library language, and an output directory.
  """
  sys.path.append(os.path.abspath(args.application))
  service_class_names, doc_format, language, output_path = (
      args.service, args.format, args.language, args.output)
  discovery_paths, client_paths = client_func(service_class_names, doc_format,
                                              language, output_path)

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
  sys.path.append(os.path.abspath(args.application))
  services, doc_format, output_path = args.service, args.format, args.output
  discovery_paths = discovery_func(services, doc_format, output_path)
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
      args: A list of option names to add. Possible names are: application,
        format, output, language, service, and discovery_doc.
    """
    if 'application' in args:
      parser.add_argument('-a', '--application', default='.',
                          help='The path to the Python App Engine App')
    if 'format' in args:
      parser.add_argument('-f', '--format', default='rest',
                          choices=['rest', 'rpc'],
                          help='The requested API protocol type')
    if 'output' in args:
      parser.add_argument('-o', '--output', default='.',
                          help='The directory to store output files')
    if 'language' in args:
      parser.add_argument('language', choices=['java', 'python'],
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
  AddStandardOptions(get_client_lib, 'application', 'format', 'output',
                     'language', 'service')

  gen_discovery_doc = subparsers.add_parser(
      'gen_discovery_doc',
      help='Generates discovery documents from service classes')
  gen_discovery_doc.set_defaults(callback=_GenDiscoveryDocCallback)
  AddStandardOptions(gen_discovery_doc, 'application', 'format', 'output',
                     'service')

  gen_client_lib = subparsers.add_parser(
      'gen_client_lib', help='Generates a client library from service classes')
  gen_client_lib.set_defaults(callback=_GenClientLibCallback)
  AddStandardOptions(gen_client_lib, 'output', 'language', 'discovery_doc')

  return parser


def main(argv):
  parser = MakeParser(argv[0])
  args = parser.parse_args(argv[1:])

  args.callback(args)
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv))
