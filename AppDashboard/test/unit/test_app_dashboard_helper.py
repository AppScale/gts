from flexmock import flexmock
import sys
import os
import unittest
import urllib

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib/"))
from app_dashboard_helper import AppDashboardHelper

sys.path.append(os.path.join(os.path.expanduser("~"), "appscale/AppServer/"))
from google.appengine.api import users



class TestAppDashboardHelper(unittest.TestCase):

  def test_get_cookie_app_list(self):
    request = flexmock()
    request.cookies = { AppDashboardHelper.DEV_APPSERVER_LOGIN_COOKIE :
      urllib.quote('a@a.com:a:app1,app2:FAKEHASH') }

    output = AppDashboardHelper().get_cookie_app_list(request)
    self.assertTrue( len(output) == 2 )
    self.assertEquals('app1', output[0] )
    self.assertEquals('app2', output[1] )

  def test_update_cookie_app_list(self):
    fake_user = flexmock()
    fake_user.should_receive('email').and_return('a@a.com')
    flexmock(users).should_receive('get_current_user') \
      .and_return(fake_user)
    flexmock(AppDashboardHelper).should_receive('get_cookie_app_list') \
      .and_return(['app1', 'app2'])
    flexmock(AppDashboardHelper).should_receive('set_appserver_cookie') \
      .once()

    self.assertTrue(AppDashboardHelper().update_cookie_app_list(['app1',
      'app2', 'app3'], flexmock(), flexmock()))
    self.assertFalse(AppDashboardHelper().update_cookie_app_list(['app1',
      'app2'], flexmock(), flexmock()))

  def test_get_user_app_list(self):
    flexmock(AppDashboardHelper).should_receive('query_user_data') \
      .and_return('\napplications:app1:app2\n')
    output = AppDashboardHelper().get_user_app_list('a@a.com')
    self.assertTrue( len(output) == 2 )
    self.assertEquals('app1', output[0] )
    self.assertEquals('app2', output[1] )

  def setUpClusterStats(self):
    cluster_stats = [
      {
        # System stats provided by Hermes
        "cpu": {
          "idle": 50.0,
          "system": 28.2,
          "user": 10.5,
          "count": 2,
        },
        "partitions_dict": [
          {
            "/" : {
              "total": 30965743616,
              "free": 15482871808,
              "used": 15482871808,
            }
          }
        ],
        "memory": {
          "total": 12365412865,
          "available": 6472179712,
          "used": 8186245120
        },
        "swap": {
          "total": 2097147904,
          "free": 1210527744,
          "used": 886620160
        },
        "services": {
          # For each Process monitored by monit
          "cassandra": "Running",
        },
        "loadavg": {
          "last_1min": 0.08,
          "last_5min": 0.27,
          "last_15min": 0.33
        },
        # Node information provided by AppController itself
        "apps": {
          "test1": {
            # This hash is empty for non-shadow nodes
            "language": "python",
            "appservers": 4,
            "pending_appservers": 2,
            "http": 8080,
            "https": 4380,
            "reqs_enqueued": 15,
            "total_reqs": 6513
          },
          "test2": {
            # This hash is empty for non-shadow nodes
            "language": "python",
            "appservers": 4,
            "pending_appservers": 2,
            "http": 8080,
            "https": 4380,
            "reqs_enqueued": 15,
            "total_reqs": 6513
          }
        },
        "cloud": "cloud1",
        "state": "Done starting up AppScale, now in heartbeat mode",
        "db_location": "192.168.33.10",
        "public_ip": "1.1.1.1",
        "private_ip": "10.10.105.18",
        "roles": ["shadow", "zookeeper", "datastore", "taskqueue"],
      },
      {
        # System stats provided by Hermes
        "cpu": {
          "idle": 50.0,
          "system": 28.2,
          "user": 10.5,
          "count": 2,
        },
        "partitions_dict": [
          {
            "/" : {
              "total": 30965743616,
              "free": 15482871808,
              "used": 15482871808,
            }
          }
        ],
        "memory": {
          "total": 12365412865,
          "available": 6472179712,
          "used": 8186245120
        },
        "swap": {
          "total": 2,
          "free": 0,
          "used": 0
        },
        "services": {
          # For each Process monitored by monit
        },
        "loadavg": {
          "last_1min": 0.08,
          "last_5min": 0.27,
          "last_15min": 0.33
        },
        # Node information provided by AppController itself
        "apps": {},
        "cloud": "cloud1",
        "state": "Done starting up AppScale, now in heartbeat mode",
        "db_location": "192.168.33.10",
        "public_ip": "2.2.2.2",
        "private_ip": "10.10.105.19",
        "roles": ["appengine"],
      }
    ]
    fake_get_appcontroller_client = flexmock()
    fake_get_appcontroller_client.should_receive('get_cluster_stats') \
      .and_return(cluster_stats)
    return cluster_stats

  def setUpInstanceStats(self):
    instance_stats = [
      {'appid': 'test1',
       'host': '1.1.1.1',
       'port': 0000,
       'language': 'python'},
      {'appid': 'test1',
       'host': '1.1.1.1',
       'port': 0001,
       'language': 'python'},
      {'appid': 'test1',
       'host': '1.1.1.1',
       'port': 0002,
       'language': 'python'},
      {'appid': 'test2',
       'host': '2.2.2.2',
       'port': 1001,
       'language': 'python'},
      {'appid': 'test2',
       'host': '2.2.2.2',
       'port': 1002,
       'language': 'python'},
      {'appid': 'test2',
       'host': '2.2.2.2',
       'port': 1002,
       'language': 'python'}
    ]
    fake_get_appcontroller_client = flexmock()
    fake_get_appcontroller_client.should_receive('get_cluster_stats') \
      .and_return(instance_stats)

  def get_status_info(self):
    """ Queries our local AppController to get server-level information about
    every server running in this AppScale deployment.

    Returns:
      A list of dicts, where each dict contains VM-level info (e.g., CPU,
      memory, disk usage) about that machine. The empty list is returned if
      there was a problem retrieving this information.
    """
    cluster_stats = self.setUpClusterStats()
    statuses = AppDashboardHelper().get_status_info()
    test_statuses = []
    for node in cluster_stats:
      cpu_usage = 100.0 - node['cpu']['idle']
      total_memory = node['memory']['available'] + node['memory']['used']
      memory_usage = round(100.0 * node['memory']['used'] /
                           total_memory, 1)
      total_disk = 0
      total_used = 0
      for _, disk_info in node['partitions_dict'].iteritems():
        total_disk += disk_info['free'] + disk_info['used']
        total_used += disk_info['used']
      disk_usage = round(100.0 * total_used / total_disk, 1)
      test_statuses.append({'ip': node['public_ip'], 'cpu': str(cpu_usage),
                       'memory': str(memory_usage), 'disk': str(disk_usage),
                       'roles': node['roles'],
                       'key': str(node['public_ip']).translate(None, '.')})
    self.assertEqual(statuses, test_statuses)



  def get_instance_info(self, app_id):
    """ Queries the AppController to get instance information for a given app_id
    """
    self.setUpInstanceStats()
    instance_info = AppDashboardHelper().get_instance_info('test1')
    test1_instance_stats = [
      {
       'host': '1.1.1.1',
       'port': 0000,
       'language': 'python'},
      {
       'host': '1.1.1.1',
       'port': 0001,
       'language': 'python'},
      {
       'host': '1.1.1.1',
       'port': 0002,
       'language': 'python'}
    ]
    self.assertEqual(instance_info, test1_instance_stats)

  def get_version_info(self):
    """ Queries the AppController for information about active versions.

    Returns:
      A dictionary mapping version keys to serving URLs. A None value indicates
      that the version is still loading.
    """
    version_info = {
      'test1_default_v1': ['http://1.1.1.1:1', 'https://1.1.1.1:1'],
      'test2_default_v1': ['http://1.1.1.1:2', 'https://1.1.1.1:2']
    }
    flexmock(AppDashboardHelper)
    AppDashboardHelper.should_receive('get_login_host').and_return('1.1.1.1')
    AppDashboardHelper.should_receive('get_version_ports').and_return([1, 1])\
      .and_return([2, 2])
    self.setUpClusterStats()
    app_info = AppDashboardHelper().get_version_info()
    self.assertEqual(app_info, version_info)
