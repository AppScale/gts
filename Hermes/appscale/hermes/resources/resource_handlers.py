""" Implementation of stats sources for cluster stats. """
import asyncio
import inspect
import json
import logging

import aiohttp
from aiohttp import web

from appscale.common import appscale_info
from appscale.hermes import constants
from appscale.hermes.resources import process

logger = logging.getLogger(__name__)

# Do not run more than 100 concurrent requests to remote hermes servers.
max_concurrency = asyncio.Semaphore(100)

# To avoid unnecessary JSON decoding and encoding,
# when listing a resource from a remote hermes,
# entities and failures are sent as two separate JSON lists connected by:
BODY_CONNECTOR = b'\n\n\xff\xff\xff\xff\n\n'


class HermesError(aiohttp.ClientError):
  """ Represents an error while listing resource from local/remote Hermes. """
  def __init__(self, host, message):
    self.host = host
    self.message = message
    super().__init__(message)


class ResourceHandler(object):
  """
  A class implementing HTTP handlers for listing a monitored resource.

  It provides two public handler methods:
   - list_local(request)    # For listing local resource
   - list_cluster(request)  # For listing resource on many nodes
  """
  def __init__(self, default_ips_getter, resource_name, local_source):
    """ Initialised instance of ResourceHandler.

    Args:
      default_ips_getter: A callable - should return a list of cluster nodes
                          to query resource from.
      resource_name: A str - name of resource (should match name in route).
      local_source: A callable (optionally async) - should return a tuple
                    of two lists: (entity_dicts, failure_strings).
    """
    self.default_ips_getter = default_ips_getter
    self.resource_name = resource_name
    self.local_source = local_source
    self.private_ip = appscale_info.get_private_ip()

  async def list_local(self, request):
    """ A handler method to be assigned to route
    'GET /v2/<resource_name>'.
    It accepts one optional query argument: 'return-as-2-json-objects=yes',
    if it is passed, entities and failures are returned as two JSON objects
    connected by BODY_CONNECTOR.

    Args:
      request: An instance of aiohttp.web.Request.
    Returns:
      An instance of aiohttp.web.Response.
    """
    entities, failures = await self._call_local_source()

    if request.query.get('return-as-2-json-objects', 'no') == 'yes':
      # Return body used for joining entities without decoding JSON.
      body = b'%(entities)b %(connector)b %(failures)b' % {
        b'entities': json.dumps(entities).encode(),
        b'connector': BODY_CONNECTOR,
        b'failures': json.dumps(failures).encode()
      }
      return web.Response(body=body)
    else:
      # Return a regular JSON body.
      body = b'{"entities": %(entities)b, "failures": %(failures)b}' % {
        b'entities': json.dumps(entities).encode(),
        b'failures': json.dumps(failures).encode()
      }
      return web.Response(body=body, content_type='application/json')

  async def list_cluster(self, request):
    """ A handler method to be assigned to route
    'GET /v2/<resource_name>/_cluster'.
    It accepts optional JSON body containing list of locations to collect
    resource entities from. e.g.:
    {"locations": ["10.0.2.15", "10.0.2.16", "10.0.2.17"]}

    If body is missing,
    locations returned by self.default_ips_getter() will be used.

    Args:
      request: An instance of aiohttp.web.Request.
    Returns:
      An instance of aiohttp.web.Response.
    """
    if request.has_body:
       try:
         locations = (await request.json())['locations']
       except (ValueError, TypeError, KeyError) as err:
         reason = 'JSON body should contain "locations" attr ({}).'.format(err)
         return web.Response(status=400, reason=reason)
    else:
      locations = self.default_ips_getter()

    joined_entities_json, failures = await self._list_resource(locations)
    # As joined_entities_json is already valid JSON array,
    # we're rendering final JSON body manually.
    body = b'{"entities": %(entities)b, "failures": %(failures)b}' % {
      b'entities': joined_entities_json,
      b'failures': json.dumps(failures).encode()
    }
    return web.Response(body=body, content_type='application/json')

  async def _list_resource(self, hermes_locations):
    """ Asynchronously collects full list of resource entities
    from remote and local nodes.

    Args:
      hermes_locations: a list of strings - hermes locations as <host>[:<port>].
    Returns:
      A Future object which wraps a dict with node IP as key and
      an instance of stats snapshot as value.
    """
    entities_json_list = []
    failures = []

    async def process_node_result(hermes_location):
      """ Retrieves entities and failures from a particular hermes server
      and appends results to local lists.

      Args:
        hermes_location: A string  - hermes locations as <host>[:<port>].
      """
      try:
        entities_json, node_failures = await self._get_from_node(hermes_location)
        if entities_json:
          entities_json_list.append(entities_json)
        if node_failures:
          failures.extend(node_failures)
      except HermesError as err:
        failures.append({'host': err.host, 'message': err.message})

    # Do multiple requests asynchronously and wait for all results
    async with max_concurrency:
      await asyncio.gather(*[
        process_node_result(location) for location in hermes_locations
      ])

    logger.info('Fetched {name} from {nodes} nodes.'
                .format(name=self.resource_name, nodes=len(entities_json_list)))

    # Join raw JSON lists of entities to a single big list.
    # This way we avoid extra JSON decoding and encoding.
    joined_entities_json = b',\n\n'.join([
      raw_bytes.strip(b'[] ') for raw_bytes in entities_json_list
    ])
    return b'[%b]' % joined_entities_json, failures

  async def _get_from_node(self, hermes_location):
    """ Retrieves entities and failures from a particular hermes server
    (local or remote).

    Args:
      hermes_location: A string  - hermes locations as <host>[:<port>].
    Returns:
      A tuple (JSON encoded list of resource entities, list of failures).
    """
    if hermes_location.split(':')[0] == self.private_ip:
      # List local resource entities (and failures).
      try:
        entities, failures = await self._call_local_source()
        entities_json = json.dumps(entities).encode()
        return entities_json, failures
      except Exception as err:
        logger.error('Failed to prepare local stats: {err}'.format(err=err))
        raise HermesError(host=hermes_location, message=str(err))
    else:
      # List remote resource entities (and failures).
      entities_json, failures = await self._fetch_remote(hermes_location)
    return entities_json, failures

  async def _fetch_remote(self, hermes_location):
    """ Fetches resource entities from a single remote node.

    Args:
      hermes_location: a string  - remote hermes location as <host>[:<port>].
    Returns:
      A tuple (JSON encoded list of resource entities, list of failures).
    """
    # Security header
    headers = {constants.SECRET_HEADER: appscale_info.get_secret()}

    # Determine host and port of remote hermes
    if ':' in hermes_location:
      host, port = hermes_location.split(':')
    else:
      host = hermes_location
      port = constants.HERMES_PORT

    url = 'http://{host}:{port}/v2/{resource}'.format(
      host=host, port=port, resource=self.resource_name
    )
    try:
      # Do HTTP call to remote hermes requesting body in two parts.
      async with aiohttp.ClientSession() as session:
        awaitable_get = session.get(
          url, headers=headers, params={'return-as-2-json-objects': 'yes'},
          timeout=constants.REMOTE_REQUEST_TIMEOUT
        )
        async with awaitable_get as resp:
          if resp.status >= 400:
            # Handler client error
            err_message = 'HTTP {}: {}'.format(resp.status, resp.reason)
            resp_text = await resp.text()
            if resp_text:
              err_message += '. {}'.format(resp_text)
            logger.error("Failed to get {} ({})".format(url, err_message))
            raise HermesError(host=host, message=err_message)

          # Read body without decoding JSON
          body = await resp.read()
          entities_json, failures_json = body.split(BODY_CONNECTOR)
          failures = json.loads(failures_json.decode())
          return entities_json, failures

    except aiohttp.ClientError as err:
      # Handle server error
      logger.error("Failed to get {} ({})".format(url, err))
      raise HermesError(host=host, message=str(err))

  async def _call_local_source(self):
    """ A wrapper method for retrieving local resource entities and failures.
    It awaits awaitable if needed and add host information to failures.

    Returns:
      A tuple (list of resource entities, list of failures).
    """
    local = self.local_source()
    if inspect.isawaitable(local):
      entities, failures = await local
    else:
      entities, failures = local
    failures = [{'host': self.private_ip, 'message': message}
                for message in failures]
    return entities, failures


processes = ResourceHandler(
  default_ips_getter=appscale_info.get_all_ips,
  resource_name='processes',
  local_source=process.list_resource
)
