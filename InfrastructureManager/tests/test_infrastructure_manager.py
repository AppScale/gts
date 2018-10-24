import json

try:
  from unittest import TestCase
except ImportError:
  from unittest.case import TestCase

import appscale.infrastructure as iaas

from tornado.testing import AsyncHTTPTestCase, gen_test
from tornado.httpclient import HTTPRequest, HTTPError
from tornado.ioloop import IOLoop
from tornado.escape import json_encode, json_decode
from mock import patch, Mock, PropertyMock, MagicMock
from appscale.tools.agents.base_agent import AgentRuntimeException
from appscale.tools.agents.ec2_agent import EC2Agent

full_params = {
  'credentials': {
    'a': 'b', 'EC2_URL': 'http://testing.appscale.com:8773/foo/bar',
    'EC2_ACCESS_KEY': 'access_key', 'EC2_SECRET_KEY': 'secret_key'},
  'group': 'boogroup',
  'image_id': 'booid',
  'infrastructure': 'ec2',
  'instance_type': 'booinstance_type',
  'keyname': 'bookeyname',
  'use_spot_instances': False,
  'region': 'my-zone-1',
  'zone': 'my-zone-1b',
  'autoscale_agent': True
}

zk_client = Mock()
agent_params = Mock()
agent_params.state_details = full_params
# @patch.object(iaas, 'zk_client', return_value=zk_client)
class TestInfrastructureManager(AsyncHTTPTestCase):

  def get_app(self):
    return iaas.make_app("secret")

  @gen_test
  def test_describe_instances(self):
    # No secret header.
    payload_request = HTTPRequest(
        method='GET', url=self.get_url('/instances'), headers=None, body=None
    )
    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)
      print context.exception
      self.assertEqual(context.exception.code, 401)
      self.assertEqual(context.exception.message, 'Invalid secret')

    # Invalid secret header.
    payload_request = HTTPRequest(
        method='GET', url=self.get_url('/instances'),
        headers={'AppScale-Secret': 'invalid-secret'}, body=None
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)
      self.assertEqual(context.exception.code, 401)
      self.assertEqual(context.exception.message, 'Invalid secret')

    # No operation_id.
    payload_request = HTTPRequest(
        method='GET', url=self.get_url('/instances'), headers={
          'AppScale-Secret': 'secret'}
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)
      self.assertEqual(context.exception.code, 400)
      self.assertEqual(context.exception.message,
                       'operation_id is a required parameter')

    operation_id = '0000000000'
    # operation_id not valid.
    payload_request = HTTPRequest(
        method='GET', url=self.get_url('/instances?operation_id={}'.format(
            operation_id)),
        headers={'AppScale-Secret': 'secret'}
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)
      self.assertEqual(context.exception.code, 404)
      self.assertEqual(context.exception.message, 'Operation id not found')

    # operation_id valid.
    vm_info = {
      'public_ips': ['public-ip'],
      'private_ips': ['private-ip'],
      'instance_ids': ['i-id']
    }
    status_info = {
      'success': True,
      'reason': 'received run request',
      'state': iaas.InstancesHandler.STATE_SUCCESS,
      'vm_info': vm_info
    }
    iaas.operation_ids[operation_id] = status_info
    result = iaas.operation_ids.get(operation_id)
    payload_request = HTTPRequest(
        method='GET', url=self.get_url('/instances?operation_id={}'.format(operation_id)),
        headers={'AppScale-Secret': 'secret'}
    )
    response = yield self.http_client.fetch(payload_request)
    self.assertEqual(response.code, 200)
    self.assertEquals(result, json.loads(response.body))


  @gen_test
  def test_run_instances_fail_cases(self):
    """Success cases are done in the test_{cloud}_agent files."""
    # No secret header.
    payload_request = HTTPRequest(
        method='POST', url=self.get_url('/instances'), headers=None,
        body=json.dumps(None)
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)
      self.assertEqual(context.exception.code, 401)
      self.assertEqual(context.exception.message, 'Invalid secret')

    # Invalid secret header.
    payload_request = HTTPRequest(
        method='POST', url=self.get_url('/instances'),
        headers={'AppScale-Secret': 'invalid-secret'}, body=json.dumps(None)
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)
      self.assertEqual(context.exception.code, 401)
      self.assertEqual(context.exception.message, 'Invalid secret')

    # Missing parameters.
    params1 = json.dumps({})
    payload_request = HTTPRequest(
        method='POST', url=self.get_url('/instances'),
        headers={'AppScale-Secret': 'secret'}, body=params1
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)

      self.assertEqual(context.exception.code, 400)
      self.assertEqual(context.exception.message,
                       'infrastructure is a required parameter')

    params2 = json.dumps({})
    payload_request = HTTPRequest(
        method='POST', url=self.get_url('/instances'),
        headers={'AppScale-Secret': 'secret'}, body=params2
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)

      self.assertEqual(context.exception.code, 400)
      self.assertEqual(context.exception.message,
                       'num_vms is a required parameter')

    params = json.dumps({'num_vms': 0})
    payload_request = HTTPRequest(
        method='POST', url=self.get_url('/instances'),
        headers={'AppScale-Secret': 'secret'}, body=params
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)

      self.assertEqual(context.exception.code, 400)
      self.assertEqual(context.exception.message, 'Invalid VM count: 0')

    # Passing parameter verification and calling __spawn_vms.
    iaas.agent_params = MagicMock(state_details=full_params)
    #with patch.dict(iaas.agent_params.state_details, full_params):
    # Successful calls ignoring callback of __spawn_vms
    with patch.object(iaas.InstancesHandler, 'get_agent', return_value=EC2Agent):
      with patch.object(IOLoop, 'spawn_callback', return_value=None):
        params = json_encode({'num_vms': 1})
        payload_request = HTTPRequest(
            method='POST', url=self.get_url('/instances'),
            headers={'AppScale-Secret': 'secret'}, body=params
        )
        response = yield self.http_client.fetch(payload_request)
        self.assertEqual(response.code, 200)
        self.assertTrue(iaas.PARAM_OPERATION_ID in json_decode(response.body))

      vm_info = {
        'public_ips': ['public-ip'],
        'private_ips': ['private-ip'],
        'instance_ids': ['i-id']
      }
      vm_info_return = (['public-ip'], ['private-ip'], ['i-id'])

      with patch.object(EC2Agent, 'run_instances',
                        side_effect=[vm_info_return, AgentRuntimeException(
                            "Runtime Exception")]):
        # No Exception raised.
        params = json.dumps({'num_vms': 1})
        payload_request = HTTPRequest(
            method='POST', url=self.get_url('/instances'),
            headers={'AppScale-Secret': 'secret'}, body=params
        )
        response = yield self.http_client.fetch(payload_request)
        self.assertEqual(response.code, 200)
        self.assertTrue(iaas.PARAM_OPERATION_ID in json_decode(response.body))
        operation_id = json_decode(response.body)[iaas.PARAM_OPERATION_ID]

        status_info = {
          'success': True,
          'reason': 'received run request',
              'state': iaas.InstancesHandler.STATE_SUCCESS,
          'vm_info': vm_info
        }
        iaas.operation_ids[operation_id] = status_info
        result = iaas.operation_ids.get(operation_id)
        payload_request = HTTPRequest(
            method='GET', url=self.get_url('/instances?operation_id={}'.format(operation_id)), headers={
              'AppScale-Secret': 'secret'}
        )
        response = yield self.http_client.fetch(payload_request)
        self.assertEqual(response.code, 200)
        self.assertEquals(result, json.loads(response.body))

        params = json.dumps({'num_vms': 1})
        payload_request = HTTPRequest(
            method='POST', url=self.get_url('/instances'),
            headers={'AppScale-Secret': 'secret'}, body=params
        )
        response = yield self.http_client.fetch(payload_request)
        self.assertEqual(response.code, 200)
        self.assertTrue(iaas.PARAM_OPERATION_ID in json_decode(response.body))
        operation_id = json_decode(response.body)[iaas.PARAM_OPERATION_ID]
        # operation_id valid.
        status_info = {
          'success': False,
          'reason': str(AgentRuntimeException),
          'state': iaas.InstancesHandler.STATE_FAILED,
        }
        iaas.operation_ids[operation_id] = status_info
        result = iaas.operation_ids.get(operation_id)
        payload_request = HTTPRequest(
            method='GET', url=self.get_url('/instances?operation_id={}'.format(operation_id)), headers={
              'AppScale-Secret': 'secret'}
        )
        response = yield self.http_client.fetch(payload_request)
        self.assertEqual(response.code, 200)
        self.assertEquals(result, json.loads(response.body))

  @gen_test
  def test_terminate_instances(self):
    """Success cases are done in the test_{cloud}_agent files."""
    # No secret header.
    payload_request = HTTPRequest(
        method='DELETE', url=self.get_url('/instances'), headers=None
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)

      self.assertEqual(context.exception.code, 401)
      self.assertEqual(context.exception.message, 'Invalid secret')

    # Invalid secret header.
    payload_request = HTTPRequest(
        method='DELETE', url=self.get_url('/instances'),
        headers={'AppScale-Secret': 'invalid-secret'}
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)

      self.assertEqual(context.exception.code, 401)
      self.assertEqual(context.exception.message, 'Invalid secret')

    payload_request = HTTPRequest(
        method='DELETE', url=self.get_url('/instances'),
        headers={'AppScale-Secret': 'secret'}
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)

      self.assertEqual(context.exception.code, 400)
      self.assertEqual(context.exception.message,
                       'num_vms is a required parameter')

    test_instance_id = 'i-foobar'
    # Successful calls ignoring callback of __kill_vms
    with patch.object(iaas.InstancesHandler, 'get_agent', return_value=EC2Agent):
      with patch.dict(iaas.agent_params.state_details, full_params):
        with patch.object(IOLoop, 'spawn_callback', return_value=None):
          payload_request = HTTPRequest(
              method='DELETE',
              url=self.get_url('/instances?instance_id={}'.format(test_instance_id)),
              headers={'AppScale-Secret': 'secret'}
          )
          response = yield self.http_client.fetch(payload_request)
          self.assertEqual(response.code, 200)
          self.assertTrue(iaas.PARAM_OPERATION_ID in json_decode(response.body))

        with patch.object(EC2Agent,
                          'terminate_instances',
                          side_effect=[None, AgentRuntimeException("Exception!")]):
          # No Exception raised.
          payload_request = HTTPRequest(
              method='DELETE',
              url=self.get_url('/instances?instance_id={}'.format(test_instance_id)),
              headers={'AppScale-Secret': 'secret'}
          )
          response = yield self.http_client.fetch(payload_request)
          self.assertEqual(response.code, 200)
          self.assertTrue(iaas.PARAM_OPERATION_ID in json_decode(response.body))
          operation_id = json_decode(response.body)[iaas.PARAM_OPERATION_ID]

          # operation_id valid.

          status_info = {
            'success': True,
            'reason': 'received kill request',
            'state': iaas.InstancesHandler.STATE_SUCCESS,
          }
          iaas.operation_ids[operation_id] = status_info
          result = iaas.operation_ids.get(operation_id)
          payload_request = HTTPRequest(
              method='GET',
              url=self.get_url('/instances?operation_id={}'.format(operation_id)),
              headers={'AppScale-Secret': 'secret'}
          )
          response = yield self.http_client.fetch(payload_request)
          self.assertEqual(response.code, 200)
          self.assertEquals(result, json.loads(response.body))

          # AgentRuntimeException raised.
          payload_request = HTTPRequest(
              method='DELETE',
              url=self.get_url('/instances?instance_id={}'.format(test_instance_id)),
              headers={'AppScale-Secret': 'secret'}
          )
          response = yield self.http_client.fetch(payload_request)
          self.assertEqual(response.code, 200)
          self.assertTrue(iaas.PARAM_OPERATION_ID in json_decode(response.body))
          operation_id = json_decode(response.body)[iaas.PARAM_OPERATION_ID]
          # operation_id valid.
          status_info = {
            'success': False,
            'state': iaas.InstancesHandler.STATE_FAILED,
            'reason': str(AgentRuntimeException)
          }
          iaas.operation_ids[operation_id] = status_info
          result = iaas.operation_ids.get(operation_id)
          payload_request = HTTPRequest(
              method='GET', url=self.get_url('/instances?operation_id={}'.format(operation_id)), headers={
                'AppScale-Secret': 'secret'}
          )
          response = yield self.http_client.fetch(payload_request)
          self.assertEqual(response.code, 200)
          self.assertEquals(result, json.loads(response.body))
