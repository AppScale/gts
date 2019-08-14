import json

import appscale.infrastructure as iaas

from tornado.testing import AsyncHTTPTestCase, gen_test
from tornado.httpclient import HTTPRequest, HTTPError
from tornado.ioloop import IOLoop
from mock import patch, MagicMock

from appscale.agents.base_agent import AgentRuntimeException
from appscale.agents.ec2_agent import EC2Agent

full_params = {
  'a': 'b', 'EC2_URL': 'http://testing.appscale.com:8773/foo/bar',
  'EC2_ACCESS_KEY': 'access_key', 'EC2_SECRET_KEY': 'secret_key',
  'group': 'boogroup',
  'machine': 'booid',
  'infrastructure': 'ec2',
  'instance_type': 'booinstance_type',
  'keyname': 'bookeyname',
  'use_spot_instances': False,
  'region': 'my-zone-1',
  'zone': 'my-zone-1b',
  'autoscale_agent': True
}

class TestInfrastructureManager(AsyncHTTPTestCase):

  def get_app(self):
    return iaas.make_app("secret", True)

  ############################################################
  # InstancesHandler tests
  ############################################################
  @gen_test
  def test_describe_instances(self):
    # No secret header.
    payload_request = HTTPRequest(
        allow_nonstandard_methods=True, method='GET',
        url=self.get_url('/instances'), headers=None, body=None
    )
    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)
      self.assertEqual(context.exception.code, 401)
      self.assertEqual(context.exception.message, 'Invalid secret')

    # Invalid secret header.
    payload_request = HTTPRequest(
        allow_nonstandard_methods=True, method='GET',
        url=self.get_url('/instances'),
        headers={'AppScale-Secret': 'invalid-secret'}, body=None
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)
      self.assertEqual(context.exception.code, 401)
      self.assertEqual(context.exception.message, 'Invalid secret')

    # No operation_id.
    payload_request = HTTPRequest(
        allow_nonstandard_methods=True, method='GET',
        url=self.get_url('/instances'),
        headers={'AppScale-Secret': 'secret'}, body=json.dumps({})
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)
      self.assertEqual(context.exception.code, 400)
      self.assertEqual(context.exception.message,
                       'operation_id is a required parameter')

    operation_id = '0000000000'
    # operation_id not valid.
    payload_request = HTTPRequest(
        allow_nonstandard_methods=True, method='GET',
        url=self.get_url('/instances'),
        body=json.dumps({'operation_id': operation_id}),
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
        allow_nonstandard_methods=True,
        method='GET', url=self.get_url('/instances'),
        body=json.dumps({'operation_id': operation_id}),
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
        body=json.dumps({})
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)
      self.assertEqual(context.exception.code, 401)
      self.assertEqual(context.exception.message, 'Invalid secret')

    # Invalid secret header.
    payload_request = HTTPRequest(
        method='POST', url=self.get_url('/instances'),
        headers={'AppScale-Secret': 'invalid-secret'}, body=json.dumps({})
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

    params2 = json.dumps(full_params)
    payload_request = HTTPRequest(
        method='POST', url=self.get_url('/instances'),
        headers={'AppScale-Secret': 'secret'}, body=params2
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)

      self.assertEqual(context.exception.code, 400)
      self.assertEqual(context.exception.message,
                       'num_vms is a required parameter')

    params_copy = full_params.copy()
    params_copy['num_vms'] = 0
    params = json.dumps(params_copy)
    payload_request = HTTPRequest(
        method='POST', url=self.get_url('/instances'),
        headers={'AppScale-Secret': 'secret'}, body=params
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)

      self.assertEqual(context.exception.code, 400)
      self.assertEqual(context.exception.message, 'Invalid VM count: 0')

    params_copy = full_params.copy()
    params_copy['num_vms'] = 1
    run_params = json.dumps(params_copy)

    # Passing parameter verification and calling __spawn_vms.
    # Successful calls ignoring callback of __spawn_vms
    with patch.object(EC2Agent, 'assert_credentials_are_valid'):
      with patch.object(IOLoop, 'spawn_callback', return_value=None):
        payload_request = HTTPRequest(
            method='POST', url=self.get_url('/instances'),
            headers={'AppScale-Secret': 'secret'}, body=run_params
        )
        response = yield self.http_client.fetch(payload_request)
        self.assertEqual(response.code, 200)
        self.assertTrue(iaas.PARAM_OPERATION_ID in json.loads(response.body))
        operation_id = json.loads(response.body)[iaas.PARAM_OPERATION_ID]

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
            allow_nonstandard_methods=True,
            method='GET', url=self.get_url('/instances'),
            body=json.dumps({'operation_id': operation_id}),
            headers={'AppScale-Secret': 'secret'}
        )
        response = yield self.http_client.fetch(payload_request)
        self.assertEqual(response.code, 200)
        self.assertEquals(result, json.loads(response.body))

        payload_request = HTTPRequest(
            method='POST', url=self.get_url('/instances'),
            headers={'AppScale-Secret': 'secret'}, body=run_params
        )
        response = yield self.http_client.fetch(payload_request)
        self.assertEqual(response.code, 200)
        self.assertTrue(iaas.PARAM_OPERATION_ID in json.loads(response.body))
        operation_id = json.loads(response.body)[iaas.PARAM_OPERATION_ID]
        # operation_id valid.
        status_info = {
          'success': False,
          'reason': str(AgentRuntimeException),
          'state': iaas.InstancesHandler.STATE_FAILED,
        }
        iaas.operation_ids[operation_id] = status_info
        result = iaas.operation_ids.get(operation_id)
        payload_request = HTTPRequest(
            allow_nonstandard_methods=True,
            method='GET', url=self.get_url('/instances'),
            body=json.dumps({'operation_id': operation_id}),
            headers={'AppScale-Secret': 'secret'}
        )
        response = yield self.http_client.fetch(payload_request)
        self.assertEqual(response.code, 200)
        self.assertEquals(result, json.loads(response.body))

  @gen_test
  def test_terminate_instances(self):
    """Success cases are done in the test_{cloud}_agent files."""
    # No secret header.
    payload_request = HTTPRequest(
        method='DELETE', url=self.get_url('/instances'), headers={}
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
        allow_nonstandard_methods=True,
        method='DELETE', url=self.get_url('/instances'),
        headers={'AppScale-Secret': 'secret'}, body=json.dumps({})
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)

      self.assertEqual(context.exception.code, 400)
      self.assertEqual(context.exception.message,
                       'infrastructure is a required parameter')

    payload_request = HTTPRequest(
        allow_nonstandard_methods=True,
        method='DELETE', url=self.get_url('/instances'),
        headers={'AppScale-Secret': 'secret'}, body=json.dumps(full_params)
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)

      self.assertEqual(context.exception.code, 400)
      self.assertEqual(context.exception.message,
                       'instance_ids is a required parameter')

    params_copy = full_params.copy()
    params_copy['instance_ids'] = ['i-foobar']
    terminate_params = json.dumps(params_copy)

    # Successful calls ignoring callback of __kill_vms
    with patch.object(EC2Agent, 'assert_credentials_are_valid'):
      with patch.object(IOLoop, 'spawn_callback', return_value=None):
        payload_request = HTTPRequest(
            allow_nonstandard_methods=True,
            method='DELETE',
            url=self.get_url('/instances'), body=terminate_params,
            headers={'AppScale-Secret': 'secret'}
        )
        response = yield self.http_client.fetch(payload_request)
        self.assertEqual(response.code, 200)
        self.assertTrue(iaas.PARAM_OPERATION_ID in json.loads(response.body))
        operation_id = json.loads(response.body)[iaas.PARAM_OPERATION_ID]

        # operation_id valid.

        status_info = {
          'success': True,
          'reason': 'received kill request',
          'state': iaas.InstancesHandler.STATE_SUCCESS,
        }
        iaas.operation_ids[operation_id] = status_info
        result = iaas.operation_ids.get(operation_id)
        payload_request = HTTPRequest(
            allow_nonstandard_methods=True,
            method='GET',
            url=self.get_url('/instances'),
            body=json.dumps({'operation_id': operation_id}),
            headers={'AppScale-Secret': 'secret'}
        )
        response = yield self.http_client.fetch(payload_request)
        self.assertEqual(response.code, 200)
        self.assertEquals(result, json.loads(response.body))

        # AgentRuntimeException raised.
        payload_request = HTTPRequest(
            allow_nonstandard_methods=True,
            method='DELETE',
            url=self.get_url('/instances'), body=terminate_params,
            headers={'AppScale-Secret': 'secret'}
        )
        response = yield self.http_client.fetch(payload_request)
        self.assertEqual(response.code, 200)
        self.assertTrue(iaas.PARAM_OPERATION_ID in json.loads(response.body))
        operation_id = json.loads(response.body)[iaas.PARAM_OPERATION_ID]
        # operation_id valid.
        status_info = {
          'success': False,
          'state': iaas.InstancesHandler.STATE_FAILED,
          'reason': str(AgentRuntimeException)
        }
        iaas.operation_ids[operation_id] = status_info
        result = iaas.operation_ids.get(operation_id)
        payload_request = HTTPRequest(
            allow_nonstandard_methods=True,
            method='GET', url=self.get_url('/instances'),
            body=json.dumps({'operation_id': operation_id}),
            headers={'AppScale-Secret': 'secret'}
        )
        response = yield self.http_client.fetch(payload_request)
        self.assertEqual(response.code, 200)
        self.assertEquals(result, json.loads(response.body))

  ############################################################
  # InstancesHandler helper methods tests
  ############################################################
  @gen_test
  def test_spawn_vms(self):
    no_vms = ([], [], [])
    vm_info_return = (['i-id'], ['public-ip'], ['private-ip'])
    describe_vms_return = (['public-ip'], ['private-ip'], ['i-id'])
    agent_exception = AgentRuntimeException("Runtime Exception")
    mocked_agent = EC2Agent()
    mocked_agent.assert_credentials_are_valid = MagicMock()
    mocked_agent.run_instances = MagicMock(side_effect=[vm_info_return,
                                                        agent_exception,
                                                        agent_exception])
    mocked_agent.describe_instances = MagicMock(side_effect=[no_vms,
                                                             describe_vms_return])
    mocked_agent.configure_instance_security = MagicMock()

    initial_status_info = {
      'success': False,
      'reason': 'received run request',
      'state': iaas.InstancesHandler.STATE_PENDING
    }
    iaas.operation_ids['op_id'] = initial_status_info
    iaas.InstancesHandler._spawn_vms(mocked_agent, 1, full_params, 'op_id')
    vm_info = {
      'public_ips': ['public-ip'],
      'private_ips': ['private-ip'],
      'instance_ids': ['i-id']
    }

    result_status_info = {
      'success': True,
      'reason': 'received run request',
      'state': iaas.InstancesHandler.STATE_SUCCESS,
      'vm_info': vm_info
    }

    self.assertEqual(iaas.operation_ids['op_id'], result_status_info)

    # Exception happened but vms were started.
    mocked_agent.describe_instances = MagicMock(side_effect=[no_vms,
                                                             describe_vms_return])
    initial_status_info = {
      'success': False,
      'reason': 'received run request',
      'state': iaas.InstancesHandler.STATE_PENDING
    }
    iaas.operation_ids['op_id_2'] = initial_status_info
    iaas.InstancesHandler._spawn_vms(mocked_agent, 1, full_params, 'op_id_2')

    result_status_info = {
      'success': False,
      'reason': str(agent_exception),
      'state': iaas.InstancesHandler.STATE_SUCCESS,
      'vm_info': vm_info
    }

    self.assertEqual(iaas.operation_ids['op_id_2'], result_status_info)

    # Exception happened but vms were not started.
    mocked_agent.describe_instances = MagicMock(side_effect=[no_vms, no_vms])
    initial_status_info = {
      'success': False,
      'reason': 'received run request',
      'state': iaas.InstancesHandler.STATE_PENDING
    }
    iaas.operation_ids['op_id_3'] = initial_status_info
    iaas.InstancesHandler._spawn_vms(mocked_agent, 1, full_params, 'op_id_3')
    result_status_info = {
      'success': False,
      'reason': str(agent_exception),
      'state': iaas.InstancesHandler.STATE_FAILED,
    }

    self.assertEqual(iaas.operation_ids['op_id_3'], result_status_info)

  @gen_test
  def test_kill_vms(self):
    agent_exception = AgentRuntimeException("Runtime Exception")
    mocked_agent = EC2Agent()
    mocked_agent.terminate_instances = MagicMock(side_effect=[None,
                                                              agent_exception])

    initial_status_info = {
      'success': False,
      'reason': 'received kill request',
      'state': iaas.InstancesHandler.STATE_PENDING,
      'vm_info': None
    }
    iaas.operation_ids['op_id'] = initial_status_info
    terminate_params = full_params.copy()
    terminate_params['instance_ids'] = ['i-foobar']
    iaas.InstancesHandler._kill_vms(mocked_agent, terminate_params, 'op_id')

    result_status_info = {
      'success': True,
      'reason': 'received kill request',
      'state': iaas.InstancesHandler.STATE_SUCCESS,
      'vm_info': None
    }

    self.assertEqual(iaas.operation_ids['op_id'], result_status_info)

    initial_status_info = {
      'success': False,
      'reason': 'received kill request',
      'state': iaas.InstancesHandler.STATE_PENDING,
      'vm_info': None
    }
    iaas.operation_ids['op_id_2'] = initial_status_info
    iaas.InstancesHandler._kill_vms(mocked_agent, terminate_params, 'op_id_2')
    result_status_info = {
      'success': False,
      'reason': str(agent_exception),
      'state': iaas.InstancesHandler.STATE_FAILED,
      'vm_info': None
    }

    self.assertEqual(iaas.operation_ids['op_id_2'], result_status_info)

  @gen_test
  def test_describe_vms(self):
    agent_exception = AgentRuntimeException("Runtime Exception")
    vm_info_return = (['public-ip'], ['private-ip'], ['i-id'])
    mocked_agent = EC2Agent()
    mocked_agent.describe_instances= MagicMock(side_effect=[vm_info_return,
                                                            agent_exception])
    # Test describe vms returns values.
    expected = vm_info_return
    actual = iaas.InstancesHandler._describe_vms(mocked_agent, full_params)
    self.assertEquals(actual, expected)

    # Test describe vms runs into exception.

    with self.assertRaises(AgentRuntimeException):
      iaas.InstancesHandler._describe_vms(mocked_agent, full_params)
    self.assertEquals(actual, expected)

  ############################################################
  # InstanceHandler tests
  ############################################################

  @gen_test
  def test_attach_disk(self):
    """Success cases are done in the test_{cloud}_agent files."""
    # No secret header.
    payload_request = HTTPRequest(
        method='POST', url=self.get_url('/instance'), headers=None,
        body=json.dumps({})
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)
      self.assertEqual(context.exception.code, 401)
      self.assertEqual(context.exception.message, 'Invalid secret')

    # Invalid secret header.
    payload_request = HTTPRequest(
        method='POST', url=self.get_url('/instance'),
        headers={'AppScale-Secret': 'invalid-secret'}, body=json.dumps({})
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)
      self.assertEqual(context.exception.code, 401)
      self.assertEqual(context.exception.message, 'Invalid secret')

    # Missing parameters.
    params1 = json.dumps({})
    payload_request = HTTPRequest(
        method='POST', url=self.get_url('/instance'),
        headers={'AppScale-Secret': 'secret'}, body=params1
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)

      self.assertEqual(context.exception.code, 400)
      self.assertEqual(context.exception.message,
                       'disk_name is a required parameter')

    params2 = json.dumps({'disk_name': 'foo'})
    payload_request = HTTPRequest(
        method='POST', url=self.get_url('/instance'),
        headers={'AppScale-Secret': 'secret'}, body=params2
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)

      self.assertEqual(context.exception.code, 400)
      self.assertEqual(context.exception.message,
                       'instance_id is a required parameter')

    params3 = json.dumps({'disk_name': 'foo', 'instance_id': 'i-foobar'})
    payload_request = HTTPRequest(
        method='POST', url=self.get_url('/instance'),
        headers={'AppScale-Secret': 'secret'}, body=params3
    )

    with self.assertRaises(HTTPError) as context:
      yield self.http_client.fetch(payload_request)

      self.assertEqual(context.exception.code, 400)
      self.assertEqual(context.exception.message,
                       'infrastructure is a required parameter')

    params_copy = full_params.copy()
    params_copy.update({'disk_name': 'foo', 'instance_id': 'i-foobar'})
    attach_params = json.dumps(params_copy)

    attach_exception = AgentRuntimeException("Runtime Exception")
    with patch.object(EC2Agent, 'assert_credentials_are_valid'):
      with patch.object(EC2Agent, 'attach_disk', side_effect=[
          attach_exception, '/dev/sdc']):
        payload_request = HTTPRequest(
            method='POST', url=self.get_url('/instance'),
            headers={'AppScale-Secret': 'secret'}, body=attach_params
        )
        with self.assertRaises(HTTPError) as context:
          yield self.http_client.fetch(payload_request)

          self.assertEqual(context.exception.code, 500)
          self.assertEqual(context.exception.message,
                           'Error attaching disk! {}'.format(attach_exception))

        response = yield self.http_client.fetch(payload_request)
        self.assertEqual(response.code, 200)
        self.assertTrue('location' in json.loads(response.body))
        self.assertEqual(json.loads(response.body)['location'], '/dev/sdc')
