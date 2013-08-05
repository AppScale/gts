#!/usr/bin/env python
# Programmer: Chris Bunch (chris@appscale.com)


# General-purpose Python library imports
import os.path
import time
try:
  from unittest import TestCase
except ImportError:
  from unittest.case import TestCase


# Third-party imports
import apiclient.discovery
import apiclient.errors
from flexmock import flexmock
import httplib2
import oauth2client.client
import oauth2client.file
import oauth2client.tools


# AppScale-specific imports
from agents.gce_agent import GCEAgent
from agents.factory import InfrastructureAgentFactory
from infrastructure_manager import InfrastructureManager
from utils import utils


class TestGCEAgent(TestCase):

  
  def setUp(self):
    self.project = '123456789'

    # Mock out reading the secret file
    flexmock(utils).should_receive('get_secret').and_return('secret')

    # Assume that our client_secrets.json file exists
    flexmock(os.path)
    os.path.should_call('exists')
    os.path.should_receive('exists').with_args(
      GCEAgent.CLIENT_SECRETS_LOCATION).and_return(True)

    self.reservation_id = '00000000'
    flexmock(utils).should_receive('get_random_alphanumeric').and_return(
      self.reservation_id)

    self.params = {
      'credentials' : {
        'EC2_URL': None,
        'EC2_ACCESS_KEY': None,
        'EC2_SECRET_KEY': None,
      },
      'project': self.project,
      'group': 'boogroup',
      'image_id': 'booid',
      'infrastructure': 'gce',
      'instance_type': 'booinstance_type',
      'keyname': 'bookeyname',
      'num_vms': '1',
      'use_spot_instances': False,
    }


  def test_gce_run_instances(self):
    # mock out interactions with GCE
    # first, mock out the oauth library calls
    fake_flow = flexmock(name='fake_flow')
    flexmock(oauth2client.client)
    oauth2client.client.should_receive('flow_from_clientsecrets').with_args(
      GCEAgent.CLIENT_SECRETS_LOCATION, scope=GCEAgent.GCE_SCOPE).and_return(
      fake_flow)

    fake_storage = flexmock(name='fake_storage')
    fake_storage.should_receive('get').and_return(None)

    flexmock(oauth2client.file)
    oauth2client.file.should_receive('Storage').with_args(
      GCEAgent.OAUTH2_STORAGE_LOCATION).and_return(fake_storage)

    fake_credentials = flexmock(name='fake_credentials')
    flexmock(oauth2client.tools)
    oauth2client.tools.should_receive('run').with_args(fake_flow,
      fake_storage).and_return(fake_credentials)

    # next, mock out http calls to GCE
    fake_http = flexmock(name='fake_http')
    fake_authorized_http = flexmock(name='fake_authorized_http')

    flexmock(httplib2)
    httplib2.should_receive('Http').and_return(fake_http)
    fake_credentials.should_receive('authorize').with_args(fake_http) \
      .and_return(fake_authorized_http)

    # add some fake data in where no instances are initially running, then one
    # is (in response to our insert request)
    no_instance_info = {
    }

    instance_id = u'appscale-bazgroup-feb10b11-62bc-4536-ac25-9734f2267d6d'
    list_instance_info = {
      u'items': [{
        u'status': u'RUNNING',
        u'kind': u'compute#instance',
        u'machineType': u'https://www.googleapis.com/compute/v1beta14/projects/appscale.com:appscale/global/machineTypes/n1-standard-1',
        u'name': instance_id,
        u'zone': u'https://www.googleapis.com/compute/v1beta14/projects/appscale.com:appscale/zones/us-central1-a',
        u'tags': {u'fingerprint': u'42WmSpB8rSM='},
        u'image': u'https://www.googleapis.com/compute/v1beta14/projects/appscale.com:appscale/global/images/lucid64',
        u'disks': [{
          u'index': 0,
          u'kind': u'compute#attachedDisk',
          u'type': u'EPHEMERAL',
          u'mode': u'READ_WRITE'
        }],
        u'canIpForward': False,
        u'serviceAccounts': [{
          u'scopes': [GCEAgent.GCE_SCOPE],
          u'email': u'961228229472@project.gserviceaccount.com'
        }],
        u'metadata': {
          u'kind': u'compute#metadata',
          u'fingerprint': u'42WmSpB8rSM='
        },
        u'creationTimestamp': u'2013-05-22T11:52:33.254-07:00',
        u'id': u'8684033495853907982',
        u'selfLink': u'https://www.googleapis.com/compute/v1beta14/projects/appscale.com:appscale/zones/us-central1-a/instances/appscale-bazgroup-feb10b11-62bc-4536-ac25-9734f2267d6d',
        u'networkInterfaces': [{
          u'accessConfigs': [{
            u'kind': u'compute#accessConfig',
            u'type': u'ONE_TO_ONE_NAT',
            u'name': u'External NAT',
            u'natIP': u'public-ip'
          }],
          u'networkIP': u'private-ip',
          u'network': u'https://www.googleapis.com/compute/v1beta14/projects/appscale.com:appscale/global/networks/bazgroup',
          u'name': u'nic0'
        }]
      }],
      u'kind': u'compute#instanceList',
      u'id': u'projects/appscale.com:appscale/zones/us-central1-a/instances',
      u'selfLink': u'https://www.googleapis.com/compute/v1beta14/projects/961228229472/zones/us-central1-a/instances'
    }

    fake_list_instance_request = flexmock(name='fake_list_instance_request')
    fake_list_instance_request.should_receive('execute').with_args(
      fake_authorized_http).and_return(no_instance_info).and_return(
        list_instance_info)

    fake_instances = flexmock(name='fake_instances')
    fake_gce = flexmock(name='fake_gce')
    fake_gce.should_receive('instances').and_return(fake_instances)
    fake_instances.should_receive('list').with_args(project=self.project,
      filter="name eq appscale-boogroup-.*", zone=GCEAgent.DEFAULT_ZONE) \
      .and_return(fake_list_instance_request)

    # we only need to create one node, so set up mocks for that
    add_instance = u'operation-1369248752891-4dd5311848461-afc55a20'
    add_instance_info = {
      u'status': u'PENDING',
      u'kind': u'compute#operation',
      u'name': add_instance,
      u'azone': unicode(GCEAgent.GCE_URL) + u'appscale.com:appscale/zones/us-central1-a',
      u'startTime': u'2013-05-22T11:52:32.939-07:00',
      u'insertTime': u'2013-05-22T11:52:32.891-07:00',
      u'targetLink': unicode(GCEAgent.GCE_URL) + u'appscale.com:appscale/zones/us-central1-a/instances/appscale-bazgroup-feb10b11-62bc-4536-ac25-9734f2267d6d',
      u'operationType': u'insert',
      u'progress': 0,
      u'id': u'6663616273628949255',
      u'selfLink': unicode(GCEAgent.GCE_URL) + u'appscale.com:appscale/zones/us-central1-a/operations/operation-1369248752891-4dd5311848461-afc55a20',
      u'user': u'Chris@appscale.com'
    }

    fake_add_instance_request = flexmock(name='fake_add_instance_request')
    fake_add_instance_request.should_receive('execute').with_args(
      fake_authorized_http).and_return(add_instance_info)

    fake_instances.should_receive('insert').with_args(project=self.project,
      body=dict, zone=str).and_return(fake_add_instance_request)

    created_instance_info = {
      u'status': u'DONE'
    }

    fake_instance_checker = flexmock(name='fake_network_checker')
    fake_instance_checker.should_receive('execute').and_return(
      created_instance_info)

    fake_blocker = flexmock(name='fake_blocker')
    fake_gce.should_receive('globalOperations').and_return(fake_blocker)
    fake_blocker.should_receive('get').with_args(project=self.project,
      operation=add_instance).and_return(fake_instance_checker)

    # finally, inject our fake GCE connection
    flexmock(apiclient.discovery)
    apiclient.discovery.should_receive('build').with_args('compute',
      GCEAgent.API_VERSION).and_return(fake_gce)

    i = InfrastructureManager(blocking=True)

    # first, validate that the run_instances call goes through successfully
    # and gives the user a reservation id
    full_result = {
      'success': True,
      'reservation_id': self.reservation_id,
      'reason': 'none'
    }
    self.assertEquals(full_result, i.run_instances(self.params, 'secret'))

    # next, look at run_instances internally to make sure it actually is
    # updating its reservation info
    self.assertEquals(InfrastructureManager.STATE_RUNNING, i.reservations.get(
      self.reservation_id)['state'])
    vm_info = i.reservations.get(self.reservation_id)['vm_info']
    self.assertEquals(['public-ip'], vm_info['public_ips'])
    self.assertEquals(['private-ip'], vm_info['private_ips'])
    self.assertEquals([instance_id], vm_info['instance_ids'])


  def test_attach_persistent_disk(self):
    # mock out interactions with GCE
    # first, mock out the oauth library calls
    fake_flow = flexmock(name='fake_flow')
    flexmock(oauth2client.client)
    oauth2client.client.should_receive('flow_from_clientsecrets').with_args(
      GCEAgent.CLIENT_SECRETS_LOCATION, scope=GCEAgent.GCE_SCOPE).and_return(
      fake_flow)

    fake_storage = flexmock(name='fake_storage')
    fake_storage.should_receive('get').and_return(None)

    flexmock(oauth2client.file)
    oauth2client.file.should_receive('Storage').with_args(
      GCEAgent.OAUTH2_STORAGE_LOCATION).and_return(fake_storage)

    fake_credentials = flexmock(name='fake_credentials')
    flexmock(oauth2client.tools)
    oauth2client.tools.should_receive('run').with_args(fake_flow,
      fake_storage).and_return(fake_credentials)

    # next, mock out http calls to GCE
    fake_http = flexmock(name='fake_http')
    fake_authorized_http = flexmock(name='fake_authorized_http')

    flexmock(httplib2)
    httplib2.should_receive('Http').and_return(fake_http)
    fake_credentials.should_receive('authorize').with_args(fake_http) \
      .and_return(fake_authorized_http)

    fake_instances = flexmock(name='fake_instances')
    fake_gce = flexmock(name='fake_gce')
    fake_gce.should_receive('instances').and_return(fake_instances)

    attach_disk_info = {
      'status' : 'DONE'
    }

    fake_attach_disk_request = flexmock(name='fake_attach_disk_request')
    fake_attach_disk_request.should_receive('execute').with_args(
      fake_authorized_http).and_return(attach_disk_info)

    fake_instances.should_receive('attachDisk').with_args(project=self.project,
      body=dict, instance='my-instance', zone=str).and_return(
      fake_attach_disk_request)

    # finally, inject our fake GCE connection
    flexmock(apiclient.discovery)
    apiclient.discovery.should_receive('build').with_args('compute',
      GCEAgent.API_VERSION).and_return(fake_gce)

    iaas = InfrastructureManager(blocking=True)
    disk_name = 'my-disk-name'
    instance_id = 'my-instance'
    expected = '/dev/disk/by-id/google-{0}'.format(disk_name)
    actual = iaas.attach_disk(self.params, disk_name, instance_id, 'secret')
    self.assertTrue(actual['success'])
    self.assertEquals(expected, actual['location'])
