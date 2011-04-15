$:.unshift File.join(File.dirname(__FILE__))
require 'cron_helper'
require 'load_balancer'
require 'monitoring'
require 'haproxy'
require 'collectd'
require 'nginx'
require 'helperfunctions'

APPSCALE_HOME = ENV['APPSCALE_HOME']

tree = YAML.load_file("#{APPSCALE_HOME}/.appscale/database_info.yaml")
table = tree[:table]

CronHelper.clear_crontab
`bash #{APPSCALE_HOME}/AppController/killDjinn.sh`
# we should not call appscale-controller because it is parent.
#`service appscale-controller stop`

`rm -f #{APPSCALE_HOME}/.appscale/secret.key`
#`rm -rf /tmp/*.log`
#`rm -rf /tmp/h*`
`rm -f #{APPSCALE_HOME}/.appscale/status-*`
`rm -f #{APPSCALE_HOME}/.appscale/database_info`
`rm -f #{APPSCALE_HOME}/.appscale/neptune_info.txt`
`rm -f /tmp/uploaded-apps`
`rm -f ~/.appscale_cookies`

#`rm -f /tmp/mysql.sock`
Nginx.clear_sites_enabled
HAProxy.clear_sites_enabled
Collectd.clear_sites_enabled
Collectd.clear_monitoring_data
Nginx.stop
HAProxy.stop
Collectd.stop
LoadBalancer.stop
Monitoring.stop
PbServer.stop(table)
Ejabberd.stop
Ejabberd.clear_online_users

# klogd is installed on jaunty but not karmic
klogd = "/etc/init.d/klogd"
if File.exists?(klogd)
  `#{klog} stop`
end

`rm -rf /var/apps/`
`rm -rf #{APPSCALE_HOME}/.appscale/*.pid`
`rm -rf /tmp/ec2/*`
`rm -rf /tmp/*started`
`rm -rf #{APPSCALE_HOME}/appscale/`

`echo "" > /root/.ssh/known_hosts` # empty it out but leave the file there

# force kill processes

["memcached",
 "nginx", "haproxy", "collectd", "collectdmon", "tcpdump",
 "soap_server", "appscale_server",
 "AppLoadBalancer", "AppMonitoring",
 # AppServer
 "dev_appserver", "DevAppServerMain",
 #Blobstore
 "blobstore_server",
 # Cassandra
 "CassandraDaemon",
 # Hadoop
 "NameNode", "DataNode", "JobTracker", "TaskTracker",
 # HBase, ZooKeeper
 "HMaster", "HRegionServer", "HQuorumPeer", "QuorumPeerMain",
 "ThriftServer",
 # Hypertable
 "Hyperspace", "Hypertable.Master", "Hypertable.RangeServer", "ThriftBroker",
 "DfsBroker",
 # Memcachedb
 "memcachedb",
 # MongoDB
 "mongod", "mongo", "mongos",
 # MySQL
 "ndb_mgmd", "ndbd", "mysqld",
 # Scalaris
 "activemq",
 "beam", "epmd",
 # Voldemort
 "VoldemortServer",
# these are too general to kill
# "java", "python", "python2.6", "python2.5",
 "thin"
].each do |program|
  HelperFunctions.kill_process(program)
end
